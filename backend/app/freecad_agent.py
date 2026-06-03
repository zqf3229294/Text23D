from __future__ import annotations

import html
import json
import queue
import subprocess
import textwrap
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import Settings
from .runner import CadRunner, RunnerResult
from .validation import CodeValidationError, validate_cadquery_code


@dataclass
class FreeCADToolResult:
    ok: bool
    content: dict[str, Any]
    asset_path: Path | None = None


def freecad_worker_command(settings: Settings, worker_script: Path) -> list[str]:
    executable = (
        settings.freecad_python
        or settings.freecad_gui_executable
        or "FreeCAD"
    )
    return [executable, str(worker_script)]


class FreeCADSession:
    tool_call_count: int
    tool_log_path: Path
    last_result: RunnerResult | None
    last_script_path: Path | None

    def begin_generation(self, generation_id: str, session_dir: Path) -> None:
        ...

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> FreeCADToolResult:
        ...

    def close(self) -> None:
        ...


class FreeCADWorkerClient:
    def __init__(self, settings: Settings, log_path: Path):
        self.settings = settings
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._stdout_queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self.process = self._start_process()
        self._start_reader_threads()

    def request(self, command: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.process.poll() is not None:
            raise RuntimeError(f"FreeCAD worker exited with {self.process.returncode}.")

        request_id = uuid.uuid4().hex
        payload = {"id": request_id, "command": command, "args": args or {}}
        with self._lock:
            assert self.process.stdin is not None
            self.process.stdin.write(json.dumps(payload) + "\n")
            self.process.stdin.flush()

            deadline = time.monotonic() + self.settings.freecad_worker_timeout_seconds
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"FreeCAD worker command timed out: {command}")
                try:
                    line = self._stdout_queue.get(timeout=remaining)
                except queue.Empty as exc:
                    raise TimeoutError(f"FreeCAD worker command timed out: {command}") from exc

                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    with self.log_path.open("a", encoding="utf-8") as handle:
                        handle.write(f"Non-JSON stdout from FreeCAD worker: {line}\n")
                    continue
                if response.get("id") == request_id:
                    return response

    def close(self, graceful: bool = True) -> None:
        if self.process.poll() is None:
            if graceful:
                try:
                    self.request("shutdown")
                except Exception:
                    pass
            try:
                self.process.terminate()
            except Exception:
                pass
            try:
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

    def _start_process(self) -> subprocess.Popen:
        command = freecad_worker_command(self.settings, self._worker_script())
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write("Command:\n" + subprocess.list2cmdline(command) + "\n")
            if self.settings.freecad_gui_executable and not self.settings.freecad_python:
                handle.write(
                    "Warning: launched through TEXT23D_FREECAD_GUI_EXECUTABLE. "
                    "On Windows, the persistent worker protocol is more reliable "
                    "with TEXT23D_FREECAD_PYTHON pointing to FreeCAD's bundled "
                    "python.exe.\n"
                )
            handle.write("\n")
        return subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def _start_reader_threads(self) -> None:
        assert self.process.stdout is not None
        assert self.process.stderr is not None
        threading.Thread(
            target=self._read_stdout,
            args=(self.process.stdout,),
            daemon=True,
        ).start()
        threading.Thread(
            target=self._read_stderr,
            args=(self.process.stderr,),
            daemon=True,
        ).start()

    def _read_stdout(self, stream) -> None:
        for line in stream:
            line = line.strip()
            if line:
                self._stdout_queue.put(line)

    def _read_stderr(self, stream) -> None:
        for line in stream:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def _worker_script(self) -> Path:
        if self.settings.freecad_worker_script:
            return self.settings.freecad_worker_script
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "freecad-runner" / "freecad_worker.py"


class FreeCADSessionManager:
    def __init__(
        self,
        settings: Settings,
        runner: CadRunner,
        worker_client_factory: Callable[[Path], Any] | None = None,
    ):
        self.settings = settings
        self.runner = runner
        self.worker_client_factory = worker_client_factory
        self._replay_sessions: dict[str, ReplayFreeCADSession] = {}
        self._worker_sessions: dict[str, WorkerFreeCADSession] = {}

    def start_session(
        self,
        generation_id: str,
        conversation_id: str,
        session_dir: Path,
    ) -> FreeCADSession:
        self.cleanup_idle_sessions()
        if self.settings.freecad_agent_backend == "replay":
            self.close_session(generation_id, conversation_id)
            session = ReplayFreeCADSession(
                settings=self.settings,
                runner=self.runner,
                generation_id=generation_id,
                conversation_id=conversation_id,
                session_dir=session_dir,
            )
            self._replay_sessions[generation_id] = session
            return session

        session = self._worker_sessions.get(conversation_id)
        if session is None:
            log_path = (
                self.settings.storage_dir
                / "conversations"
                / conversation_id
                / "freecad-worker.log"
            )
            client = (
                self.worker_client_factory(log_path)
                if self.worker_client_factory
                else FreeCADWorkerClient(self.settings, log_path)
            )
            session = WorkerFreeCADSession(
                settings=self.settings,
                client=client,
                conversation_id=conversation_id,
                generation_id=generation_id,
                session_dir=session_dir,
            )
            self._worker_sessions[conversation_id] = session
            return session

        session.begin_generation(generation_id, session_dir)
        return session

    def finish_session(self, generation_id: str, conversation_id: str) -> None:
        if self.settings.freecad_agent_backend == "replay":
            self.close_session(generation_id, conversation_id)
            return
        session = self._worker_sessions.get(conversation_id)
        if session:
            if getattr(session, "failed", False):
                self.close_session(conversation_id=conversation_id)
            else:
                session.touch()

    def close_session(
        self,
        generation_id: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        if generation_id:
            session = self._replay_sessions.pop(generation_id, None)
            if session:
                session.close()
        if conversation_id:
            session = self._worker_sessions.pop(conversation_id, None)
            if session:
                session.close()

    def cleanup_idle_sessions(self) -> None:
        now = time.monotonic()
        expired = [
            conversation_id
            for conversation_id, session in self._worker_sessions.items()
            if now - session.last_used_at > self.settings.freecad_session_idle_timeout_seconds
        ]
        for conversation_id in expired:
            self.close_session(conversation_id=conversation_id)


class WorkerFreeCADSession(FreeCADSession):
    def __init__(
        self,
        settings: Settings,
        client: Any,
        conversation_id: str,
        generation_id: str,
        session_dir: Path,
    ):
        self.settings = settings
        self.client = client
        self.conversation_id = conversation_id
        self.generation_id = generation_id
        self.session_dir = session_dir
        self.tool_call_count = 0
        self.view_count = 0
        self.last_result: RunnerResult | None = None
        self.last_script_path: Path | None = None
        self.last_objects: list[dict[str, Any]] = []
        self.last_used_at = time.monotonic()
        self.document_name = "Text23DGeneratedModel"
        self.failed = False
        self.tool_log_path = self.session_dir / "worker-tool-calls.log"
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def begin_generation(self, generation_id: str, session_dir: Path) -> None:
        self.generation_id = generation_id
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.tool_log_path = self.session_dir / "worker-tool-calls.log"
        self.last_result = None
        self.last_script_path = None
        self.touch()

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> FreeCADToolResult:
        self.touch()
        self.tool_call_count += 1
        self._append_log(f"TOOL {name}\n{json.dumps(arguments, indent=2)}")

        if name == "execute_code":
            code = str(arguments.get("code", ""))
            validation = self._validate_code(code)
            if validation:
                return validation
            response = self._request(name, {"code": code})
        elif name == "get_view":
            self.view_count += 1
            if self.settings.freecad_worker_view_backend == "summary":
                return self._summary_view()
            view_path = self.session_dir / f"view_{self.view_count:02d}.png"
            response = self._request(name, {"output_path": str(view_path)})
        elif name == "export_model":
            output_dir = self.session_dir / "final"
            response = self._request(name, {"output_dir": str(output_dir)})
        else:
            response = self._request(name, arguments)

        result = self._tool_result_from_response(response)
        if result.ok:
            self._accept_success(name, result)
        return result

    def close(self) -> None:
        self._close_client(graceful=not self.failed)

    def touch(self) -> None:
        self.last_used_at = time.monotonic()

    def _request(self, command: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.request(command, args)
        except Exception as exc:
            self.failed = True
            self._append_log(f"ERROR {command}\n{exc}")
            return {
                "ok": False,
                "content": {
                    "error": str(exc),
                    "fatal": True,
                    "log_path": str(self.tool_log_path),
                },
            }
        self._append_log(f"RESULT\n{json.dumps(response, indent=2)}")
        return response

    def _close_client(self, graceful: bool) -> None:
        try:
            self.client.close(graceful=graceful)
        except TypeError:
            self.client.close()

    def _tool_result_from_response(self, response: dict[str, Any]) -> FreeCADToolResult:
        return FreeCADToolResult(
            ok=bool(response.get("ok")),
            content=response.get("content") or {},
            asset_path=Path(response["asset_path"]) if response.get("asset_path") else None,
        )

    def _accept_success(self, name: str, result: FreeCADToolResult) -> None:
        document = result.content.get("document")
        if isinstance(document, str) and document:
            self.document_name = document
        objects = result.content.get("objects")
        if isinstance(objects, list):
            self.last_objects = [item for item in objects if isinstance(item, dict)]
        if name != "export_model":
            return

        artifacts = result.content.get("artifacts") or {}
        self.last_script_path = (
            Path(result.content["script_path"])
            if result.content.get("script_path")
            else None
        )
        self.last_result = RunnerResult(
            success=True,
            step_path=Path(artifacts["step"]) if artifacts.get("step") else None,
            glb_path=Path(artifacts["glb"]) if artifacts.get("glb") else None,
            stl_path=Path(artifacts["stl"]) if artifacts.get("stl") else None,
            native_path=Path(artifacts["native"]) if artifacts.get("native") else None,
            log_path=self.tool_log_path,
            stdout="",
            stderr="",
        )

    def _validate_code(self, code: str) -> FreeCADToolResult | None:
        if not code.strip():
            return FreeCADToolResult(ok=False, content={"error": "Code is empty."})
        if len(code) > self.settings.agent_max_code_chars:
            return FreeCADToolResult(
                ok=False,
                content={
                    "error": (
                        "Code block exceeds "
                        f"{self.settings.agent_max_code_chars} characters."
                    )
                },
            )
        try:
            validate_cadquery_code(_compose_snippet_validation_script(code), "freecad")
        except CodeValidationError as exc:
            return FreeCADToolResult(
                ok=False,
                content={"error": f"Validation failed: {exc}"},
            )
        return None

    def _summary_view(self) -> FreeCADToolResult:
        view_path = self.session_dir / f"view_{self.view_count:02d}.svg"
        view_path.write_text(
            _render_view_svg(self.document_name, self.last_objects),
            encoding="utf-8",
        )
        result = FreeCADToolResult(
            ok=True,
            asset_path=view_path,
            content={
                "message": (
                    "Captured a stable SVG view summary. Set "
                    "TEXT23D_FREECAD_WORKER_VIEW_BACKEND=gui to try native "
                    "FreeCAD viewport PNG screenshots."
                ),
                "image_path": str(view_path),
                "objects": self.last_objects,
                "view_backend": "summary",
            },
        )
        self._append_log(
            "RESULT\n"
            + json.dumps(
                {
                    "ok": result.ok,
                    "content": result.content,
                    "asset_path": str(result.asset_path),
                },
                indent=2,
            )
        )
        return result

    def _append_log(self, text: str) -> None:
        with self.tool_log_path.open("a", encoding="utf-8") as handle:
            handle.write(text.rstrip())
            handle.write("\n\n")


class ReplayFreeCADSession(FreeCADSession):
    def __init__(
        self,
        settings: Settings,
        runner: CadRunner,
        generation_id: str,
        conversation_id: str,
        session_dir: Path,
    ):
        self.settings = settings
        self.runner = runner
        self.generation_id = generation_id
        self.conversation_id = conversation_id
        self.session_dir = session_dir
        self.document_name = "Text23DGeneratedModel"
        self.snippets: list[str] = []
        self.tool_call_count = 0
        self.view_count = 0
        self.last_result: RunnerResult | None = None
        self.last_script_path: Path | None = None
        self.last_objects: list[dict[str, Any]] = []
        self.tool_log_path = self.session_dir / "tool-calls.log"
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def begin_generation(self, generation_id: str, session_dir: Path) -> None:
        self.generation_id = generation_id
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.tool_log_path = self.session_dir / "tool-calls.log"

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> FreeCADToolResult:
        self._append_log(f"TOOL {name}\n{json.dumps(arguments, indent=2)}")
        if name == "create_document":
            return self.create_document(arguments.get("name"))
        if name == "execute_code":
            return self.execute_code(str(arguments.get("code", "")))
        if name == "get_objects":
            return self.get_objects()
        if name == "get_object":
            return self.get_object(str(arguments.get("name", "")))
        if name == "get_view":
            return self.get_view()
        if name == "export_model":
            return self.export_model()
        return FreeCADToolResult(
            ok=False,
            content={"error": f"Unsupported FreeCAD tool: {name}"},
        )

    def close(self) -> None:
        return

    def create_document(self, name: str | None = None) -> FreeCADToolResult:
        self.document_name = _safe_document_name(name or "Text23DGeneratedModel")
        self.snippets.clear()
        self.last_result = None
        self.last_script_path = None
        self.last_objects = []
        return FreeCADToolResult(
            ok=True,
            content={
                "document": self.document_name,
                "message": "Created a fresh FreeCAD document for this generation.",
            },
        )

    def execute_code(self, code: str) -> FreeCADToolResult:
        if not code.strip():
            return FreeCADToolResult(ok=False, content={"error": "Code is empty."})
        if len(code) > self.settings.agent_max_code_chars:
            return FreeCADToolResult(
                ok=False,
                content={
                    "error": (
                        "Code block exceeds "
                        f"{self.settings.agent_max_code_chars} characters."
                    )
                },
            )

        self.snippets.append(code)
        try:
            result = self._run_current_script()
        except CodeValidationError as exc:
            self.snippets.pop()
            return FreeCADToolResult(
                ok=False,
                content={"error": f"Validation failed: {exc}"},
            )

        if not result.success:
            self.snippets.pop()
            self.last_result = result
            return FreeCADToolResult(
                ok=False,
                content={
                    "error": result.error or "FreeCAD execution failed.",
                    "stdout": result.stdout[-2000:],
                    "stderr": result.stderr[-4000:],
                    "log_path": str(result.log_path),
                },
            )

        self.last_result = result
        self.last_objects = self._read_objects(result.log_path.parent)
        return FreeCADToolResult(
            ok=True,
            content={
                "message": "Code executed and the FreeCAD document was exported.",
                "object_count": len(self.last_objects),
                "objects": self.last_objects,
                "artifacts": _result_artifacts(result),
            },
        )

    def get_objects(self) -> FreeCADToolResult:
        return FreeCADToolResult(
            ok=True,
            content={
                "object_count": len(self.last_objects),
                "objects": self.last_objects,
            },
        )

    def get_object(self, name: str) -> FreeCADToolResult:
        target = name.strip().lower()
        for obj in self.last_objects:
            names = {
                str(obj.get("name", "")).lower(),
                str(obj.get("label", "")).lower(),
            }
            if target in names:
                return FreeCADToolResult(ok=True, content={"object": obj})
        return FreeCADToolResult(
            ok=False,
            content={"error": f"Object not found: {name}"},
        )

    def get_view(self) -> FreeCADToolResult:
        self.view_count += 1
        view_path = self.session_dir / f"view_{self.view_count:02d}.svg"
        view_path.write_text(self._render_view_svg(), encoding="utf-8")
        return FreeCADToolResult(
            ok=True,
            asset_path=view_path,
            content={
                "message": (
                    "A textual SVG view summary was captured. "
                    "Use the exported STL/STEP for geometric verification."
                ),
                "image_path": str(view_path),
                "objects": self.last_objects,
            },
        )

    def export_model(self) -> FreeCADToolResult:
        if self.last_result is None:
            if not self.snippets:
                return FreeCADToolResult(
                    ok=False,
                    content={"error": "No FreeCAD geometry has been created yet."},
                )
            result = self._run_current_script()
            self.last_result = result
            self.last_objects = self._read_objects(result.log_path.parent)

        if not self.last_result.success:
            return FreeCADToolResult(
                ok=False,
                content={
                    "error": self.last_result.error or "The latest export failed.",
                    "stderr": self.last_result.stderr[-4000:],
                },
            )

        return FreeCADToolResult(
            ok=True,
            content={
                "message": "Final FreeCAD artifacts are ready.",
                "objects": self.last_objects,
                "artifacts": _result_artifacts(self.last_result),
                "script_path": str(self.last_script_path) if self.last_script_path else None,
                "log_path": str(self.tool_log_path),
            },
        )

    def _run_current_script(self) -> RunnerResult:
        self.tool_call_count += 1
        output_dir = self.session_dir / f"tool_{self.tool_call_count:02d}"
        output_dir.mkdir(parents=True, exist_ok=True)
        script_path = output_dir / "model.py"
        code = self._compose_script()
        validate_cadquery_code(code, "freecad")
        script_path.write_text(code, encoding="utf-8")
        self.last_script_path = script_path
        result = self.runner.run(script_path, output_dir)
        self._append_log(
            "\n".join(
                [
                    f"RESULT success={result.success}",
                    f"error={result.error}",
                    f"stdout={result.stdout[-2000:]}",
                    f"stderr={result.stderr[-4000:]}",
                ]
            )
        )
        return result

    def _compose_script(self) -> str:
        blocks = [
            "import FreeCAD as App",
            "import Part",
            "import Mesh",
            "",
            "",
            "def build_model(doc):",
        ]
        if not self.snippets:
            blocks.append("    return []")
            return "\n".join(blocks) + "\n"

        for index, snippet in enumerate(self.snippets, start=1):
            blocks.append(f"    # Agent snippet {index}")
            blocks.append(textwrap.indent(snippet.strip(), "    "))
            blocks.append("    doc.recompute()")
            blocks.append("")
        blocks.extend(
            [
                "    return [",
                "        obj",
                "        for obj in doc.Objects",
                "        if hasattr(obj, 'Shape')",
                "        and not getattr(obj.Shape, 'isNull', lambda: True)()",
                "    ]",
                "",
            ]
        )
        return "\n".join(blocks)

    def _read_objects(self, output_dir: Path) -> list[dict[str, Any]]:
        manifest = output_dir / "objects.json"
        if not manifest.exists():
            return []
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    def _render_view_svg(self) -> str:
        return _render_view_svg(self.document_name, self.last_objects)

    def _append_log(self, text: str) -> None:
        with self.tool_log_path.open("a", encoding="utf-8") as handle:
            handle.write(text.rstrip())
            handle.write("\n\n")


def _compose_snippet_validation_script(code: str) -> str:
    return "\n".join(
        [
            "import FreeCAD as App",
            "import Part",
            "import Mesh",
            "",
            "",
            "def build_model(doc):",
            textwrap.indent(code.strip(), "    "),
            "    doc.recompute()",
            "    return []",
            "",
        ]
    )


def _safe_document_name(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in {"_", "-"}).strip()
    return cleaned[:64] or "Text23DGeneratedModel"


def _render_view_svg(document_name: str, objects: list[dict[str, Any]]) -> str:
    rows = objects[:8]
    object_lines = "".join(
        (
            f"<text x=\"32\" y=\"{166 + index * 28}\" "
            "class=\"row\">"
            f"{html.escape(str(obj.get('label') or obj.get('name') or 'Object'))} "
            f"<tspan class=\"muted\">{html.escape(str(obj.get('type') or ''))}</tspan>"
            "</text>"
        )
        for index, obj in enumerate(rows)
    )
    if not object_lines:
        object_lines = (
            "<text x=\"32\" y=\"166\" class=\"row\">No exported objects yet.</text>"
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
  <rect width="960" height="540" fill="#11151d"/>
  <rect x="24" y="24" width="912" height="492" rx="8" fill="#1b212b" stroke="#343d4c"/>
  <text x="32" y="70" class="title">FreeCAD session view</text>
  <text x="32" y="106" class="meta">Document: {html.escape(document_name)}</text>
  <text x="32" y="134" class="meta">Objects: {len(objects)}</text>
  {object_lines}
  <style>
    .title {{ fill: #f4f7fb; font: 700 30px Arial, sans-serif; }}
    .meta {{ fill: #aab4c3; font: 18px Arial, sans-serif; }}
    .row {{ fill: #f4f7fb; font: 19px Arial, sans-serif; }}
    .muted {{ fill: #7f8998; font-size: 15px; }}
  </style>
</svg>
"""


def _result_artifacts(result: RunnerResult) -> dict[str, str | None]:
    return {
        "step": str(result.step_path) if result.step_path else None,
        "glb": str(result.glb_path) if result.glb_path else None,
        "stl": str(result.stl_path) if result.stl_path else None,
        "native": str(result.native_path) if result.native_path else None,
        "runner_log": str(result.log_path) if result.log_path else None,
    }

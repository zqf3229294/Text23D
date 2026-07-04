import asyncio
import json
import sys
import types
from pathlib import Path

from app.agent import CADAgent
from app.config import Settings
from app.db import SQLiteRepository
from app.freecad_agent import FreeCADSessionManager, freecad_worker_command
from app.models import GenerationStatus, MessageRole
from app.providers.mock import MockLLMProvider
from app.runner import RunnerResult
from app.service import GenerationService


class FakeWorkerClient:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.requests = []
        self.objects = [
            {
                "name": "CubeWithThroughHole",
                "label": "Cube with 10 mm through-hole",
                "type": "Part::Cut",
                "visible": True,
            }
        ]

    def request(self, command: str, args: dict | None = None):
        args = args or {}
        self.requests.append((command, args))
        if command == "create_document":
            return {
                "ok": True,
                "content": {"document": args.get("name") or "Text23D"},
            }
        if command == "execute_code":
            return {
                "ok": True,
                "content": {
                    "message": "executed",
                    "objects": self.objects,
                    "object_count": len(self.objects),
                },
            }
        if command == "get_objects":
            return {
                "ok": True,
                "content": {"objects": self.objects, "object_count": len(self.objects)},
            }
        if command == "get_view":
            view_path = Path(args["output_path"])
            view_path.parent.mkdir(parents=True, exist_ok=True)
            view_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            return {
                "ok": True,
                "asset_path": str(view_path),
                "content": {"image_path": str(view_path), "objects": self.objects},
            }
        if command == "export_preview_mesh":
            mesh_path = Path(args["output_path"])
            mesh_path.parent.mkdir(parents=True, exist_ok=True)
            mesh_path.write_text("solid preview\nendsolid preview\n", encoding="utf-8")
            return {
                "ok": True,
                "content": {
                    "message": "mesh exported",
                    "mesh_path": str(mesh_path),
                    "objects": self.objects,
                },
            }
        if command == "export_model":
            output_dir = Path(args["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            step_path = output_dir / "model.step"
            stl_path = output_dir / "preview.stl"
            native_path = output_dir / "model.FCStd"
            script_path = output_dir / "live_session.py"
            step_path.write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")
            stl_path.write_text("solid preview\nendsolid preview\n", encoding="utf-8")
            native_path.write_bytes(b"fcstd")
            script_path.write_text("# live session", encoding="utf-8")
            return {
                "ok": True,
                "content": {
                    "message": "exported",
                    "objects": self.objects,
                    "script_path": str(script_path),
                    "artifacts": {
                        "step": str(step_path),
                        "stl": str(stl_path),
                        "native": str(native_path),
                        "glb": None,
                        "script": str(script_path),
                    },
                },
            }
        return {"ok": False, "content": {"error": f"unknown command {command}"}}

    def close(self):
        return


class DeadWorkerClient:
    def __init__(self, log_path: Path):
        self.log_path = log_path

    def request(self, command: str, args: dict | None = None):
        raise TimeoutError(f"FreeCAD worker command timed out: {command}")

    def close(self):
        return


class TimeoutAfterCheckpointWorkerClient(FakeWorkerClient):
    def __init__(self, log_path: Path):
        super().__init__(log_path)
        self.execute_code_calls = 0

    def request(self, command: str, args: dict | None = None):
        if command == "execute_code":
            self.execute_code_calls += 1
            if self.execute_code_calls > 1:
                raise TimeoutError("FreeCAD worker command timed out: execute_code")
        return super().request(command, args)


class FakeFreeCADRunner:
    def run(self, script_path: Path, output_dir: Path) -> RunnerResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "run.log"
        step_path = output_dir / "model.step"
        stl_path = output_dir / "preview.stl"
        native_path = output_dir / "model.FCStd"
        objects_path = output_dir / "objects.json"

        log_path.write_text("fake freecad runner log", encoding="utf-8")
        step_path.write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")
        stl_path.write_text("solid preview\nendsolid preview\n", encoding="utf-8")
        native_path.write_bytes(b"fcstd")
        objects_path.write_text(
            json.dumps(
                [
                    {
                        "name": "CubeWithThroughHole",
                        "label": "Cube with 10 mm through-hole",
                        "type": "Part::Cut",
                    }
                ]
            ),
            encoding="utf-8",
        )
        return RunnerResult(
            success=True,
            step_path=step_path,
            glb_path=None,
            stl_path=stl_path,
            native_path=native_path,
            log_path=log_path,
            stdout="ok",
        )


def test_mock_freecad_agent_exports_artifacts_and_events(tmp_path):
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        cad_kernel="freecad",
        generation_mode="agent",
        freecad_agent_backend="worker",
        llm_provider="mock",
    )
    repository = SQLiteRepository(settings.database_path)
    runner = FakeFreeCADRunner()
    clients = []

    def client_factory(log_path: Path):
        client = FakeWorkerClient(log_path)
        clients.append(client)
        return client

    agent = CADAgent(
        settings,
        repository,
        FreeCADSessionManager(settings, runner, worker_client_factory=client_factory),
    )
    service = GenerationService(
        settings,
        repository,
        MockLLMProvider(),
        runner,
        agent,
    )

    conversation = repository.create_conversation()
    repository.create_message(
        conversation["id"],
        MessageRole.user,
        "make a 40 mm cube with a 10 mm through-hole",
    )
    generation = repository.create_generation(
        conversation["id"],
        "make a 40 mm cube with a 10 mm through-hole",
    )

    asyncio.run(service.run_generation(generation["id"]))

    updated = repository.get_generation(generation["id"])
    assert updated["status"] == GenerationStatus.succeeded.value
    assert updated["step_path"] and Path(updated["step_path"]).exists()
    assert updated["stl_path"] and Path(updated["stl_path"]).exists()
    assert updated["native_path"] and Path(updated["native_path"]).exists()
    assert updated["script_path"] and Path(updated["script_path"]).exists()
    assert updated["log_path"] and Path(updated["log_path"]).exists()

    events = repository.list_generation_events(generation["id"])
    event_types = [event["event_type"] for event in events]
    status_messages = [
        event["message"] for event in events if event["event_type"] == "status"
    ]
    assert "tool_call" in event_types
    assert "screenshot" in event_types
    assert "artifact" in event_types
    assert any("Agent iteration 1:" in message for message in status_messages)

    screenshot = next(event for event in events if event["event_type"] == "screenshot")
    assert screenshot["asset_path"] and Path(screenshot["asset_path"]).exists()
    assert Path(screenshot["asset_path"]).suffix == ".svg"
    assert len(clients) == 1
    assert all(command != "get_view" for command, _args in clients[0].requests)

    messages = repository.list_messages(conversation["id"])
    assert messages[-1]["role"] == MessageRole.assistant.value


def test_worker_session_is_reused_for_same_conversation(tmp_path):
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        cad_kernel="freecad",
        generation_mode="agent",
        freecad_agent_backend="worker",
        llm_provider="mock",
    )
    repository = SQLiteRepository(settings.database_path)
    runner = FakeFreeCADRunner()
    clients = []

    def client_factory(log_path: Path):
        client = FakeWorkerClient(log_path)
        clients.append(client)
        return client

    manager = FreeCADSessionManager(settings, runner, worker_client_factory=client_factory)
    agent = CADAgent(settings, repository, manager)
    service = GenerationService(settings, repository, MockLLMProvider(), runner, agent)
    conversation = repository.create_conversation()

    for prompt in ["make a cube with a hole", "make the hole larger"]:
        repository.create_message(conversation["id"], MessageRole.user, prompt)
        generation = repository.create_generation(conversation["id"], prompt)
        asyncio.run(service.run_generation(generation["id"]))

    assert len(clients) == 1


def test_worker_gui_view_backend_calls_worker_get_view(tmp_path):
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        cad_kernel="freecad",
        generation_mode="agent",
        freecad_agent_backend="worker",
        freecad_worker_view_backend="gui",
        llm_provider="mock",
    )
    repository = SQLiteRepository(settings.database_path)
    runner = FakeFreeCADRunner()
    clients = []

    def client_factory(log_path: Path):
        client = FakeWorkerClient(log_path)
        clients.append(client)
        return client

    agent = CADAgent(
        settings,
        repository,
        FreeCADSessionManager(settings, runner, worker_client_factory=client_factory),
    )
    service = GenerationService(settings, repository, MockLLMProvider(), runner, agent)
    conversation = repository.create_conversation()
    repository.create_message(conversation["id"], MessageRole.user, "make a cube")
    generation = repository.create_generation(conversation["id"], "make a cube")

    asyncio.run(service.run_generation(generation["id"]))

    events = repository.list_generation_events(generation["id"])
    screenshot = next(event for event in events if event["event_type"] == "screenshot")
    assert Path(screenshot["asset_path"]).suffix == ".png"
    assert any(command == "get_view" for command, _args in clients[0].requests)


def test_worker_pyvista_view_backend_exports_mesh_and_renders_png(tmp_path, monkeypatch):
    from app import pyvista_renderer

    def fake_render(mesh_path: Path, output_path: Path, **_kwargs):
        assert mesh_path.exists()
        output_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        return {
            "mesh_path": str(mesh_path),
            "image_path": str(output_path),
            "point_count": 8,
            "cell_count": 12,
            "views": ["ISO", "TOP", "FRONT", "RIGHT"],
        }

    monkeypatch.setattr(pyvista_renderer, "render_stl_preview", fake_render)
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        cad_kernel="freecad",
        generation_mode="agent",
        freecad_agent_backend="worker",
        freecad_worker_view_backend="pyvista",
        llm_provider="mock",
    )
    repository = SQLiteRepository(settings.database_path)
    runner = FakeFreeCADRunner()
    clients = []

    def client_factory(log_path: Path):
        client = FakeWorkerClient(log_path)
        clients.append(client)
        return client

    agent = CADAgent(
        settings,
        repository,
        FreeCADSessionManager(settings, runner, worker_client_factory=client_factory),
    )
    service = GenerationService(settings, repository, MockLLMProvider(), runner, agent)
    conversation = repository.create_conversation()
    repository.create_message(conversation["id"], MessageRole.user, "make a cube")
    generation = repository.create_generation(conversation["id"], "make a cube")

    asyncio.run(service.run_generation(generation["id"]))

    events = repository.list_generation_events(generation["id"])
    screenshot = next(event for event in events if event["event_type"] == "screenshot")
    assert Path(screenshot["asset_path"]).suffix == ".png"
    assert json.loads(screenshot["data_json"])["view_backend"] == "pyvista"
    assert any(command == "export_preview_mesh" for command, _args in clients[0].requests)
    assert all(command != "get_view" for command, _args in clients[0].requests)


def test_replay_freecad_agent_backend_still_exports_artifacts(tmp_path):
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        cad_kernel="freecad",
        generation_mode="agent",
        freecad_agent_backend="replay",
        llm_provider="mock",
    )
    repository = SQLiteRepository(settings.database_path)
    runner = FakeFreeCADRunner()
    agent = CADAgent(settings, repository, FreeCADSessionManager(settings, runner))
    service = GenerationService(settings, repository, MockLLMProvider(), runner, agent)
    conversation = repository.create_conversation()
    repository.create_message(conversation["id"], MessageRole.user, "make a cube with a hole")
    generation = repository.create_generation(conversation["id"], "make a cube with a hole")

    asyncio.run(service.run_generation(generation["id"]))

    updated = repository.get_generation(generation["id"])
    assert updated["status"] == GenerationStatus.succeeded.value
    assert updated["step_path"] and Path(updated["step_path"]).exists()


def test_worker_command_prefers_freecad_python_over_gui_executable(tmp_path):
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        freecad_python=r"C:\Program Files\FreeCAD 1.1\bin\python.exe",
        freecad_gui_executable=r"C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe",
    )

    command = freecad_worker_command(settings, tmp_path / "freecad_worker.py")

    assert command[0] == r"C:\Program Files\FreeCAD 1.1\bin\python.exe"


def test_anthropic_agent_stops_on_fatal_worker_error(tmp_path, monkeypatch):
    calls = {"count": 0}

    class FakeMessages:
        async def create(self, **kwargs):
            calls["count"] += 1
            return types.SimpleNamespace(
                content=[
                    types.SimpleNamespace(
                        type="tool_use",
                        id="toolu_create_document",
                        name="create_document",
                        input={"name": "Text23D"},
                    )
                ]
            )

    class FakeAsyncAnthropic:
        def __init__(self, api_key: str):
            self.messages = FakeMessages()

    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        types.SimpleNamespace(AsyncAnthropic=FakeAsyncAnthropic),
    )
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        cad_kernel="freecad",
        generation_mode="agent",
        freecad_agent_backend="worker",
        llm_provider="anthropic",
        anthropic_api_key="test-key",
        agent_max_runtime_seconds=30,
    )
    repository = SQLiteRepository(settings.database_path)
    runner = FakeFreeCADRunner()
    agent = CADAgent(
        settings,
        repository,
        FreeCADSessionManager(
            settings,
            runner,
            worker_client_factory=lambda log_path: DeadWorkerClient(log_path),
        ),
    )
    conversation = repository.create_conversation()
    generation = repository.create_generation(conversation["id"], "make a cube")

    result = asyncio.run(
        agent.run(
            generation,
            [{"role": "user", "content": "make a cube"}],
            tmp_path / "generation",
        )
    )

    assert not result.success
    assert result.assistant_summary == "The FreeCAD worker stopped responding."
    assert "timed out" in (result.error or "")
    assert calls["count"] == 1


def test_anthropic_agent_uses_checkpoint_after_later_worker_timeout(
    tmp_path,
    monkeypatch,
):
    calls = {"count": 0}

    class FakeMessages:
        async def create(self, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return types.SimpleNamespace(
                    content=[
                        types.SimpleNamespace(
                            type="tool_use",
                            id="toolu_create_document",
                            name="create_document",
                            input={"name": "Text23D"},
                        ),
                        types.SimpleNamespace(
                            type="tool_use",
                            id="toolu_execute_initial",
                            name="execute_code",
                            input={"code": "box = doc.addObject('Part::Box', 'Box')"},
                        ),
                    ]
                )
            return types.SimpleNamespace(
                content=[
                        types.SimpleNamespace(
                            type="tool_use",
                            id="toolu_execute_timeout",
                            name="execute_code",
                            input={"code": "box = doc.addObject('Part::Box', 'Box2')"},
                        )
                ]
            )

    class FakeAsyncAnthropic:
        def __init__(self, api_key: str):
            self.messages = FakeMessages()

    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        types.SimpleNamespace(AsyncAnthropic=FakeAsyncAnthropic),
    )
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        cad_kernel="freecad",
        generation_mode="agent",
        freecad_agent_backend="worker",
        llm_provider="anthropic",
        anthropic_api_key="test-key",
        agent_max_runtime_seconds=30,
    )
    repository = SQLiteRepository(settings.database_path)
    runner = FakeFreeCADRunner()
    clients = []

    def client_factory(log_path: Path):
        client = TimeoutAfterCheckpointWorkerClient(log_path)
        clients.append(client)
        return client

    agent = CADAgent(
        settings,
        repository,
        FreeCADSessionManager(settings, runner, worker_client_factory=client_factory),
    )
    conversation = repository.create_conversation()
    generation = repository.create_generation(conversation["id"], "make a bracket")

    result = asyncio.run(
        agent.run(
            generation,
            [{"role": "user", "content": "make a bracket"}],
            tmp_path / "generation",
        )
    )

    assert result.success
    assert result.step_path and result.step_path.exists()
    assert result.native_path and result.native_path.exists()
    assert calls["count"] == 2
    assert [
        command for command, _args in clients[0].requests if command == "export_model"
    ] == ["export_model"]
    events = repository.list_generation_events(generation["id"])
    assert any(
        event["message"] == "Saved a successful FreeCAD checkpoint."
        for event in events
    )
    assert any(
        "Using the latest successful checkpoint" in event["message"]
        for event in events
    )


def test_anthropic_agent_does_not_export_twice_after_tool_export(tmp_path, monkeypatch):
    calls = {"count": 0}

    class FakeMessages:
        async def create(self, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return types.SimpleNamespace(
                    content=[
                        types.SimpleNamespace(
                            type="tool_use",
                            id="toolu_export_model",
                            name="export_model",
                            input={},
                        )
                    ]
                )
            return types.SimpleNamespace(
                content=[
                    types.SimpleNamespace(
                        type="text",
                        text="The model has been exported successfully.",
                    )
                ]
            )

    class FakeAsyncAnthropic:
        def __init__(self, api_key: str):
            self.messages = FakeMessages()

    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        types.SimpleNamespace(AsyncAnthropic=FakeAsyncAnthropic),
    )
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        cad_kernel="freecad",
        generation_mode="agent",
        freecad_agent_backend="worker",
        llm_provider="anthropic",
        anthropic_api_key="test-key",
    )
    repository = SQLiteRepository(settings.database_path)
    runner = FakeFreeCADRunner()
    clients = []

    def client_factory(log_path: Path):
        client = FakeWorkerClient(log_path)
        clients.append(client)
        return client

    agent = CADAgent(
        settings,
        repository,
        FreeCADSessionManager(settings, runner, worker_client_factory=client_factory),
    )
    conversation = repository.create_conversation()
    generation = repository.create_generation(conversation["id"], "make a cube")

    result = asyncio.run(
        agent.run(
            generation,
            [{"role": "user", "content": "make a cube"}],
            tmp_path / "generation",
        )
    )

    assert result.success
    events = repository.list_generation_events(generation["id"])
    status_messages = [
        event["message"] for event in events if event["event_type"] == "status"
    ]
    assert any("Agent iteration 1:" in message for message in status_messages)
    assert any("Agent iteration 2:" in message for message in status_messages)
    assert calls["count"] == 2
    assert [
        command
        for command, _args in clients[0].requests
        if command == "export_model"
    ] == ["export_model"]


def test_anthropic_agent_sends_get_view_png_as_tool_result_image(tmp_path, monkeypatch):
    calls = {"count": 0}
    captured_messages = []

    class FakeMessages:
        async def create(self, **kwargs):
            calls["count"] += 1
            captured_messages.append(kwargs["messages"])
            if calls["count"] == 1:
                return types.SimpleNamespace(
                    content=[
                        types.SimpleNamespace(
                            type="tool_use",
                            id="toolu_get_view",
                            name="get_view",
                            input={},
                        )
                    ]
                )
            return types.SimpleNamespace(
                content=[
                    types.SimpleNamespace(
                        type="text",
                        text="The screenshot looks correct.",
                    )
                ]
            )

    class FakeAsyncAnthropic:
        def __init__(self, api_key: str):
            self.messages = FakeMessages()

    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        types.SimpleNamespace(AsyncAnthropic=FakeAsyncAnthropic),
    )
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        cad_kernel="freecad",
        generation_mode="agent",
        freecad_agent_backend="worker",
        freecad_worker_view_backend="gui",
        llm_provider="anthropic",
        anthropic_api_key="test-key",
    )
    repository = SQLiteRepository(settings.database_path)
    runner = FakeFreeCADRunner()
    agent = CADAgent(
        settings,
        repository,
        FreeCADSessionManager(
            settings,
            runner,
            worker_client_factory=lambda log_path: FakeWorkerClient(log_path),
        ),
    )
    conversation = repository.create_conversation()
    generation = repository.create_generation(conversation["id"], "inspect the model")

    result = asyncio.run(
        agent.run(
            generation,
            [{"role": "user", "content": "inspect the model"}],
            tmp_path / "generation",
        )
    )

    assert result.success
    assert calls["count"] == 2
    tool_result = captured_messages[1][-1]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert isinstance(tool_result["content"], list)
    assert tool_result["content"][0]["type"] == "image"
    assert tool_result["content"][0]["source"]["media_type"] == "image/png"
    assert tool_result["content"][0]["source"]["data"]
    assert tool_result["content"][1]["type"] == "text"
    assert "FreeCAD tool result metadata" in tool_result["content"][1]["text"]

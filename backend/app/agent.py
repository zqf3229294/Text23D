from __future__ import annotations

import asyncio
import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .db import SQLiteRepository
from .freecad_agent import FreeCADSession, FreeCADSessionManager, FreeCADToolResult
from .models import GenerationEventType
from .providers.multimodal import anthropic_content_blocks, message_text


@dataclass
class AgentRunResult:
    success: bool
    assistant_summary: str
    script_path: Path | None = None
    step_path: Path | None = None
    glb_path: Path | None = None
    stl_path: Path | None = None
    native_path: Path | None = None
    log_path: Path | None = None
    error: str | None = None
    tool_call_count: int = 0


class CADAgent:
    def __init__(
        self,
        settings: Settings,
        repository: SQLiteRepository,
        session_manager: FreeCADSessionManager,
    ):
        self.settings = settings
        self.repository = repository
        self.session_manager = session_manager

    async def run(
        self,
        generation: dict[str, Any],
        context: list[dict[str, Any]],
        generation_dir: Path,
    ) -> AgentRunResult:
        if self.settings.cad_kernel != "freecad":
            return AgentRunResult(
                success=False,
                assistant_summary="Agent mode requires the FreeCAD CAD kernel.",
                error="TEXT23D_GENERATION_MODE=agent requires TEXT23D_CAD_KERNEL=freecad.",
            )

        session = self.session_manager.start_session(
            generation_id=generation["id"],
            conversation_id=generation["conversation_id"],
            session_dir=generation_dir / "agent",
        )
        self._event(
            generation["id"],
            GenerationEventType.status,
            "Agent mode started. FreeCAD tools are running on the backend.",
        )

        try:
            if self.settings.llm_provider == "mock":
                return await self._run_mock(generation["id"], context, session)
            if self.settings.llm_provider == "anthropic":
                return await self._run_anthropic(generation["id"], context, session)
            message = (
                "Agent mode V1 supports TEXT23D_LLM_PROVIDER=mock for local testing "
                "or anthropic for Claude tool use. Use script mode for DeepSeek/OpenAI "
                "until their tool/image behavior is wired into this agent loop."
            )
            self._event(
                generation["id"],
                GenerationEventType.error,
                message,
            )
            return AgentRunResult(
                success=False,
                assistant_summary="The selected provider does not support agent mode yet.",
                error=message,
            )
        finally:
            self.session_manager.finish_session(
                generation["id"],
                generation["conversation_id"],
            )

    def cancel_generation(self, generation: dict[str, Any]) -> None:
        self.session_manager.abort_session(
            generation_id=generation["id"],
            conversation_id=generation["conversation_id"],
        )

    async def _run_mock(
        self,
        generation_id: str,
        context: list[dict[str, Any]],
        session: FreeCADSession,
    ) -> AgentRunResult:
        prompt = _latest_user_prompt(context)
        steps: list[tuple[str, dict[str, Any]]] = [
            ("create_document", {"name": "Text23DMockAgentModel"}),
            ("execute_code", {"code": _mock_freecad_snippet(prompt)}),
            ("get_objects", {}),
            ("get_view", {}),
            ("export_model", {}),
        ]
        final_result: FreeCADToolResult | None = None
        for iteration, (name, arguments) in enumerate(steps, start=1):
            if self._is_cancelled(generation_id):
                return AgentRunResult(
                    success=False,
                    assistant_summary="Generation cancelled.",
                    error="Generation cancelled by user.",
                    log_path=session.tool_log_path,
                    tool_call_count=session.tool_call_count,
                )
            self._event(
                generation_id,
                GenerationEventType.status,
                f"Agent iteration {iteration}: running FreeCAD tool {name}.",
                data={"iteration": iteration, "tool_name": name},
            )
            final_result = await self._execute_tool(generation_id, session, name, arguments)
            if not final_result.ok:
                return AgentRunResult(
                    success=False,
                    assistant_summary="The mock FreeCAD agent could not finish the model.",
                    error=str(final_result.content.get("error") or final_result.content),
                    log_path=session.tool_log_path,
                    tool_call_count=session.tool_call_count,
                )

        assert final_result is not None
        return self._agent_success(
            session,
            "Mock FreeCAD agent generated the model and exported final artifacts.",
        )

    async def _run_anthropic(
        self,
        generation_id: str,
        context: list[dict[str, Any]],
        session: FreeCADSession,
    ) -> AgentRunResult:
        if not self.settings.anthropic_api_key:
            return AgentRunResult(
                success=False,
                assistant_summary="Anthropic API key is not configured.",
                error="TEXT23D_ANTHROPIC_API_KEY is required for agent mode.",
                log_path=session.tool_log_path,
            )
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            return AgentRunResult(
                success=False,
                assistant_summary="Anthropic SDK is not installed.",
                error=str(exc),
                log_path=session.tool_log_path,
            )

        client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
        messages = _anthropic_context(context)
        started = time.monotonic()
        tool_calls = 0
        iteration = 0
        final_text = ""

        while True:
            if self._is_cancelled(generation_id):
                return AgentRunResult(
                    success=False,
                    assistant_summary="Generation cancelled.",
                    error="Generation cancelled by user.",
                    log_path=session.tool_log_path,
                    tool_call_count=tool_calls,
                )
            if time.monotonic() - started > self.settings.agent_max_runtime_seconds:
                return AgentRunResult(
                    success=False,
                    assistant_summary="Agent runtime limit reached.",
                    error="Agent runtime limit reached.",
                    log_path=session.tool_log_path,
                    tool_call_count=tool_calls,
                )
            if tool_calls >= self.settings.agent_max_tool_calls:
                return AgentRunResult(
                    success=False,
                    assistant_summary="Agent tool-call limit reached.",
                    error="Agent tool-call limit reached.",
                    log_path=session.tool_log_path,
                    tool_call_count=tool_calls,
                )

            iteration += 1
            self._event(
                generation_id,
                GenerationEventType.status,
                f"Agent iteration {iteration}: asking the model for the next FreeCAD action.",
                data={"iteration": iteration},
            )
            request: dict[str, Any] = {
                "model": self.settings.anthropic_model,
                "max_tokens": self.settings.llm_max_tokens,
                "system": _agent_system_prompt(self.settings.agent_max_code_chars),
                "tools": FREECAD_TOOLS,
                "messages": messages,
            }
            cache_control = _anthropic_agent_cache_control(self.settings)
            if cache_control is not None:
                request["cache_control"] = cache_control
            response = await client.messages.create(**request)
            if self._is_cancelled(generation_id):
                return AgentRunResult(
                    success=False,
                    assistant_summary="Generation cancelled.",
                    error="Generation cancelled by user.",
                    log_path=session.tool_log_path,
                    tool_call_count=tool_calls,
                )

            content_blocks = [_anthropic_block_to_dict(block) for block in response.content]
            text = "\n".join(
                block.get("text", "")
                for block in content_blocks
                if block.get("type") == "text"
            ).strip()
            if text:
                final_text = text
                self._event(
                    generation_id,
                    GenerationEventType.status,
                    text[:1000],
                )

            tool_blocks = [
                block for block in content_blocks if block.get("type") == "tool_use"
            ]
            if not tool_blocks:
                if session.last_result is not None and session.last_result.success:
                    return self._agent_success(
                        session,
                        final_text or "FreeCAD agent generated and exported the model.",
                        tool_call_count=tool_calls,
                    )
                export = await self._execute_tool(
                    generation_id,
                    session,
                    "export_model",
                    {},
                )
                if not export.ok:
                    return AgentRunResult(
                        success=False,
                        assistant_summary=final_text or "The agent stopped before export.",
                        error=str(export.content.get("error") or export.content),
                        log_path=session.tool_log_path,
                        tool_call_count=tool_calls,
                    )
                return self._agent_success(
                    session,
                    final_text or "FreeCAD agent generated and exported the model.",
                    tool_call_count=tool_calls,
                )

            messages.append({"role": "assistant", "content": content_blocks})
            tool_results = []
            for block in tool_blocks:
                if self._is_cancelled(generation_id):
                    return AgentRunResult(
                        success=False,
                        assistant_summary="Generation cancelled.",
                        error="Generation cancelled by user.",
                        log_path=session.tool_log_path,
                        tool_call_count=tool_calls,
                    )
                if tool_calls >= self.settings.agent_max_tool_calls:
                    break
                tool_calls += 1
                result = await self._execute_tool(
                    generation_id,
                    session,
                    str(block["name"]),
                    dict(block.get("input") or {}),
                )
                if not result.ok and result.content.get("fatal"):
                    error = str(result.content.get("error") or result.content)
                    if session.last_result is not None and session.last_result.success:
                        self._event(
                            generation_id,
                            GenerationEventType.error,
                            (
                                "FreeCAD worker stopped during a later refinement. "
                                "Using the latest successful checkpoint."
                            ),
                            data={"error": error, "recovered_from_checkpoint": True},
                        )
                        return self._agent_success(
                            session,
                            final_text
                            or (
                                "The FreeCAD worker stopped during a later refinement, "
                                "so I exported the latest successful checkpoint."
                            ),
                            tool_call_count=tool_calls,
                        )
                    return AgentRunResult(
                        success=False,
                        assistant_summary="The FreeCAD worker stopped responding.",
                        error=error,
                        log_path=session.tool_log_path,
                        tool_call_count=tool_calls,
                    )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "is_error": not result.ok,
                        "content": _anthropic_tool_result_content(
                            str(block["name"]),
                            result,
                        ),
                    }
                )
            messages.append({"role": "user", "content": tool_results})

    async def _execute_tool(
        self,
        generation_id: str,
        session: FreeCADSession,
        name: str,
        arguments: dict[str, Any],
    ) -> FreeCADToolResult:
        self._event(
            generation_id,
            GenerationEventType.tool_call,
            f"Calling FreeCAD tool: {name}",
            tool_name=name,
            data=_safe_event_arguments(arguments),
        )
        result = await asyncio.to_thread(session.execute_tool, name, arguments)
        event_type = (
            GenerationEventType.screenshot
            if name == "get_view" and result.ok and result.asset_path
            else GenerationEventType.tool_result
            if result.ok
            else GenerationEventType.error
        )
        self._event(
            generation_id,
            event_type,
            _tool_result_message(name, result),
            tool_name=name,
            asset_path=result.asset_path,
            data=result.content,
        )
        if name == "export_model" and result.ok:
            self._event(
                generation_id,
                GenerationEventType.artifact,
                "Final FreeCAD artifacts are available.",
                tool_name=name,
                data=result.content.get("artifacts", {}),
            )
        elif result.ok and self._should_checkpoint(name, result, session):
            await self._save_checkpoint(generation_id, session, name)
        return result

    async def _save_checkpoint(
        self,
        generation_id: str,
        session: FreeCADSession,
        source_tool: str,
    ) -> None:
        checkpoint = await asyncio.to_thread(session.execute_tool, "export_model", {})
        if not checkpoint.ok:
            self._event(
                generation_id,
                GenerationEventType.status,
                "FreeCAD checkpoint export was skipped.",
                tool_name="export_model",
                data=checkpoint.content,
            )
            return
        self._event(
            generation_id,
            GenerationEventType.status,
            "Saved a successful FreeCAD checkpoint.",
            tool_name="export_model",
            data={
                "source_tool": source_tool,
                "artifacts": checkpoint.content.get("artifacts", {}),
            },
        )

    def _should_checkpoint(
        self,
        name: str,
        result: FreeCADToolResult,
        session: FreeCADSession,
    ) -> bool:
        if name == "execute_code" and session.last_result is None:
            return _has_model_objects(result.content)
        if name == "get_view":
            return _has_model_objects(result.content)
        return False

    def _agent_success(
        self,
        session: FreeCADSession,
        summary: str,
        tool_call_count: int | None = None,
    ) -> AgentRunResult:
        result = session.last_result
        if result is None or not result.success:
            return AgentRunResult(
                success=False,
                assistant_summary=summary,
                error="Agent finished without successful FreeCAD artifacts.",
                log_path=session.tool_log_path,
                tool_call_count=tool_call_count or session.tool_call_count,
            )
        return AgentRunResult(
            success=True,
            assistant_summary=summary,
            script_path=session.last_script_path,
            step_path=result.step_path,
            glb_path=result.glb_path,
            stl_path=result.stl_path,
            native_path=result.native_path,
            log_path=session.tool_log_path,
            tool_call_count=tool_call_count or session.tool_call_count,
        )

    def _event(
        self,
        generation_id: str,
        event_type: GenerationEventType,
        message: str,
        tool_name: str | None = None,
        asset_path: Path | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.repository.create_generation_event(
            generation_id=generation_id,
            event_type=event_type.value,
            message=message,
            tool_name=tool_name,
            asset_path=str(asset_path) if asset_path else None,
            data=data or {},
        )

    def _is_cancelled(self, generation_id: str) -> bool:
        generation = self.repository.get_generation(generation_id)
        return bool(generation and generation.get("status") == "cancelled")


FREECAD_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_document",
        "description": "Create or reset the FreeCAD document for this generation.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "execute_code",
        "description": (
            "Execute a small FreeCAD Python snippet inside build_model(doc). "
            "Use the provided doc variable and App/Part/Mesh imports. Do not access files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
    },
    {
        "name": "get_objects",
        "description": "List exported FreeCAD document objects and basic bounds.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_object",
        "description": "Inspect one FreeCAD object by Name or Label.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "get_view",
        "description": (
            "Capture a server-side view of the current FreeCAD model. Depending on "
            "backend settings this may return a solid B-Rep projection PNG, a rendered "
            "mesh PNG screenshot, a native viewport PNG, or a stable SVG/text summary."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "export_model",
        "description": "Export final FCStd, STEP, and STL artifacts.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def _agent_system_prompt(max_code_chars: int) -> str:
    return f"""You are a mechanical CAD agent controlling FreeCAD on a backend server.
Build the requested model incrementally with the available tools.

Rules:
- Start with create_document unless the current document state is clearly reusable.
- Use execute_code with concise FreeCAD Python snippets that run inside build_model(doc).
- The snippet may use doc, App, Part, and Mesh. Do not read or write files.
- Give important objects descriptive labels so the FCStd feature tree is useful.
- Prefer parametric FreeCAD document objects such as Part::Box, Part::Cylinder, Part::Cut, and Part::Fuse.
- Keep each execute_code input under {max_code_chars} characters.
- Inspect progress with get_objects and get_view when useful. get_view may return
  a solid B-Rep projection image, another rendered image of the model, or a stable
  object summary depending on backend settings.
- Call export_model before you give the final answer.
- If a tool returns an error, repair with a smaller snippet.
"""


def _anthropic_agent_cache_control(settings: Settings) -> dict[str, str] | None:
    if not settings.anthropic_agent_prompt_cache:
        return None
    cache_control = {"type": "ephemeral"}
    if settings.anthropic_agent_prompt_cache_ttl == "1h":
        cache_control["ttl"] = "1h"
    return cache_control


def _anthropic_context(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    last_role: str | None = None
    for item in messages:
        role = "assistant" if item["role"] == "assistant" else "user"
        content = (
            item.get("content", "")
            if role == "assistant"
            else anthropic_content_blocks(item)
        )
        if result and role == last_role:
            result[-1]["content"] = _merge_anthropic_content(
                result[-1]["content"],
                content,
            )
        else:
            result.append({"role": role, "content": content})
            last_role = role
    return result or [{"role": "user", "content": "Create a simple FreeCAD part."}]


def _merge_anthropic_content(left, right):
    if isinstance(left, str) and isinstance(right, str):
        return f"{left}\n\n{right}"
    left_blocks = left if isinstance(left, list) else [{"type": "text", "text": left}]
    right_blocks = right if isinstance(right, list) else [{"type": "text", "text": right}]
    return [*left_blocks, *right_blocks]


def _anthropic_block_to_dict(block: Any) -> dict[str, Any]:
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True)
    if hasattr(block, "to_dict"):
        return block.to_dict()
    return {
        "type": getattr(block, "type", None),
        "text": getattr(block, "text", None),
        "id": getattr(block, "id", None),
        "name": getattr(block, "name", None),
        "input": getattr(block, "input", None),
    }


def _latest_user_prompt(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message_text(message)
    return ""


def _mock_freecad_snippet(prompt: str) -> str:
    if "hole" in prompt.lower():
        return '''side = 40.0
hole_radius = 5.0

cube = doc.addObject("Part::Box", "BaseCube")
cube.Label = "40 mm cube body"
cube.Length = side
cube.Width = side
cube.Height = side

hole = doc.addObject("Part::Cylinder", "ThroughHoleTool")
hole.Label = "10 mm through-hole tool"
hole.Radius = hole_radius
hole.Height = side * 2.0
hole.Placement = App.Placement(
    App.Vector(side / 2.0, side / 2.0, -side / 2.0),
    App.Rotation(),
)

cut = doc.addObject("Part::Cut", "CubeWithThroughHole")
cut.Label = "Cube with 10 mm through-hole"
cut.Base = cube
cut.Tool = hole
'''
    return '''base = doc.addObject("Part::Box", "BasePlate")
base.Label = "Mounting bracket base"
base.Length = 80.0
base.Width = 38.0
base.Height = 8.0

upright = doc.addObject("Part::Box", "VerticalWeb")
upright.Label = "Vertical bracket web"
upright.Length = 8.0
upright.Width = 38.0
upright.Height = 48.0
upright.Placement = App.Placement(App.Vector(0.0, 0.0, 8.0), App.Rotation())

blank = doc.addObject("Part::Fuse", "BracketBlank")
blank.Label = "Fused bracket blank"
blank.Base = base
blank.Tool = upright
'''


def _safe_event_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    safe = dict(arguments)
    code = safe.get("code")
    if isinstance(code, str) and len(code) > 600:
        safe["code"] = f"{code[:600]}... ({len(code)} chars)"
    return safe


def _has_model_objects(content: dict[str, Any]) -> bool:
    object_count = content.get("object_count")
    if isinstance(object_count, int) and object_count > 0:
        return True
    objects = content.get("objects")
    return isinstance(objects, list) and len(objects) > 0


_ANTHROPIC_TOOL_IMAGE_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_MAX_INLINE_TOOL_IMAGE_BYTES = 5 * 1024 * 1024


def _anthropic_tool_result_content(
    tool_name: str,
    result: FreeCADToolResult,
) -> str | list[dict[str, Any]]:
    text = "FreeCAD tool result metadata:\n" + json.dumps(result.content, default=str)
    if tool_name != "get_view" or not result.ok or result.asset_path is None:
        return text

    media_type = _ANTHROPIC_TOOL_IMAGE_MEDIA_TYPES.get(result.asset_path.suffix.lower())
    if media_type is None:
        return text

    try:
        if result.asset_path.stat().st_size > _MAX_INLINE_TOOL_IMAGE_BYTES:
            return text
        encoded = base64.b64encode(result.asset_path.read_bytes()).decode("ascii")
    except OSError:
        return text

    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": encoded,
            },
        },
        {"type": "text", "text": text},
    ]


def _tool_result_message(name: str, result: FreeCADToolResult) -> str:
    if not result.ok:
        return f"FreeCAD tool failed: {name}"
    if name == "get_view":
        return "Captured FreeCAD view update."
    if name == "export_model":
        return "Exported FreeCAD model artifacts."
    return f"FreeCAD tool completed: {name}"

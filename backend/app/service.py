from __future__ import annotations

import asyncio
from pathlib import Path

from .config import Settings
from .db import SQLiteRepository
from .agent import CADAgent
from .models import GenerationEventType, GenerationStatus, MessageRole
from .providers.base import LLMProvider
from .runner import CadRunner
from .validation import CodeValidationError, validate_cadquery_code


class GenerationService:
    def __init__(
        self,
        settings: Settings,
        repository: SQLiteRepository,
        provider: LLMProvider,
        runner: CadRunner,
        agent: CADAgent | None = None,
    ):
        self.settings = settings
        self.repository = repository
        self.provider = provider
        self.runner = runner
        self.agent = agent

    async def run_generation(self, generation_id: str) -> None:
        generation = self.repository.get_generation(generation_id)
        if generation is None:
            return

        self.repository.update_generation(
            generation_id,
            status=GenerationStatus.running.value,
            error=None,
        )
        self._event(
            generation_id,
            GenerationEventType.status,
            "Generation started.",
        )

        context = self._conversation_context(generation["conversation_id"])
        if self.settings.generation_mode == "agent":
            await self._run_agent_generation(generation, context)
            return

        previous_error: str | None = None
        max_attempts = self.settings.generation_max_repair_attempts + 1

        for attempt in range(1, max_attempts + 1):
            self.repository.update_generation(
                generation_id,
                status=GenerationStatus.running.value,
                attempt_count=attempt,
                error=previous_error,
            )
            generation_dir = self._generation_dir(generation["conversation_id"], generation_id)
            attempt_dir = generation_dir / f"attempt_{attempt}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            script_path = attempt_dir / "model.py"

            try:
                response = await self.provider.generate_cad(
                    context,
                    previous_error,
                    self.settings.cad_kernel,
                )
            except Exception as exc:
                await self._fail_generation(
                    generation_id,
                    f"LLM provider failed: {exc}",
                    None,
                )
                return

            script_path.write_text(response.code, encoding="utf-8")

            try:
                validate_cadquery_code(response.code, self.settings.cad_kernel)
            except CodeValidationError as exc:
                previous_error = f"Validation failed: {exc}"
                log_path = attempt_dir / "validation.log"
                log_path.write_text(previous_error, encoding="utf-8")
                self.repository.update_generation(
                    generation_id,
                    script_path=str(script_path),
                    log_path=str(log_path),
                    error=previous_error,
                )
                continue

            result = await asyncio.to_thread(self.runner.run, script_path, attempt_dir)
            if result.success and result.step_path and (result.glb_path or result.stl_path):
                self.repository.update_generation(
                    generation_id,
                    status=GenerationStatus.succeeded.value,
                    assistant_summary=response.assistant_summary,
                    script_path=str(script_path),
                    step_path=str(result.step_path),
                    glb_path=str(result.glb_path) if result.glb_path else None,
                    stl_path=str(result.stl_path) if result.stl_path else None,
                    native_path=str(result.native_path) if result.native_path else None,
                    log_path=str(result.log_path),
                    error=None,
                    attempt_count=attempt,
                )
                self.repository.create_message(
                    generation["conversation_id"],
                    MessageRole.assistant,
                    response.assistant_summary,
                    generation_id,
                )
                self._event(
                    generation_id,
                    GenerationEventType.artifact,
                    "CAD artifacts are available.",
                    data={
                        "step": str(result.step_path),
                        "glb": str(result.glb_path) if result.glb_path else None,
                        "stl": str(result.stl_path) if result.stl_path else None,
                        "native": str(result.native_path) if result.native_path else None,
                    },
                )
                return

            previous_error = _runner_failure_message(result.error, result.stdout, result.stderr)
            self.repository.update_generation(
                generation_id,
                script_path=str(script_path),
                log_path=str(result.log_path),
                error=previous_error,
                attempt_count=attempt,
            )

        await self._fail_generation(generation_id, previous_error or "Generation failed.", None)

    async def _run_agent_generation(
        self,
        generation: dict,
        context: list[dict],
    ) -> None:
        generation_id = generation["id"]
        if self.agent is None:
            await self._fail_generation(
                generation_id,
                "Agent mode is configured, but no CAD agent is available.",
                None,
            )
            return

        generation_dir = self._generation_dir(generation["conversation_id"], generation_id)
        generation_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = await self.agent.run(generation, context, generation_dir)
        except Exception as exc:
            await self._fail_generation(
                generation_id,
                f"Agent failed: {exc}",
                None,
            )
            return

        if result.success:
            self.repository.update_generation(
                generation_id,
                status=GenerationStatus.succeeded.value,
                assistant_summary=result.assistant_summary,
                script_path=str(result.script_path) if result.script_path else None,
                step_path=str(result.step_path) if result.step_path else None,
                glb_path=str(result.glb_path) if result.glb_path else None,
                stl_path=str(result.stl_path) if result.stl_path else None,
                native_path=str(result.native_path) if result.native_path else None,
                log_path=str(result.log_path) if result.log_path else None,
                error=None,
                attempt_count=max(result.tool_call_count, 1),
            )
            self.repository.create_message(
                generation["conversation_id"],
                MessageRole.assistant,
                result.assistant_summary,
                generation_id,
            )
            self._event(
                generation_id,
                GenerationEventType.status,
                "Agent generation completed.",
            )
            return

        await self._fail_generation(
            generation_id,
            result.error or "Agent generation failed.",
            result.log_path,
        )

    def _conversation_context(self, conversation_id: str) -> list[dict]:
        messages = self.repository.list_messages(conversation_id)
        attachments_by_message = self.repository.list_attachments_for_messages(
            [message["id"] for message in messages]
        )
        return [
            {
                "role": message["role"],
                "content": message["content"],
                "attachments": attachments_by_message.get(message["id"], []),
            }
            for message in messages
            if message["role"] in {MessageRole.user.value, MessageRole.assistant.value}
        ]

    def _generation_dir(self, conversation_id: str, generation_id: str) -> Path:
        return (
            self.settings.storage_dir
            / "conversations"
            / conversation_id
            / "generations"
            / generation_id
        )

    async def _fail_generation(
        self,
        generation_id: str,
        error: str,
        log_path: Path | None,
    ) -> None:
        generation = self.repository.get_generation(generation_id)
        if generation is None:
            return
        self.repository.update_generation(
            generation_id,
            status=GenerationStatus.failed.value,
            error=error,
            log_path=str(log_path) if log_path else generation.get("log_path"),
        )
        self.repository.create_message(
            generation["conversation_id"],
            MessageRole.assistant,
            "I could not generate a valid CAD model yet. The failure details are available in the run log.",
            generation_id,
        )
        self._event(
            generation_id,
            GenerationEventType.error,
            error,
        )

    def _event(
        self,
        generation_id: str,
        event_type: GenerationEventType,
        message: str,
        data: dict | None = None,
    ) -> None:
        self.repository.create_generation_event(
            generation_id=generation_id,
            event_type=event_type.value,
            message=message,
            data=data or {},
        )


def _runner_failure_message(error: str | None, stdout: str, stderr: str) -> str:
    parts = []
    if error:
        parts.append(error)
    if stderr:
        parts.append(f"stderr:\n{stderr[-3000:]}")
    if stdout:
        parts.append(f"stdout:\n{stdout[-3000:]}")
    return "\n\n".join(parts) or "CAD runner failed without output."

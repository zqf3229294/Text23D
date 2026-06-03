from .base import CADGenerationResponse
from .json_utils import parse_json_response
from .multimodal import anthropic_content_blocks
from ..config import Settings
from ..prompts import build_repair_prompt, build_system_prompt


class AnthropicProvider:
    def __init__(self, settings: Settings):
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "TEXT23D_ANTHROPIC_API_KEY is required for Anthropic provider."
            )
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise RuntimeError("Install the `anthropic` package to use Anthropic.") from exc

        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model

    async def generate_cad(
        self,
        messages: list[dict],
        previous_error: str | None = None,
        cad_kernel: str = "cadquery",
    ) -> CADGenerationResponse:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=5000,
            system=build_system_prompt(cad_kernel),
            messages=_anthropic_messages(messages, previous_error),
        )
        text_parts = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]
        return parse_json_response("\n".join(text_parts))


def _anthropic_messages(
    messages: list[dict],
    previous_error: str | None,
) -> list[dict]:
    result = []
    last_role = None
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
    if previous_error:
        repair = build_repair_prompt(previous_error)
        if result and result[-1]["role"] == "user":
            result[-1]["content"] += f"\n\n{repair}"
        else:
            result.append({"role": "user", "content": repair})
    return result


def _merge_anthropic_content(left, right):
    if isinstance(left, str) and isinstance(right, str):
        return f"{left}\n\n{right}"
    left_blocks = left if isinstance(left, list) else [{"type": "text", "text": left}]
    right_blocks = right if isinstance(right, list) else [{"type": "text", "text": right}]
    return [*left_blocks, *right_blocks]

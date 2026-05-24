from .base import CADGenerationResponse
from .json_utils import parse_json_response
from ..prompts import build_repair_prompt, build_system_prompt


class ChatCompletionsProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        model: str | None,
        provider_name: str,
        max_tokens: int,
    ):
        missing = []
        if not api_key:
            missing.append("api key")
        if not base_url:
            missing.append("base URL")
        if not model:
            missing.append("model")
        if missing:
            raise RuntimeError(
                f"{provider_name} provider is missing: {', '.join(missing)}."
            )

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("Install the `openai` package to use this provider.") from exc

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.provider_name = provider_name
        self.max_tokens = max_tokens

    async def generate_cad(
        self,
        messages: list[dict[str, str]],
        previous_error: str | None = None,
        cad_kernel: str = "cadquery",
    ) -> CADGenerationResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=_chat_messages(messages, previous_error, cad_kernel),
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=self.max_tokens,
        )
        if not response.choices:
            raise ValueError(f"{self.provider_name} returned no choices.")

        content = response.choices[0].message.content
        if not content:
            raise ValueError(f"{self.provider_name} returned empty content.")

        return parse_json_response(content)


def _chat_messages(
    messages: list[dict[str, str]],
    previous_error: str | None,
    cad_kernel: str,
) -> list[dict[str, str]]:
    result = [{"role": "system", "content": build_system_prompt(cad_kernel)}]
    result.extend(
        {"role": item["role"], "content": item["content"]}
        for item in messages
        if item.get("role") in {"user", "assistant"}
    )
    if previous_error:
        result.append({"role": "user", "content": build_repair_prompt(previous_error)})
    return result

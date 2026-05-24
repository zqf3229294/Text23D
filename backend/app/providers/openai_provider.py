from .base import CADGenerationResponse
from .json_utils import parse_json_response
from ..config import Settings
from ..prompts import SYSTEM_PROMPT, build_repair_prompt


class OpenAIProvider:
    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise RuntimeError("TEXT23D_OPENAI_API_KEY is required for OpenAI provider.")
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("Install the `openai` package to use OpenAI.") from exc

        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def generate_cad(
        self,
        messages: list[dict[str, str]],
        previous_error: str | None = None,
    ) -> CADGenerationResponse:
        input_messages = _with_repair_message(messages, previous_error)
        try:
            response = await self.client.responses.parse(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=input_messages,
                text_format=CADGenerationResponse,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise ValueError("OpenAI returned no parsed CAD response.")
            return parsed
        except AttributeError:
            response = await self.client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=input_messages,
            )
            return parse_json_response(response.output_text)


def _with_repair_message(
    messages: list[dict[str, str]],
    previous_error: str | None,
) -> list[dict[str, str]]:
    result = [{"role": item["role"], "content": item["content"]} for item in messages]
    if previous_error:
        result.append({"role": "user", "content": build_repair_prompt(previous_error)})
    return result

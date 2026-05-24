from typing import Protocol

from pydantic import BaseModel, Field


class CADGenerationResponse(BaseModel):
    assistant_summary: str = Field(min_length=1, max_length=2000)
    code: str = Field(min_length=1)


class LLMProvider(Protocol):
    async def generate_cad(
        self,
        messages: list[dict[str, str]],
        previous_error: str | None = None,
    ) -> CADGenerationResponse:
        ...

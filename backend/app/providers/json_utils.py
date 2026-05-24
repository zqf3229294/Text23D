import json
import re

from .base import CADGenerationResponse


FENCE_RE = re.compile(r"^```(?:json|python)?\s*|\s*```$", re.IGNORECASE)


def parse_json_response(text: str) -> CADGenerationResponse:
    cleaned = FENCE_RE.sub("", text.strip()).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Provider response did not contain a JSON object.")
    payload = json.loads(cleaned[start : end + 1])
    return CADGenerationResponse.model_validate(payload)

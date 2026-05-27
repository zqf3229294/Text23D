from pathlib import Path
from typing import Any

from .models import (
    ArtifactAvailability,
    ConversationDetail,
    ConversationRead,
    GenerationRead,
    MessageRead,
)


def _exists(path_value: str | None) -> bool:
    return bool(path_value and Path(path_value).exists())


def serialize_generation(row: dict[str, Any]) -> GenerationRead:
    return GenerationRead(
        id=row["id"],
        conversation_id=row["conversation_id"],
        status=row["status"],
        prompt=row["prompt"],
        assistant_summary=row.get("assistant_summary"),
        error=row.get("error"),
        attempt_count=row.get("attempt_count") or 0,
        artifacts=ArtifactAvailability(
            step=_exists(row.get("step_path")),
            glb=_exists(row.get("glb_path")),
            stl=_exists(row.get("stl_path")),
            native=_exists(row.get("native_path")),
            script=_exists(row.get("script_path")),
            log=_exists(row.get("log_path")),
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def serialize_message(row: dict[str, Any]) -> MessageRead:
    return MessageRead(**row)


def serialize_conversation(row: dict[str, Any]) -> ConversationRead:
    return ConversationRead(**row)


def serialize_conversation_detail(
    conversation: dict[str, Any],
    messages: list[dict[str, Any]],
    generations: list[dict[str, Any]],
) -> ConversationDetail:
    base = serialize_conversation(conversation)
    return ConversationDetail(
        **base.model_dump(),
        messages=[serialize_message(message) for message in messages],
        generations=[serialize_generation(generation) for generation in generations],
    )

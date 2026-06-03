import json
from pathlib import Path
from typing import Any

from .models import (
    ArtifactAvailability,
    ConversationDetail,
    ConversationRead,
    GenerationEventRead,
    GenerationRead,
    ImageAttachmentRead,
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


def serialize_generation_event(row: dict[str, Any]) -> GenerationEventRead:
    data = row.get("data_json") or "{}"
    return GenerationEventRead(
        id=row["id"],
        generation_id=row["generation_id"],
        event_type=row["event_type"],
        message=row["message"],
        tool_name=row.get("tool_name"),
        data=data if isinstance(data, dict) else json.loads(data),
        has_asset=_exists(row.get("asset_path")),
        created_at=row["created_at"],
    )


def serialize_image_attachment(row: dict[str, Any]) -> ImageAttachmentRead:
    return ImageAttachmentRead(
        id=row["id"],
        conversation_id=row["conversation_id"],
        message_id=row.get("message_id"),
        filename=row["filename"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        created_at=row["created_at"],
    )


def serialize_message(
    row: dict[str, Any],
    attachments: list[dict[str, Any]] | None = None,
) -> MessageRead:
    payload = {key: value for key, value in row.items() if key != "attachments"}
    return MessageRead(
        **payload,
        attachments=[
            serialize_image_attachment(attachment)
            for attachment in attachments or []
        ],
    )


def serialize_conversation(row: dict[str, Any]) -> ConversationRead:
    return ConversationRead(**row)


def serialize_conversation_detail(
    conversation: dict[str, Any],
    messages: list[dict[str, Any]],
    generations: list[dict[str, Any]],
) -> ConversationDetail:
    base = serialize_conversation(conversation)
    attachments_by_message = _attachments_by_message(messages)
    return ConversationDetail(
        **base.model_dump(),
        messages=[
            serialize_message(message, attachments_by_message.get(message["id"], []))
            for message in messages
        ],
        generations=[serialize_generation(generation) for generation in generations],
    )


def _attachments_by_message(
    messages: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for message in messages:
        for attachment in message.get("attachments") or []:
            result.setdefault(message["id"], []).append(attachment)
    return result

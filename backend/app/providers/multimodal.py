from __future__ import annotations

import base64
from pathlib import Path
from typing import Any


def message_text(message: dict[str, Any]) -> str:
    return str(message.get("content") or "")


def message_attachments(message: dict[str, Any]) -> list[dict[str, Any]]:
    attachments = message.get("attachments") or []
    return [item for item in attachments if isinstance(item, dict)]


def attachment_summary(message: dict[str, Any]) -> str:
    attachments = message_attachments(message)
    if not attachments:
        return message_text(message)
    names = ", ".join(str(item.get("filename") or "image") for item in attachments)
    return f"{message_text(message)}\n\nAttached reference image(s): {names}"


def anthropic_content_blocks(message: dict[str, Any]) -> str | list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for attachment in message_attachments(message):
        encoded = _attachment_base64(attachment)
        if not encoded:
            continue
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": attachment["content_type"],
                    "data": encoded,
                },
            }
        )
    text = message_text(message)
    if text or blocks:
        blocks.append({"type": "text", "text": text or "Use the attached image as CAD reference."})
    return blocks if blocks and any(block["type"] == "image" for block in blocks) else text


def openai_response_content(message: dict[str, Any]) -> str | list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    text = message_text(message)
    if text:
        blocks.append({"type": "input_text", "text": text})
    for attachment in message_attachments(message):
        data_url = attachment_data_url(attachment)
        if data_url:
            blocks.append({"type": "input_image", "image_url": data_url})
    return blocks if blocks else text


def chat_completion_content(message: dict[str, Any]) -> str | list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    text = message_text(message)
    if text:
        blocks.append({"type": "text", "text": text})
    for attachment in message_attachments(message):
        data_url = attachment_data_url(attachment)
        if data_url:
            blocks.append({"type": "image_url", "image_url": {"url": data_url}})
    return blocks if any(block["type"] == "image_url" for block in blocks) else text


def attachment_data_url(attachment: dict[str, Any]) -> str | None:
    encoded = _attachment_base64(attachment)
    if not encoded:
        return None
    return f"data:{attachment['content_type']};base64,{encoded}"


def _attachment_base64(attachment: dict[str, Any]) -> str | None:
    path_value = attachment.get("storage_path")
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return None
    return base64.b64encode(path.read_bytes()).decode("ascii")

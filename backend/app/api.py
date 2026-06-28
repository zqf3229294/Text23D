import asyncio
import re
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse

from .config import Settings
from .db import SQLiteRepository
from .models import (
    AppConfigRead,
    ConversationCreate,
    ConversationDetail,
    FeatureFlagsRead,
    GenerationEventRead,
    GenerationRead,
    ImageAttachmentRead,
    MessageRole,
    SubmitMessageRequest,
    SubmitMessageResponse,
)
from .serializers import (
    serialize_conversation_detail,
    serialize_generation,
    serialize_generation_event,
    serialize_image_attachment,
    serialize_message,
)
from .service import GenerationService


router = APIRouter(prefix="/api")


def get_repository(request: Request) -> SQLiteRepository:
    return request.app.state.repository


def get_generation_service(request: Request) -> GenerationService:
    return request.app.state.generation_service


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


@router.get("/config", response_model=AppConfigRead)
def get_app_config(settings: Settings = Depends(get_app_settings)) -> AppConfigRead:
    return AppConfigRead(
        features=FeatureFlagsRead(
            image_input_enabled=settings.image_input_enabled,
            image_max_upload_bytes=settings.image_max_upload_bytes,
            image_max_count_per_message=settings.image_max_count_per_message,
            image_allowed_content_types=settings.image_allowed_content_types,
        )
    )


@router.post("/conversations", response_model=ConversationDetail)
def create_conversation(
    payload: ConversationCreate | None = None,
    repository: SQLiteRepository = Depends(get_repository),
) -> ConversationDetail:
    conversation = repository.create_conversation(payload.title if payload else None)
    return serialize_conversation_detail(conversation, [], [])


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> ConversationDetail:
    conversation = repository.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    messages = repository.list_messages(conversation_id)
    return serialize_conversation_detail(
        conversation,
        _messages_with_attachments(repository, messages),
        repository.list_generations(conversation_id),
    )


@router.post(
    "/conversations/{conversation_id}/attachments/images",
    response_model=ImageAttachmentRead,
)
async def upload_image_attachment(
    conversation_id: str,
    request: Request,
    filename: str = "image",
    repository: SQLiteRepository = Depends(get_repository),
    settings: Settings = Depends(get_app_settings),
) -> ImageAttachmentRead:
    if not settings.image_input_enabled:
        raise HTTPException(status_code=403, detail="Image input is disabled.")

    conversation = repository.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].lower()
    if content_type not in settings.image_allowed_content_types:
        raise HTTPException(status_code=415, detail="Unsupported image type.")

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError:
            declared_size = 0
        if declared_size > settings.image_max_upload_bytes:
            raise HTTPException(status_code=413, detail="Image is too large.")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=422, detail="Image body is empty.")
    if len(body) > settings.image_max_upload_bytes:
        raise HTTPException(status_code=413, detail="Image is too large.")

    storage_dir = settings.storage_dir / "conversations" / conversation_id / "attachments"
    storage_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    extension = _image_extension(content_type)
    storage_path = storage_dir / f"{uuid.uuid4().hex}{extension}"
    storage_path.write_bytes(body)

    attachment = repository.create_image_attachment(
        conversation_id=conversation_id,
        filename=safe_name,
        content_type=content_type,
        storage_path=str(storage_path),
        size_bytes=len(body),
    )
    return serialize_image_attachment(attachment)


@router.get("/conversations/{conversation_id}/attachments/images/{attachment_id}")
def get_image_attachment(
    conversation_id: str,
    attachment_id: str,
    repository: SQLiteRepository = Depends(get_repository),
):
    attachment = repository.get_image_attachment(attachment_id)
    if attachment is None or attachment["conversation_id"] != conversation_id:
        raise HTTPException(status_code=404, detail="Image attachment not found.")

    path = Path(attachment["storage_path"])
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found.")

    return FileResponse(
        path,
        media_type=attachment["content_type"],
        filename=attachment["filename"],
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SubmitMessageResponse,
)
def submit_message(
    conversation_id: str,
    payload: SubmitMessageRequest,
    background_tasks: BackgroundTasks,
    repository: SQLiteRepository = Depends(get_repository),
    generation_service: GenerationService = Depends(get_generation_service),
    settings: Settings = Depends(get_app_settings),
) -> SubmitMessageResponse:
    conversation = repository.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content cannot be blank.")

    if conversation["title"] == "Untitled design":
        repository.update_conversation_title(conversation_id, _title_from_prompt(content))

    attachment_rows = _validate_message_attachments(
        repository,
        settings,
        conversation_id,
        payload.attachment_ids,
    )
    message = repository.create_message(conversation_id, MessageRole.user, content)
    if attachment_rows:
        attachment_rows = repository.attach_images_to_message(
            conversation_id,
            message["id"],
            payload.attachment_ids,
        )
    generation = repository.create_generation(conversation_id, content)
    background_tasks.add_task(generation_service.run_generation, generation["id"])
    return SubmitMessageResponse(
        message=serialize_message(message, attachment_rows),
        generation=serialize_generation(generation),
    )


@router.get("/generations/{generation_id}", response_model=GenerationRead)
def get_generation(
    generation_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> GenerationRead:
    generation = repository.get_generation(generation_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="Generation not found.")
    return serialize_generation(generation)


@router.get(
    "/generations/{generation_id}/events",
    response_model=list[GenerationEventRead],
)
def get_generation_events(
    generation_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> list[GenerationEventRead]:
    generation = repository.get_generation(generation_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="Generation not found.")
    return [
        serialize_generation_event(event)
        for event in repository.list_generation_events(generation_id)
    ]


@router.get("/generations/{generation_id}/events/{event_id}/asset")
def get_generation_event_asset(
    generation_id: str,
    event_id: str,
    repository: SQLiteRepository = Depends(get_repository),
):
    generation = repository.get_generation(generation_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="Generation not found.")

    event = repository.get_generation_event(generation_id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")

    path_value = event.get("asset_path")
    if not path_value:
        raise HTTPException(status_code=404, detail="Event asset not available.")

    path = Path(path_value)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Event asset file not found.")

    return FileResponse(path, media_type=_event_asset_media_type(path))


@router.websocket("/generations/{generation_id}/stream")
async def stream_generation_events(websocket: WebSocket, generation_id: str):
    await websocket.accept()
    repository: SQLiteRepository = websocket.app.state.repository
    try:
        generation = repository.get_generation(generation_id)
        if generation is None:
            await websocket.send_json(
                {"type": "error", "detail": "Generation not found."}
            )
            await websocket.close(code=1008)
            return

        seen: set[str] = set()
        while True:
            events = repository.list_generation_events(generation_id)
            for event in events:
                if event["id"] in seen:
                    continue
                seen.add(event["id"])
                payload = serialize_generation_event(event).model_dump(mode="json")
                await websocket.send_json({"type": "event", "event": payload})

            generation = repository.get_generation(generation_id)
            if generation and generation["status"] in {"succeeded", "failed"}:
                await websocket.send_json(
                    {
                        "type": "done",
                        "generation": serialize_generation(generation).model_dump(
                            mode="json"
                        ),
                    }
                )
                await websocket.close()
                return

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return


@router.get("/generations/{generation_id}/artifacts/{kind}")
def get_generation_artifact(
    generation_id: str,
    kind: str,
    repository: SQLiteRepository = Depends(get_repository),
):
    generation = repository.get_generation(generation_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="Generation not found.")

    path_field = {
        "step": "step_path",
        "glb": "glb_path",
        "stl": "stl_path",
        "native": "native_path",
        "script": "script_path",
        "log": "log_path",
    }.get(kind)
    if path_field is None:
        raise HTTPException(status_code=404, detail="Artifact kind not found.")

    path_value = generation.get(path_field)
    if not path_value:
        raise HTTPException(status_code=404, detail="Artifact not available.")

    path = Path(path_value)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found.")

    return FileResponse(
        path,
        media_type=_media_type(kind),
        filename=_artifact_filename(generation_id, kind),
    )


def _media_type(kind: str) -> str:
    return {
        "step": "model/step",
        "glb": "model/gltf-binary",
        "stl": "model/stl",
        "native": "application/vnd.freecad",
        "script": "text/x-python",
        "log": "text/plain",
    }[kind]


def _event_asset_media_type(path: Path) -> str:
    return {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".txt": "text/plain",
        ".log": "text/plain",
    }.get(path.suffix.lower(), "application/octet-stream")


def _artifact_filename(generation_id: str, kind: str) -> str:
    extension = {
        "step": "step",
        "glb": "glb",
        "stl": "stl",
        "native": "FCStd",
        "script": "py",
        "log": "log",
    }[kind]
    return f"{generation_id}.{extension}"


def _title_from_prompt(prompt: str) -> str:
    compact = " ".join(prompt.split())
    return compact[:60] + ("..." if len(compact) > 60 else "")


def _messages_with_attachments(
    repository: SQLiteRepository,
    messages: list[dict],
) -> list[dict]:
    attachments_by_message = repository.list_attachments_for_messages(
        [message["id"] for message in messages]
    )
    return [
        {
            **message,
            "attachments": attachments_by_message.get(message["id"], []),
        }
        for message in messages
    ]


def _validate_message_attachments(
    repository: SQLiteRepository,
    settings: Settings,
    conversation_id: str,
    attachment_ids: list[str],
) -> list[dict]:
    unique_ids = list(dict.fromkeys(attachment_ids))
    if not unique_ids:
        return []
    if not settings.image_input_enabled:
        raise HTTPException(status_code=403, detail="Image input is disabled.")
    if len(unique_ids) > settings.image_max_count_per_message:
        raise HTTPException(
            status_code=413,
            detail=f"At most {settings.image_max_count_per_message} images are allowed.",
        )

    attachments = []
    for attachment_id in unique_ids:
        attachment = repository.get_image_attachment(attachment_id)
        if attachment is None:
            raise HTTPException(status_code=404, detail="Image attachment not found.")
        if attachment["conversation_id"] != conversation_id:
            raise HTTPException(
                status_code=400,
                detail="Image attachment belongs to another conversation.",
            )
        if attachment["message_id"] is not None:
            raise HTTPException(
                status_code=400,
                detail="Image attachment is already linked to a message.",
            )
        attachments.append(attachment)
    return attachments


def _safe_filename(filename: str) -> str:
    compact = Path(filename or "image").name.strip()
    compact = re.sub(r"[^A-Za-z0-9._ -]+", "_", compact)
    compact = compact.strip(" .")
    return compact[:120] or "image"


def _image_extension(content_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(content_type, ".img")

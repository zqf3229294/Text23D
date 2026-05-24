from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from .db import SQLiteRepository
from .models import (
    ConversationCreate,
    ConversationDetail,
    GenerationRead,
    MessageRole,
    SubmitMessageRequest,
    SubmitMessageResponse,
)
from .serializers import (
    serialize_conversation_detail,
    serialize_generation,
    serialize_message,
)
from .service import GenerationService


router = APIRouter(prefix="/api")


def get_repository(request: Request) -> SQLiteRepository:
    return request.app.state.repository


def get_generation_service(request: Request) -> GenerationService:
    return request.app.state.generation_service


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
    return serialize_conversation_detail(
        conversation,
        repository.list_messages(conversation_id),
        repository.list_generations(conversation_id),
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
) -> SubmitMessageResponse:
    conversation = repository.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content cannot be blank.")

    if conversation["title"] == "Untitled design":
        repository.update_conversation_title(conversation_id, _title_from_prompt(content))

    message = repository.create_message(conversation_id, MessageRole.user, content)
    generation = repository.create_generation(conversation_id, content)
    background_tasks.add_task(generation_service.run_generation, generation["id"])
    return SubmitMessageResponse(
        message=serialize_message(message),
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
        "script": "text/x-python",
        "log": "text/plain",
    }[kind]


def _artifact_filename(generation_id: str, kind: str) -> str:
    extension = {
        "step": "step",
        "glb": "glb",
        "script": "py",
        "log": "log",
    }[kind]
    return f"{generation_id}.{extension}"


def _title_from_prompt(prompt: str) -> str:
    compact = " ".join(prompt.split())
    return compact[:60] + ("..." if len(compact) > 60 else "")

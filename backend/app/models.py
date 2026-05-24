from enum import Enum

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"


class GenerationStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class ArtifactAvailability(BaseModel):
    step: bool = False
    glb: bool = False
    stl: bool = False
    native: bool = False
    script: bool = False
    log: bool = False


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationRead(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class MessageRead(BaseModel):
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    generation_id: str | None = None
    created_at: str


class GenerationRead(BaseModel):
    id: str
    conversation_id: str
    status: GenerationStatus
    prompt: str
    assistant_summary: str | None = None
    error: str | None = None
    attempt_count: int = 0
    artifacts: ArtifactAvailability = Field(default_factory=ArtifactAvailability)
    created_at: str
    updated_at: str


class ConversationDetail(ConversationRead):
    messages: list[MessageRead] = Field(default_factory=list)
    generations: list[GenerationRead] = Field(default_factory=list)


class SubmitMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class SubmitMessageResponse(BaseModel):
    message: MessageRead
    generation: GenerationRead


class ErrorResponse(BaseModel):
    detail: str

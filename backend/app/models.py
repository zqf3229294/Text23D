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


class GenerationEventType(str, Enum):
    status = "status"
    tool_call = "tool_call"
    tool_result = "tool_result"
    screenshot = "screenshot"
    error = "error"
    artifact = "artifact"


class ArtifactAvailability(BaseModel):
    step: bool = False
    glb: bool = False
    stl: bool = False
    native: bool = False
    script: bool = False
    log: bool = False


class FeatureFlagsRead(BaseModel):
    image_input_enabled: bool = False
    image_max_upload_bytes: int = 0
    image_max_count_per_message: int = 0
    image_allowed_content_types: list[str] = Field(default_factory=list)


class AppConfigRead(BaseModel):
    features: FeatureFlagsRead = Field(default_factory=FeatureFlagsRead)


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationRead(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ImageAttachmentRead(BaseModel):
    id: str
    conversation_id: str
    message_id: str | None = None
    filename: str
    content_type: str
    size_bytes: int
    created_at: str


class MessageRead(BaseModel):
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    generation_id: str | None = None
    attachments: list[ImageAttachmentRead] = Field(default_factory=list)
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


class GenerationEventRead(BaseModel):
    id: str
    generation_id: str
    event_type: GenerationEventType
    message: str
    tool_name: str | None = None
    data: dict = Field(default_factory=dict)
    has_asset: bool = False
    created_at: str


class ConversationDetail(ConversationRead):
    messages: list[MessageRead] = Field(default_factory=list)
    generations: list[GenerationRead] = Field(default_factory=list)


class SubmitMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=10)


class SubmitMessageResponse(BaseModel):
    message: MessageRead
    generation: GenerationRead


class ErrorResponse(BaseModel):
    detail: str

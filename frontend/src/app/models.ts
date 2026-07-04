export type MessageRole = 'user' | 'assistant';
export type GenerationStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled';
export type ArtifactKind = 'step' | 'glb' | 'stl' | 'native' | 'script' | 'log';
export type GenerationEventType =
  | 'status'
  | 'tool_call'
  | 'tool_result'
  | 'screenshot'
  | 'error'
  | 'artifact';

export interface ArtifactAvailability {
  step: boolean;
  glb: boolean;
  stl: boolean;
  native: boolean;
  script: boolean;
  log: boolean;
}

export interface AppConfig {
  features: {
    image_input_enabled: boolean;
    image_max_upload_bytes: number;
    image_max_count_per_message: number;
    image_allowed_content_types: string[];
  };
}

export interface ImageAttachment {
  id: string;
  conversation_id: string;
  message_id?: string | null;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  generation_id?: string | null;
  attachments: ImageAttachment[];
  created_at: string;
}

export interface ChatSubmitPayload {
  content: string;
  images: File[];
}

export interface Generation {
  id: string;
  conversation_id: string;
  status: GenerationStatus;
  prompt: string;
  assistant_summary?: string | null;
  error?: string | null;
  attempt_count: number;
  artifacts: ArtifactAvailability;
  created_at: string;
  updated_at: string;
}

export interface GenerationEvent {
  id: string;
  generation_id: string;
  event_type: GenerationEventType;
  message: string;
  tool_name?: string | null;
  data: Record<string, unknown>;
  has_asset: boolean;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
  generations: Generation[];
}

export interface SubmitMessageResponse {
  message: Message;
  generation: Generation;
}

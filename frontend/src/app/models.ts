export type MessageRole = 'user' | 'assistant';
export type GenerationStatus = 'queued' | 'running' | 'succeeded' | 'failed';
export type ArtifactKind = 'step' | 'glb' | 'stl' | 'native' | 'script' | 'log';

export interface ArtifactAvailability {
  step: boolean;
  glb: boolean;
  stl: boolean;
  native: boolean;
  script: boolean;
  log: boolean;
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
  created_at: string;
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

export interface ConversationDetail extends Conversation {
  messages: Message[];
  generations: Generation[];
}

export interface SubmitMessageResponse {
  message: Message;
  generation: Generation;
}

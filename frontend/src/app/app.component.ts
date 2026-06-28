import { CommonModule } from '@angular/common';
import { Component, NgZone, OnDestroy, OnInit } from '@angular/core';
import { finalize, forkJoin, of, Subscription, switchMap, takeWhile, tap, timer } from 'rxjs';

import { ChatPanelComponent } from './components/chat-panel/chat-panel.component';
import { ModelViewerComponent } from './components/model-viewer/model-viewer.component';
import { ApiService } from './services/api.service';
import {
  ChatSubmitPayload,
  ConversationDetail,
  Generation,
  GenerationEvent,
  Message
} from './models';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, ChatPanelComponent, ModelViewerComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements OnInit, OnDestroy {
  conversation: ConversationDetail | null = null;
  messages: Message[] = [];
  activeGeneration: Generation | null = null;
  generationEvents: GenerationEvent[] = [];
  imageInputEnabled = false;
  imageMaxUploadBytes = 0;
  imageMaxCountPerMessage = 0;
  imageAllowedContentTypes: string[] = [];
  isSending = false;
  loadError = '';

  private polling?: Subscription;
  private eventSocket?: WebSocket;

  constructor(
    private readonly api: ApiService,
    private readonly zone: NgZone
  ) {}

  ngOnInit(): void {
    this.api.getConfig().subscribe({
      next: (config) => {
        this.imageInputEnabled = config.features.image_input_enabled;
        this.imageMaxUploadBytes = config.features.image_max_upload_bytes;
        this.imageMaxCountPerMessage = config.features.image_max_count_per_message;
        this.imageAllowedContentTypes = config.features.image_allowed_content_types;
      }
    });

    this.api.createConversation().subscribe({
      next: (conversation) => {
        this.conversation = conversation;
        this.messages = conversation.messages;
        this.activeGeneration = conversation.generations.at(-1) ?? null;
      },
      error: () => {
        this.loadError = 'Backend is not reachable at the configured API URL.';
      }
    });
  }

  ngOnDestroy(): void {
    this.polling?.unsubscribe();
    this.eventSocket?.close();
  }

  sendMessage(payload: ChatSubmitPayload): void {
    if (!this.conversation || this.isSending) {
      return;
    }

    this.isSending = true;
    this.loadError = '';
    const uploads =
      this.imageInputEnabled && payload.images.length > 0
        ? forkJoin(
            payload.images.map((image) =>
              this.api.uploadImageAttachment(this.conversation!.id, image)
            )
          )
        : of([]);

    uploads
      .pipe(
        switchMap((attachments) =>
          this.api.submitMessage(
            this.conversation!.id,
            payload.content,
            attachments.map((attachment) => attachment.id)
          )
        ),
        finalize(() => (this.isSending = false))
      )
      .subscribe({
        next: (response) => {
          this.messages = [...this.messages, response.message];
          this.activeGeneration = response.generation;
          this.generationEvents = [];
          this.streamGenerationEvents(response.generation.id);
          this.pollGeneration(response.generation.id);
        },
        error: () => {
          this.loadError = 'The message could not be submitted.';
        }
      });
  }

  private pollGeneration(generationId: string): void {
    this.polling?.unsubscribe();
    this.polling = timer(0, 1400)
      .pipe(
        switchMap(() => this.api.getGeneration(generationId)),
        tap((generation) => this.applyGeneration(generation)),
        takeWhile(
          (generation) =>
            generation.status === 'queued' || generation.status === 'running',
          true
        ),
        finalize(() => this.refreshConversation())
      )
      .subscribe({
        error: () => {
          this.loadError = 'Generation status could not be refreshed.';
        }
      });
  }

  private streamGenerationEvents(generationId: string): void {
    this.eventSocket?.close();
    this.api.getGenerationEvents(generationId).subscribe({
      next: (events) => {
        this.mergeGenerationEvents(events);
      }
    });

    const socket = new WebSocket(this.api.generationStreamUrl(generationId));
    this.eventSocket = socket;

    socket.onmessage = (message) => {
      this.zone.run(() => this.acceptStreamMessage(message.data));
    };
    socket.onerror = () => {
      this.zone.run(() => {
        this.loadError = 'Live generation updates disconnected.';
      });
    };
  }

  private refreshConversation(): void {
    if (!this.conversation) {
      return;
    }
    this.api.getConversation(this.conversation.id).subscribe({
      next: (conversation) => {
        this.conversation = conversation;
        this.messages = conversation.messages;
        const currentId = this.activeGeneration?.id;
        this.activeGeneration =
          conversation.generations.find((generation) => generation.id === currentId) ??
          conversation.generations.at(-1) ??
          null;
      }
    });
  }

  private applyGeneration(generation: Generation): void {
    this.activeGeneration = generation;
    if (!this.conversation) {
      return;
    }
    const generations = this.conversation.generations.filter(
      (item) => item.id !== generation.id
    );
    this.conversation = {
      ...this.conversation,
      generations: [...generations, generation]
    };
  }

  private acceptStreamMessage(raw: string): void {
    let payload: {
      type?: string;
      event?: GenerationEvent;
      generation?: Generation;
      detail?: string;
    };
    try {
      payload = JSON.parse(raw);
    } catch {
      return;
    }

    if (payload.type === 'event' && payload.event) {
      this.mergeGenerationEvents([payload.event]);
      return;
    }

    if (payload.type === 'done' && payload.generation) {
      this.applyGeneration(payload.generation);
      this.refreshConversation();
      return;
    }

    if (payload.type === 'error') {
      this.loadError = payload.detail ?? 'Live generation updates failed.';
    }
  }

  private mergeGenerationEvents(incoming: GenerationEvent[]): void {
    const existing = new Map(this.generationEvents.map((event) => [event.id, event]));
    for (const event of incoming) {
      existing.set(event.id, event);
    }
    this.generationEvents = Array.from(existing.values()).sort((a, b) =>
      a.created_at.localeCompare(b.created_at)
    );
  }
}

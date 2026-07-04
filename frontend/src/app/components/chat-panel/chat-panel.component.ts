import { CommonModule } from '@angular/common';
import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../services/api.service';
import {
  ArtifactKind,
  ChatSubmitPayload,
  Generation,
  GenerationEvent,
  ImageAttachment,
  Message
} from '../../models';

interface SelectedImage {
  file: File;
  previewUrl: string;
}

@Component({
  selector: 'app-chat-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat-panel.component.html',
  styleUrl: './chat-panel.component.css'
})
export class ChatPanelComponent implements OnChanges, OnDestroy {
  @Input() messages: Message[] = [];
  @Input() generation: Generation | null = null;
  @Input() events: GenerationEvent[] = [];
  @Input() imageInputEnabled = false;
  @Input() imageMaxUploadBytes = 0;
  @Input() imageMaxCount = 0;
  @Input() imageAllowedTypes: string[] = [];
  @Input() isSending = false;
  @Input() loadError = '';
  @Output() send = new EventEmitter<ChatSubmitPayload>();
  @Output() cancel = new EventEmitter<void>();

  draft = '';
  selectedImages: SelectedImage[] = [];
  imageError = '';
  eventsExpanded = true;
  currentTimeMs = Date.now();

  private readonly recentEventLimit = 4;
  private lastGenerationId = '';
  private durationTimer?: number;

  constructor(private readonly api: ApiService) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['generation']) {
      const generationId = this.generation?.id ?? '';
      if (generationId !== this.lastGenerationId) {
        this.lastGenerationId = generationId;
        this.eventsExpanded = !this.isTerminalGeneration(this.generation);
      } else if (this.isTerminalGeneration(this.generation)) {
        this.eventsExpanded = false;
      }
    }
    this.syncDurationTimer();
  }

  ngOnDestroy(): void {
    this.stopDurationTimer();
    this.clearSelectedImages();
  }

  get acceptTypes(): string {
    return this.imageAllowedTypes.length
      ? this.imageAllowedTypes.join(',')
      : 'image/png,image/jpeg,image/webp';
  }

  submit(): void {
    const content = this.draft.trim();
    if (!content || this.isSending) {
      return;
    }
    this.send.emit({
      content,
      images: this.selectedImages.map((image) => image.file)
    });
    this.draft = '';
    this.clearSelectedImages();
  }

  requestCancel(): void {
    if (this.isGenerationActive(this.generation)) {
      this.cancel.emit();
    }
  }

  toggleEvents(): void {
    this.eventsExpanded = !this.eventsExpanded;
  }

  get visibleEvents(): GenerationEvent[] {
    if (!this.eventsExpanded && this.isTerminalGeneration(this.generation)) {
      return [];
    }
    if (this.eventsExpanded && this.isTerminalGeneration(this.generation)) {
      return this.events;
    }
    return this.events.slice(-this.recentEventLimit);
  }

  artifactUrl(generationId: string, kind: ArtifactKind): string {
    return this.api.artifactUrl(generationId, kind);
  }

  imageAttachmentUrl(attachment: ImageAttachment): string {
    return this.api.imageAttachmentUrl(attachment.conversation_id, attachment.id);
  }

  eventAssetUrl(event: GenerationEvent): string {
    return this.api.generationEventAssetUrl(event.generation_id, event.id);
  }

  selectImages(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    this.imageError = '';

    for (const file of files) {
      if (this.selectedImages.length >= this.imageMaxCount) {
        this.imageError = `Only ${this.imageMaxCount} images can be attached.`;
        break;
      }
      if (this.imageAllowedTypes.length && !this.imageAllowedTypes.includes(file.type)) {
        this.imageError = 'Unsupported image type.';
        continue;
      }
      if (this.imageMaxUploadBytes && file.size > this.imageMaxUploadBytes) {
        this.imageError = 'Image is too large.';
        continue;
      }
      this.selectedImages = [
        ...this.selectedImages,
        {
          file,
          previewUrl: URL.createObjectURL(file)
        }
      ];
    }
    input.value = '';
  }

  removeSelectedImage(index: number): void {
    const image = this.selectedImages[index];
    if (image) {
      URL.revokeObjectURL(image.previewUrl);
    }
    this.selectedImages = this.selectedImages.filter((_item, itemIndex) => itemIndex !== index);
  }

  statusLabel(generation: Generation): string {
    const status = generation.status;
    if (status === 'succeeded') {
      return 'Ready';
    }
    if (status === 'failed') {
      return 'Failed';
    }
    if (status === 'cancelled') {
      return 'Stopped';
    }
    if (status === 'running') {
      return `Running attempt ${Math.max(generation.attempt_count, 1)}`;
    }
    return 'Queued';
  }

  workDurationLabel(generation: Generation): string {
    const started = Date.parse(generation.created_at);
    const ended = this.isGenerationActive(generation)
      ? this.currentTimeMs
      : Date.parse(generation.updated_at);
    if (!Number.isFinite(started) || !Number.isFinite(ended)) {
      return 'Worked for 0 m 00 s';
    }
    const totalSeconds = Math.max(0, Math.floor((ended - started) / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `Worked for ${minutes} m ${seconds.toString().padStart(2, '0')} s`;
  }

  isGenerationActive(generation: Generation | null): boolean {
    return generation?.status === 'queued' || generation?.status === 'running';
  }

  isTerminalGeneration(generation: Generation | null): boolean {
    return (
      generation?.status === 'succeeded' ||
      generation?.status === 'failed' ||
      generation?.status === 'cancelled'
    );
  }

  eventStateClass(index: number): string {
    const newestIndex = this.visibleEvents.length - 1;
    const age = newestIndex - index;
    if (age <= 0) {
      return 'event-current';
    }
    if (age === 1) {
      return 'event-recent';
    }
    return 'event-muted';
  }

  trackMessage(_index: number, message: Message): string {
    return message.id;
  }

  trackAttachment(_index: number, attachment: ImageAttachment): string {
    return attachment.id;
  }

  trackSelectedImage(index: number, image: SelectedImage): string {
    return `${image.file.name}:${image.file.size}:${index}`;
  }

  trackEvent(_index: number, event: GenerationEvent): string {
    return event.id;
  }

  private clearSelectedImages(): void {
    for (const image of this.selectedImages) {
      URL.revokeObjectURL(image.previewUrl);
    }
    this.selectedImages = [];
    this.imageError = '';
  }

  private syncDurationTimer(): void {
    if (this.isGenerationActive(this.generation)) {
      if (this.durationTimer === undefined) {
        this.durationTimer = window.setInterval(() => {
          this.currentTimeMs = Date.now();
        }, 1000);
      }
      return;
    }
    this.stopDurationTimer();
  }

  private stopDurationTimer(): void {
    if (this.durationTimer !== undefined) {
      window.clearInterval(this.durationTimer);
      this.durationTimer = undefined;
    }
  }
}

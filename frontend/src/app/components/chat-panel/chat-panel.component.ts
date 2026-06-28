import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnDestroy, Output } from '@angular/core';
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
export class ChatPanelComponent implements OnDestroy {
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

  draft = '';
  selectedImages: SelectedImage[] = [];
  imageError = '';

  constructor(private readonly api: ApiService) {}

  ngOnDestroy(): void {
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
    if (status === 'running') {
      return `Running attempt ${Math.max(generation.attempt_count, 1)}`;
    }
    return 'Queued';
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
}

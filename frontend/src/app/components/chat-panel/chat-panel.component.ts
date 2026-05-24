import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../services/api.service';
import { ArtifactKind, Generation, Message } from '../../models';

@Component({
  selector: 'app-chat-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat-panel.component.html',
  styleUrl: './chat-panel.component.css'
})
export class ChatPanelComponent {
  @Input() messages: Message[] = [];
  @Input() generation: Generation | null = null;
  @Input() isSending = false;
  @Input() loadError = '';
  @Output() send = new EventEmitter<string>();

  draft = '';

  constructor(private readonly api: ApiService) {}

  submit(): void {
    const content = this.draft.trim();
    if (!content || this.isSending) {
      return;
    }
    this.send.emit(content);
    this.draft = '';
  }

  artifactUrl(generationId: string, kind: ArtifactKind): string {
    return this.api.artifactUrl(generationId, kind);
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
}

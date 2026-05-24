import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { finalize, Subscription, switchMap, takeWhile, tap, timer } from 'rxjs';

import { ChatPanelComponent } from './components/chat-panel/chat-panel.component';
import { ModelViewerComponent } from './components/model-viewer/model-viewer.component';
import { ApiService } from './services/api.service';
import { ConversationDetail, Generation, Message } from './models';

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
  isSending = false;
  loadError = '';

  private polling?: Subscription;

  constructor(private readonly api: ApiService) {}

  ngOnInit(): void {
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
  }

  sendMessage(content: string): void {
    if (!this.conversation || this.isSending) {
      return;
    }

    this.isSending = true;
    this.loadError = '';
    this.api
      .submitMessage(this.conversation.id, content)
      .pipe(finalize(() => (this.isSending = false)))
      .subscribe({
        next: (response) => {
          this.messages = [...this.messages, response.message];
          this.activeGeneration = response.generation;
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
}

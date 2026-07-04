import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  AppConfig,
  ArtifactKind,
  ConversationDetail,
  Generation,
  GenerationEvent,
  ImageAttachment,
  SubmitMessageResponse
} from '../models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  readonly baseUrl = environment.apiBaseUrl.replace(/\/$/, '');

  constructor(private readonly http: HttpClient) {}

  getConfig(): Observable<AppConfig> {
    return this.http.get<AppConfig>(`${this.baseUrl}/api/config`);
  }

  createConversation(title?: string): Observable<ConversationDetail> {
    return this.http.post<ConversationDetail>(`${this.baseUrl}/api/conversations`, {
      title: title ?? null
    });
  }

  getConversation(conversationId: string): Observable<ConversationDetail> {
    return this.http.get<ConversationDetail>(
      `${this.baseUrl}/api/conversations/${conversationId}`
    );
  }

  submitMessage(
    conversationId: string,
    content: string,
    attachmentIds: string[] = []
  ): Observable<SubmitMessageResponse> {
    return this.http.post<SubmitMessageResponse>(
      `${this.baseUrl}/api/conversations/${conversationId}/messages`,
      { content, attachment_ids: attachmentIds }
    );
  }

  uploadImageAttachment(
    conversationId: string,
    file: File
  ): Observable<ImageAttachment> {
    const url = new URL(
      `${this.baseUrl}/api/conversations/${conversationId}/attachments/images`,
      window.location.origin
    );
    url.searchParams.set('filename', file.name);
    return this.http.post<ImageAttachment>(url.toString(), file, {
      headers: {
        'Content-Type': file.type || 'application/octet-stream'
      }
    });
  }

  imageAttachmentUrl(conversationId: string, attachmentId: string): string {
    return `${this.baseUrl}/api/conversations/${conversationId}/attachments/images/${attachmentId}`;
  }

  getGeneration(generationId: string): Observable<Generation> {
    return this.http.get<Generation>(`${this.baseUrl}/api/generations/${generationId}`);
  }

  cancelGeneration(generationId: string): Observable<Generation> {
    return this.http.post<Generation>(
      `${this.baseUrl}/api/generations/${generationId}/cancel`,
      {}
    );
  }

  getGenerationEvents(generationId: string): Observable<GenerationEvent[]> {
    return this.http.get<GenerationEvent[]>(
      `${this.baseUrl}/api/generations/${generationId}/events`
    );
  }

  artifactUrl(generationId: string, kind: ArtifactKind): string {
    return `${this.baseUrl}/api/generations/${generationId}/artifacts/${kind}`;
  }

  generationEventAssetUrl(generationId: string, eventId: string): string {
    return `${this.baseUrl}/api/generations/${generationId}/events/${eventId}/asset`;
  }

  generationStreamUrl(generationId: string): string {
    const url = new URL(
      `${this.baseUrl}/api/generations/${generationId}/stream`,
      window.location.origin
    );
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return url.toString();
  }
}

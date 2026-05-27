import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  ArtifactKind,
  ConversationDetail,
  Generation,
  SubmitMessageResponse
} from '../models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  readonly baseUrl = environment.apiBaseUrl.replace(/\/$/, '');

  constructor(private readonly http: HttpClient) {}

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
    content: string
  ): Observable<SubmitMessageResponse> {
    return this.http.post<SubmitMessageResponse>(
      `${this.baseUrl}/api/conversations/${conversationId}/messages`,
      { content }
    );
  }

  getGeneration(generationId: string): Observable<Generation> {
    return this.http.get<Generation>(`${this.baseUrl}/api/generations/${generationId}`);
  }

  artifactUrl(generationId: string, kind: ArtifactKind): string {
    return `${this.baseUrl}/api/generations/${generationId}/artifacts/${kind}`;
  }
}

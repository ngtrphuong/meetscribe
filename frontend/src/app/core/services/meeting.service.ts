import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Meeting, MeetingDetail, TranscriptSegment, Summary } from '../models/meeting.model';

@Injectable({ providedIn: 'root' })
export class MeetingService {
  constructor(private http: HttpClient) {}

  list(page = 1, perPage = 20, language?: string): Observable<{ meetings: Meeting[] }> {
    let params = new HttpParams().set('page', page).set('per_page', perPage);
    if (language) params = params.set('language', language);
    return this.http.get<{ meetings: Meeting[] }>('/api/meetings', { params });
  }

  get(id: string): Observable<MeetingDetail> {
    return this.http.get<MeetingDetail>(`/api/meetings/${id}`);
  }

  getTranscript(id: string): Observable<{ segments: TranscriptSegment[] }> {
    return this.http.get<{ segments: TranscriptSegment[] }>(`/api/meetings/${id}/transcript`);
  }

  summarize(id: string, template: string, llmProvider: string): Observable<Summary> {
    return this.http.post<Summary>(`/api/meetings/${id}/summarize`, {
      template,
      llm_provider: llmProvider,
    });
  }

  reprocess(id: string): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(`/api/meetings/${id}/reprocess`, {});
  }

  purge(id: string): Observable<any> {
    return this.http.delete(`/api/meetings/${id}/purge`);
  }

  search(query: string, type: 'fts' | 'semantic' = 'fts', language?: string): Observable<any> {
    let params = new HttpParams().set('q', query).set('type', type);
    if (language) params = params.set('language', language);
    return this.http.get('/api/search', { params });
  }
}

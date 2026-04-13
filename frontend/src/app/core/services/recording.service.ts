import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

export interface StartRecordingOptions {
  title?: string;
  system_device_id?: number;
  mic_device_id?: number;
  language?: string;
  hotwords?: string[];
  consent_recording?: boolean;
  consent_voiceprint?: boolean;
  template_name?: string;
  llm_provider?: string;
  silence_timeout?: number;
}

@Injectable({ providedIn: 'root' })
export class RecordingService {
  readonly activeMeetingId = signal<string | undefined>(undefined);
  readonly recordingStatus = signal<string>('idle');

  constructor(private http: HttpClient) {}

  async start(options: StartRecordingOptions = {}): Promise<string> {
    const body = {
      language: 'vi',
      consent_recording: false,
      consent_voiceprint: false,
      template_name: 'general_vi',
      llm_provider: 'ollama',
      silence_timeout: 300,
      ...options,
    };

    const res = await firstValueFrom(
      this.http.post<{ meeting_id: string; status: string }>('/api/recording/start', body)
    );

    this.activeMeetingId.set(res.meeting_id);
    this.recordingStatus.set('recording');
    return res.meeting_id;
  }

  async stop(meetingId: string): Promise<void> {
    await firstValueFrom(
      this.http.post<void>('/api/recording/stop', { meeting_id: meetingId })
    );
    this.recordingStatus.set('processing');
  }

  async pause(meetingId: string): Promise<void> {
    await firstValueFrom(
      this.http.post<void>('/api/recording/pause', { meeting_id: meetingId })
    );
    this.recordingStatus.set('paused');
  }

  async resume(meetingId: string): Promise<void> {
    await firstValueFrom(
      this.http.post<void>('/api/recording/resume', { meeting_id: meetingId })
    );
    this.recordingStatus.set('recording');
  }
}

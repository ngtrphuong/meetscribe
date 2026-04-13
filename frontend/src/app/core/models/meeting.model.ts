export interface Meeting {
  id: string;
  title: string;
  started_at: string;
  ended_at?: string;
  duration_seconds?: number;
  audio_retained: boolean;
  audio_file_path?: string;
  primary_language: string;
  asr_live_engine?: string;
  asr_post_engine?: string;
  llm_provider?: string;
  template_name?: string;
  consent_recording: boolean;
  consent_voiceprint: boolean;
  status: 'idle' | 'recording' | 'paused' | 'processing' | 'complete' | 'error';
  created_at?: string;
  updated_at?: string;
}

export interface TranscriptSegment {
  id?: number;
  meeting_id: string;
  speaker_label?: string;
  speaker_name?: string;
  text: string;
  start_time: number;
  end_time: number;
  confidence?: number;
  language?: string;
  source: 'live' | 'post';
  // Live WebSocket fields
  is_final?: boolean;
  timestamp?: number;
}

export interface Summary {
  id?: number;
  meeting_id: string;
  template_name?: string;
  content: string;
  llm_provider?: string;
  llm_model?: string;
  generated_at?: string;
}

export interface ActionItem {
  id?: number;
  meeting_id: string;
  description: string;
  owner?: string;
  deadline?: string;
  status: 'open' | 'in_progress' | 'done';
  created_at?: string;
}

export interface MeetingDetail extends Meeting {
  summary?: Summary;
  action_items: ActionItem[];
  segment_count: number;
}

export interface WsMessage {
  type: 'segment' | 'diarization' | 'status' | 'level' | 'ping' | 'pong';
  data?: any;
}

export interface AudioLevels {
  system: number;  // 0.0–1.0
  mic: number;     // 0.0–1.0
}

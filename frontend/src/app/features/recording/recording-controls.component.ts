/**
 * Recording controls — studio-style UI with elapsed timer, waveform, level meters.
 * Signals for all state (recording status, levels). Consent dialog gated (Decree 356).
 */
import {
  Component, ChangeDetectionStrategy, signal, inject,
  OnDestroy, OnInit, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { RecordingService } from '../../core/services/recording.service';
import { TranscriptStreamService } from '../../core/services/transcript-stream.service';
import { ConsentDialogComponent, ConsentResult } from '../consent/consent-dialog.component';

@Component({
  selector: 'ms-recording-controls',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, ConsentDialogComponent],
  template: `
    <!-- Consent overlay -->
    @if (showConsent()) {
      <ms-consent-dialog
        (confirmed)="onConsentConfirmed($event)"
        (cancelled)="showConsent.set(false)"
      />
    }

    <div class="flex flex-col h-full">

      <!-- ── Header ──────────────────────────────────────────────────── -->
      <div class="px-6 pt-6 pb-4 border-b shrink-0" style="border-color:var(--ms-border)">
        <h1 class="text-xl font-bold" style="color:var(--ms-text)">Ghi âm mới</h1>
        <p class="text-xs mt-0.5" style="color:var(--ms-muted)">
          AI tự động phiên âm · nhận diện người nói · tóm tắt sau cuộc họp
        </p>
        @if (startError()) {
          <div class="mt-3 rounded-xl px-3 py-2.5 text-xs leading-relaxed"
               style="background:rgba(239,68,68,0.12);color:#fecaca;border:1px solid rgba(239,68,68,0.35)">
            {{ startError() }}
          </div>
        }
      </div>

      <div class="flex-1 overflow-y-auto">

        <!-- ══════════════ IDLE STATE ══════════════ -->
        @if (status() === 'idle') {
          <div class="max-w-xl mx-auto px-6 py-8 fade-in">

            <!-- Meeting setup form -->
            <div class="card p-5 mb-4">
              <h2 class="text-xs font-bold uppercase tracking-widest mb-4"
                  style="color:var(--ms-muted)">Thông tin cuộc họp</h2>
              <div class="space-y-3">
                <div>
                  <label class="block text-xs font-semibold mb-1.5" style="color:var(--ms-text-2)">
                    Tiêu đề
                  </label>
                  <input [(ngModel)]="meetingTitle" placeholder="VD: Sprint review tuần 15…"
                         class="input" />
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="block text-xs font-semibold mb-1.5" style="color:var(--ms-text-2)">
                      Ngôn ngữ
                    </label>
                    <select [(ngModel)]="language" class="input select">
                      <option value="vi">🇻🇳 Tiếng Việt</option>
                      <option value="en">🇬🇧 English</option>
                      <option value="auto">⚡ Tự động</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-xs font-semibold mb-1.5" style="color:var(--ms-text-2)">
                      Mẫu tóm tắt
                    </label>
                    <select [(ngModel)]="template" class="input select">
                      <option value="general_vi">Họp chung</option>
                      <option value="standup_vi">Daily Standup</option>
                      <option value="client_call_vi">Họp khách hàng</option>
                      <option value="sprint_retro_vi">Sprint Retro</option>
                      <option value="one_on_one_vi">1-on-1</option>
                      <option value="interview_vi">Phỏng vấn</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label class="block text-xs font-semibold mb-1.5" style="color:var(--ms-text-2)">
                    Từ khoá gợi ý <span style="color:var(--ms-muted)">(tùy chọn, cách nhau bởi dấu phẩy)</span>
                  </label>
                  <input [(ngModel)]="hotwordsRaw"
                         placeholder="VD: Qwen3, TMA, Sprint, MeetScribe…"
                         class="input" />
                </div>
              </div>
            </div>

            <!-- AI engine chip row -->
            <div class="flex items-center gap-2 mb-6 flex-wrap">
              <span class="badge badge-primary">
                <svg width="9" height="9" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/></svg>
                LIVE: Parakeet-Vi
              </span>
              <span class="badge badge-accent">
                <svg width="9" height="9" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                POST: VibeVoice 7B
              </span>
              <span class="badge badge-idle">LLM: Qwen3-8B</span>
              <span class="badge badge-idle">Diarization: diart</span>
            </div>

            <!-- Big record button -->
            <div class="flex flex-col items-center gap-5">
              <div class="relative">
                <!-- Outer ring -->
                <div class="absolute inset-0 rounded-full opacity-20 pointer-events-none"
                     style="transform:scale(1.35);background:var(--ms-danger)"></div>
                <div class="absolute inset-0 rounded-full opacity-10 pointer-events-none"
                     style="transform:scale(1.6);background:var(--ms-danger)"></div>
                <button class="btn-record" (click)="showConsent.set(true)">
                  <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
                       stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                    <line x1="12" y1="19" x2="12" y2="23"/>
                    <line x1="8" y1="23" x2="16" y2="23"/>
                  </svg>
                </button>
              </div>
              <div class="text-center">
                <p class="text-sm font-semibold" style="color:var(--ms-text)">
                  Bắt đầu ghi âm
                </p>
                <p class="text-xs mt-0.5" style="color:var(--ms-muted)">
                  Nhấn để mở hội thoại xác nhận theo Nghị định 356/2025
                </p>
              </div>
            </div>
          </div>
        }

        <!-- ══════════════ RECORDING / PAUSED STATE ══════════════ -->
        @if (status() === 'recording' || status() === 'paused') {
          <div class="max-w-xl mx-auto px-6 py-8 fade-in">

            <!-- Status bar -->
            <div class="flex items-center gap-3 mb-6">
              <div class="btn-record-sm" [class.recording-pulse]="status() === 'recording'"
                   [style.background]="status() === 'recording' ? 'var(--ms-danger)' : 'var(--ms-warning)'">
                @if (status() === 'recording') {
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="white"><circle cx="12" cy="12" r="8"/></svg>
                } @else {
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="white">
                    <rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>
                  </svg>
                }
              </div>
              <div class="flex-1">
                <div class="text-xs font-bold uppercase tracking-widest"
                     [style.color]="status() === 'recording' ? 'var(--ms-danger)' : 'var(--ms-warning)'">
                  {{ status() === 'recording' ? 'Đang ghi âm' : 'Tạm dừng' }}
                </div>
                <div class="text-xs" style="color:var(--ms-muted)">{{ meetingTitle || 'Cuộc họp mới' }}</div>
              </div>
              <span class="badge" [class]="status() === 'recording' ? 'badge-recording' : 'badge-paused'">
                {{ status() === 'recording' ? 'LIVE' : 'PAUSED' }}
              </span>
            </div>

            <!-- Elapsed timer -->
            <div class="text-center mb-6">
              <div class="elapsed-timer" [style.color]="status() === 'paused' ? 'var(--ms-muted)' : 'var(--ms-text)'">
                {{ elapsedStr() }}
              </div>
              <div class="text-xs mt-1" style="color:var(--ms-muted)">thời gian ghi</div>
            </div>

            <!-- Waveform visualizer -->
            <div class="card p-4 mb-4">
              <div class="flex items-center justify-center gap-0.5 h-14 overflow-hidden mb-4">
                @for (bar of waveformBars(); track $index) {
                  <div class="waveform-bar flex-shrink-0"
                       [style.height.px]="bar"
                       [style.opacity]="status() === 'recording' ? 1 : 0.3"
                       [style.background]="barColor($index, waveformBars().length)">
                  </div>
                }
              </div>

              <!-- Level meters -->
              <div class="space-y-2.5">
                <div class="flex items-center gap-3">
                  <div class="flex items-center gap-1.5 w-20 shrink-0">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" stroke-width="2" stroke-linecap="round"
                         style="color:var(--ms-muted)">
                      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                      <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
                      <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
                    </svg>
                    <span class="text-xs" style="color:var(--ms-muted)">Hệ thống</span>
                  </div>
                  <div class="flex-1 h-2 rounded-full overflow-hidden" style="background:var(--ms-surface-2)">
                    <div class="level-bar h-full" [style.width.%]="levels().system * 100"></div>
                  </div>
                  <span class="text-xs w-8 text-right mono" style="color:var(--ms-muted)">
                    {{ (levels().system * 100).toFixed(0) }}
                  </span>
                </div>
                <div class="flex items-center gap-3">
                  <div class="flex items-center gap-1.5 w-20 shrink-0">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" stroke-width="2" stroke-linecap="round"
                         style="color:var(--ms-muted)">
                      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                    </svg>
                    <span class="text-xs" style="color:var(--ms-muted)">Micro</span>
                  </div>
                  <div class="flex-1 h-2 rounded-full overflow-hidden" style="background:var(--ms-surface-2)">
                    <div class="level-bar h-full" [style.width.%]="levels().mic * 100"></div>
                  </div>
                  <span class="text-xs w-8 text-right mono" style="color:var(--ms-muted)">
                    {{ (levels().mic * 100).toFixed(0) }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Controls -->
            <div class="flex gap-3">
              @if (status() === 'recording') {
                <button (click)="pause()" class="btn btn-ghost flex-1 btn-lg">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
                       stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                    <rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>
                  </svg>
                  Tạm dừng
                </button>
              } @else {
                <button (click)="resume()" class="btn btn-success flex-1 btn-lg">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
                       stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                  </svg>
                  Tiếp tục
                </button>
              }
              <button (click)="stop()" class="btn btn-danger flex-1 btn-lg">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                </svg>
                Dừng & xử lý
              </button>
            </div>

            <!-- View live transcript link -->
            @if (activeMeetingId()) {
              <div class="mt-3 text-center">
                <a [routerLink]="['/meetings', activeMeetingId()]"
                   class="text-xs" style="color:var(--ms-primary-h)">
                  Xem bản ghi trực tiếp →
                </a>
              </div>
            }
          </div>
        }

        <!-- ══════════════ PROCESSING STATE ══════════════ -->
        @if (status() === 'processing') {
          <div class="max-w-xl mx-auto px-6 py-16 text-center fade-in">
            <div class="relative inline-flex items-center justify-center w-20 h-20 mb-6">
              <div class="absolute inset-0 rounded-full"
                   style="background:rgba(245,158,11,0.1);animation:glow-pulse 2s ease-in-out infinite"></div>
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
                   class="spin-slow" style="color:var(--ms-warning)">
                <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/>
              </svg>
            </div>
            <h2 class="text-lg font-bold mb-2" style="color:var(--ms-text)">
              Đang xử lý bản ghi
            </h2>
            <p class="text-sm mb-1" style="color:var(--ms-muted)">
              VibeVoice-ASR 7B đang phiên âm lại toàn bộ âm thanh
            </p>
            <p class="text-xs mb-8" style="color:var(--ms-muted)">
              Kết quả sẽ chính xác hơn bản ghi trực tiếp. Thường mất 2–5 phút.
            </p>

            <!-- Progress steps -->
            <div class="text-left space-y-3 max-w-xs mx-auto">
              @for (step of processingSteps; track step.label) {
                <div class="flex items-center gap-3">
                  <div class="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                       [style.background]="step.done ? 'var(--ms-success-dim)' : 'var(--ms-surface-2)'"
                       [style.color]="step.done ? 'var(--ms-success)' : step.active ? 'var(--ms-warning)' : 'var(--ms-muted)'">
                    @if (step.done) {
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                           stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                    } @else if (step.active) {
                      <span class="spin" style="font-size:8px">⚙</span>
                    } @else {
                      <span style="font-size:8px;opacity:0.4">○</span>
                    }
                  </div>
                  <span class="text-xs"
                        [style.color]="step.active ? 'var(--ms-text)' : step.done ? 'var(--ms-success)' : 'var(--ms-muted)'">
                    {{ step.label }}
                  </span>
                </div>
              }
            </div>
          </div>
        }

      </div>
    </div>
  `,
})
export class RecordingControlsComponent implements OnInit, OnDestroy {
  private recordingService = inject(RecordingService);
  private transcriptStream = inject(TranscriptStreamService);
  private router = inject(Router);

  showConsent = signal(false);
  startError = signal<string | null>(null);
  meetingTitle = '';
  language = 'vi';
  template = 'general_vi';
  hotwordsRaw = '';

  private timerInterval?: ReturnType<typeof setInterval>;
  private elapsedSec = signal(0);

  get status()         { return this.recordingService.recordingStatus; }
  get levels()         { return this.transcriptStream.levels; }
  get activeMeetingId(){ return this.recordingService.activeMeetingId; }

  elapsedStr = computed(() => {
    const s = this.elapsedSec();
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0)
      return `${h.toString().padStart(2,'0')}:${m.toString().padStart(2,'0')}:${sec.toString().padStart(2,'0')}`;
    return `${m.toString().padStart(2,'0')}:${sec.toString().padStart(2,'0')}`;
  });

  waveformBars = computed(() => {
    const level = this.levels().system;
    const isRec = this.status() === 'recording';
    if (!isRec) return Array.from({ length: 48 }, () => 6);
    const t = Date.now() / 200;
    return Array.from({ length: 48 }, (_, i) => {
      const wave = Math.sin(i * 0.35 + t) * 0.5 + 0.5;
      return Math.max(4, Math.round((wave * 0.45 + level * 0.55) * 44));
    });
  });

  barColor(i: number, total: number): string {
    const pct = i / total;
    if (pct < 0.4) return 'var(--ms-primary)';
    if (pct < 0.7) return 'var(--ms-accent)';
    return 'var(--ms-success)';
  }

  processingSteps = [
    { label: 'Unload LIVE engines (Parakeet, diart)', done: false, active: true },
    { label: 'Load VibeVoice-ASR 7B (4-bit NF4)', done: false, active: false },
    { label: 'Full-file ASR + diarization', done: false, active: false },
    { label: 'LLM summarization (Qwen3-8B)', done: false, active: false },
    { label: 'Save to encrypted database', done: false, active: false },
  ];

  ngOnInit(): void {
    this.timerInterval = setInterval(() => {
      if (this.status() === 'recording') this.elapsedSec.update(s => s + 1);
    }, 1000);
  }

  ngOnDestroy(): void {
    if (this.timerInterval) clearInterval(this.timerInterval);
  }

  async onConsentConfirmed(consent: ConsentResult): Promise<void> {
    this.showConsent.set(false);
    this.startError.set(null);
    try {
      const hotwords = this.hotwordsRaw
        .split(',').map(h => h.trim()).filter(Boolean);
      const meetingId = await this.recordingService.start({
        title: this.meetingTitle || undefined,
        language: this.language,
        template_name: this.template,
        hotwords: hotwords.length ? hotwords : undefined,
        consent_recording: consent.recording,
        consent_voiceprint: consent.voiceprint,
      });
      this.elapsedSec.set(0);
      this.transcriptStream.listen(meetingId);
      this.router.navigate(['/meetings', meetingId]);
    } catch (err: unknown) {
      console.error('Failed to start recording:', err);
      this.startError.set(this.formatStartError(err));
    }
  }

  private formatStartError(err: unknown): string {
    if (err instanceof HttpErrorResponse) {
      const d = err.error?.detail;
      if (typeof d === 'string') {
        return d;
      }
      if (Array.isArray(d)) {
        return d.map((x: { msg?: string }) => x.msg).filter(Boolean).join(' ') || err.message;
      }
      return err.message || 'Không thể bắt đầu ghi âm.';
    }
    if (err instanceof Error) {
      return err.message;
    }
    return 'Không thể bắt đầu ghi âm.';
  }

  async pause(): Promise<void> {
    const id = this.activeMeetingId();
    if (id) await this.recordingService.pause(id);
  }

  async resume(): Promise<void> {
    const id = this.activeMeetingId();
    if (id) await this.recordingService.resume(id);
  }

  async stop(): Promise<void> {
    const id = this.activeMeetingId();
    if (id) {
      await this.recordingService.stop(id);
      this.processingSteps[0].active = true;
    }
  }
}

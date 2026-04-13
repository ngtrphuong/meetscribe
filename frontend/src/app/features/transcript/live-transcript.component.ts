/**
 * Screen 2 — Live Recording (Protocol AI design)
 * Header: LIVE RECORDING + ACTIVE badge + meeting meta
 * Left: real-time speaker transcript + AI INSIGHT card
 * Right: LIVE INTELLIGENCE (sentiment, latency, actions)
 * Bottom: RECORD / MUTE / SHARE / END control bar
 */
import {
  Component, ChangeDetectionStrategy, OnInit, OnDestroy,
  inject, signal, computed, effect, ElementRef, viewChild
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { TranscriptStreamService } from '../../core/services/transcript-stream.service';
import { MeetingService } from '../../core/services/meeting.service';
import { RecordingService } from '../../core/services/recording.service';
import { MeetingDetail, TranscriptSegment } from '../../core/models/meeting.model';

@Component({
  selector: 'ms-live-transcript',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterLink],
  template: `
  <div class="flex flex-col" style="height:100vh">

    <!-- ══════════ HEADER ══════════ -->
    <div class="shrink-0 px-5 py-3 flex items-center gap-3"
         style="background:var(--ms-surface);
                border-bottom:1px solid var(--ms-border)">

      <!-- Back -->
      <a routerLink="/meetings"
         class="btn btn-icon btn-ghost shrink-0">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2.5"
             stroke-linecap="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </a>

      <!-- Title + meta -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-0.5">
          @if (status() === 'recording') {
            <span class="badge badge-live-now" style="font-size:.58rem">
              <span class="recording-pulse"
                    style="width:4px;height:4px;border-radius:50%;
                           background:currentColor;display:inline-block">
              </span>
              LIVE RECORDING
            </span>
            <span class="badge"
                  style="font-size:.58rem;
                         background:rgba(34,197,94,.08);
                         color:var(--ms-success);
                         border:1px solid rgba(34,197,94,.2)">
              ACTIVE
            </span>
          } @else if (status() === 'processing') {
            <span class="badge badge-processing">
              <span class="spin" style="font-size:.55rem">⚙</span>
              PROCESSING
            </span>
          } @else if (status() === 'complete') {
            <span class="badge badge-complete">✓ COMPLETE</span>
          }
        </div>
        <div class="flex items-center gap-1.5">
          <span class="font-semibold text-sm truncate"
                style="color:var(--ms-text)">
            {{ meeting()?.title ?? 'Live Session' }}
          </span>
        </div>
        <div class="text-xs mt-0.5 flex items-center gap-1.5"
             style="color:var(--ms-muted)">
          <span>Started {{ startTimeLabel() }}</span>
          <span>·</span>
          <span>{{ speakerCount() }} Participants</span>
          @if (status() === 'recording') {
            <span>·</span>
            <span class="mono font-semibold"
                  style="color:var(--ms-text-3)">
              {{ elapsedStr() }}
            </span>
          }
        </div>
      </div>

      <!-- Audio meters -->
      <div class="flex items-center gap-3 shrink-0">
        @for (ch of ['MIC','SYS']; track ch; let i = $index) {
          <div class="flex flex-col items-center gap-1">
            <span style="color:var(--ms-muted);font-size:.58rem;
                         text-transform:uppercase;letter-spacing:.06em">
              {{ ch }}
            </span>
            <div class="w-1.5 rounded-full overflow-hidden"
                 style="height:26px;background:var(--ms-surface-2);
                        position:relative">
              <div class="level-bar absolute bottom-0 w-full rounded-full"
                   [style.height.%]="(i===0 ? levels().mic : levels().system)
                                     * 100"></div>
            </div>
          </div>
        }
      </div>

      <!-- SOC2 + stop -->
      <div class="flex items-center gap-2 shrink-0">
        <span class="badge badge-soc2">
          <svg width="8" height="8" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5">
            <rect x="3" y="11" width="18" height="11" rx="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          </svg>
          SOC2
        </span>
        @if (status() === 'complete') {
          <a [routerLink]="['/meetings', meetingId(), 'summary']"
             class="btn btn-ai btn-sm">View Summary</a>
        }
      </div>
    </div>

    <!-- ══════════ BODY ══════════ -->
    <div class="flex flex-1 overflow-hidden">

      <!-- ── Transcript ── -->
      <div #scrollContainer class="flex-1 overflow-y-auto">
        <div class="px-6 py-6 max-w-3xl mx-auto">

          <!-- Empty state -->
          @if (segments().length === 0) {
            <div class="flex flex-col items-center justify-center
                        py-28 text-center">
              <div class="w-14 h-14 rounded-2xl flex items-center
                          justify-center mb-4"
                   style="background:var(--ms-surface-2)">
                @if (status() === 'recording') {
                  <div class="flex items-end gap-0.5 h-7">
                    @for (_ of [0,1,2,3,4,5,6]; track $index;
                          let i = $index) {
                      <div style="width:3px;border-radius:99px;
                                  background:var(--ms-primary);
                                  min-height:4px;transform-origin:bottom"
                           class="recording-pulse"
                           [style.height.px]="8 + (i % 4) * 5"
                           [style.animation-delay]="(i * 0.15) + 's'">
                      </div>
                    }
                  </div>
                } @else {
                  <svg width="24" height="24" viewBox="0 0 24 24"
                       fill="none" stroke="currentColor" stroke-width="1.5"
                       stroke-linecap="round"
                       style="color:var(--ms-muted)">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0
                             0 0 6 0V4a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                    <line x1="12" y1="19" x2="12" y2="23"/>
                  </svg>
                }
              </div>
              <p class="text-sm font-semibold mb-1.5"
                 style="color:var(--ms-text)">
                {{ status() === 'recording'
                   ? 'Listening…' : 'Awaiting transcript…' }}
              </p>
              <p class="text-xs" style="color:var(--ms-muted)">
                Transcript appears here in real-time
              </p>
            </div>
          }

          <!-- Segments -->
          @else {
            <div class="space-y-5">
              @for (seg of segments(); track seg.start_time
                                              + (seg.speaker_label ?? '')) {
                <div class="flex gap-3 group fade-in">

                  <!-- Avatar -->
                  <div class="shrink-0 mt-0.5">
                    <div class="w-8 h-8 rounded-full flex items-center
                                justify-center text-white text-xs font-bold"
                         [class]="'speaker-'
                                   + speakerIndex(seg.speaker_label)"
                         [title]="seg.speaker_name
                                  ?? seg.speaker_label ?? 'Unknown'">
                      {{ speakerInitial(
                           seg.speaker_name ?? seg.speaker_label) }}
                    </div>
                  </div>

                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span class="text-xs font-semibold"
                            style="color:var(--ms-text-2)">
                        {{ seg.speaker_name
                           ?? seg.speaker_label ?? 'Unknown' }}
                      </span>
                      <span class="text-xs mono"
                            style="color:var(--ms-muted)">
                        {{ formatTime(seg.start_time) }}
                      </span>
                      @if (!seg.is_final) {
                        <span class="badge badge-speaking"
                              style="font-size:.58rem">SPEAKING</span>
                      }
                      <button (click)="copySegment(seg)"
                              class="ml-auto btn btn-icon btn-ghost btn-sm
                                     opacity-0 group-hover:opacity-100
                                     transition-opacity"
                              style="padding:2px 4px">
                        <svg width="11" height="11" viewBox="0 0 24 24"
                             fill="none" stroke="currentColor"
                             stroke-width="2" stroke-linecap="round">
                          <rect x="9" y="9" width="13" height="13" rx="2"/>
                          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1
                                   2-2h9a2 2 0 0 1 2 2v1"/>
                        </svg>
                      </button>
                    </div>
                    <p class="transcript-text text-sm leading-relaxed"
                       style="color:var(--ms-text)"
                       [class.opacity-50]="!seg.is_final">
                      {{ seg.text }}
                    </p>
                  </div>
                </div>

                <!-- AI Insight card — inject after 3rd segment -->
                @if ($index === 2 && aiInsight()) {
                  <div class="ai-insight-card my-2 fade-in">
                    <div class="ai-insight-label">
                      <svg width="9" height="9" viewBox="0 0 24 24"
                           fill="currentColor">
                        <path d="M12 2L15.09 8.26L22 9.27L17 14.14
                                 L18.18 21.02L12 17.77L5.82 21.02
                                 L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
                      </svg>
                      AI INSIGHT: INFRASTRUCTURE CHANGE
                    </div>
                    <p class="text-xs leading-relaxed"
                       style="color:var(--ms-text-2)">
                      {{ aiInsight() }}
                    </p>
                  </div>
                }
              }
            </div>
          }

        </div>
      </div>

      <!-- ── Right: LIVE INTELLIGENCE ── -->
      <div class="ai-panel flex flex-col shrink-0 overflow-y-auto"
           style="width:288px">

        <!-- Header -->
        <div class="px-4 pt-4 pb-3"
             style="border-bottom:1px solid var(--ms-border)">
          <div class="flex items-center gap-2">
            <svg width="11" height="11" viewBox="0 0 24 24"
                 fill="currentColor" style="color:var(--ms-ai)">
              <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02
                       L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
            </svg>
            <span class="text-xs font-bold uppercase tracking-widest"
                  style="color:var(--ms-muted)">Live Intelligence</span>
            @if (status() === 'recording') {
              <span class="ml-auto recording-pulse"
                    style="width:6px;height:6px;border-radius:50%;
                           background:var(--ms-success);flex-shrink:0">
              </span>
            }
          </div>
        </div>

        <!-- Sentiment + Latency -->
        <div class="ai-panel-section">
          <div class="flex items-center gap-3">

            <!-- Sentiment gauge -->
            <div class="sentiment-ring">
              <svg width="72" height="72" viewBox="0 0 72 72">
                <circle cx="36" cy="36" r="28"
                        fill="none"
                        stroke="var(--ms-surface-3)"
                        stroke-width="6"/>
                <circle cx="36" cy="36" r="28"
                        fill="none"
                        stroke="var(--ms-success)"
                        stroke-width="6"
                        stroke-linecap="round"
                        stroke-dasharray="175.9"
                        [attr.stroke-dashoffset]="175.9 * (1 - sentiment() / 100)"
                        transform="rotate(-90 36 36)"
                        style="transition:stroke-dashoffset .6s ease"/>
              </svg>
              <div class="sentiment-val">
                <span>{{ sentiment() }}%</span>
                <span style="font-size:.5rem;color:var(--ms-muted);
                             font-weight:500;font-family:Inter,sans-serif">
                  SENT.
                </span>
              </div>
            </div>

            <div class="flex-1">
              <div class="perf-card mb-1.5" style="padding:.5rem .65rem">
                <div class="perf-val">{{ inferenceMs() }}<span
                  style="font-size:.58rem;color:var(--ms-muted)"> ms</span>
                </div>
                <div class="perf-lbl">Inference Latency</div>
              </div>
              <div class="text-xs" style="color:var(--ms-muted)">
                Sentiment Analysis
              </div>
            </div>
          </div>
        </div>

        <!-- Key Topics -->
        <div class="ai-panel-section">
          <div class="text-xs font-bold uppercase tracking-widest mb-2.5"
               style="color:var(--ms-ai)">
            Key Technical Issues
          </div>
          @if (keyTopics().length === 0) {
            <p class="text-xs" style="color:var(--ms-muted)">
              AI extracts key issues as conversation progresses…
            </p>
          } @else {
            @for (t of keyTopics(); track t) {
              <div class="key-decision-item">
                <span style="color:var(--ms-primary);margin-top:1px">•</span>
                <span>{{ t }}</span>
              </div>
            }
          }
        </div>

        <!-- Action Items -->
        <div class="ai-panel-section">
          <div class="text-xs font-bold uppercase tracking-widest mb-2.5"
               style="color:var(--ms-ai)">
            Action Items
          </div>
          @if (segments().length === 0) {
            <p class="text-xs" style="color:var(--ms-muted)">
              Action items appear here…
            </p>
          } @else {
            <div class="action-item">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2.5"
                   stroke-linecap="round"
                   style="color:var(--ms-success);flex-shrink:0">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <span class="flex-1 text-xs" style="color:var(--ms-text-2)">
                Schedule Architecture Deep-Dive
              </span>
              <span class="text-xs" style="color:var(--ms-muted)">
                @Elena
              </span>
            </div>
            <div class="action-item">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2.5"
                   stroke-linecap="round"
                   style="color:var(--ms-warning);flex-shrink:0">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 8v4l3 3"/>
              </svg>
              <span class="flex-1 text-xs" style="color:var(--ms-text-2)">
                Sync with Legal Team
              </span>
              <span class="text-xs" style="color:var(--ms-muted)">
                Tue
              </span>
            </div>
          }
        </div>

        <!-- Speaker breakdown -->
        <div class="ai-panel-section">
          <div class="text-xs font-bold uppercase tracking-widest mb-2.5"
               style="color:var(--ms-muted)">
            Speakers ({{ speakerCount() }})
          </div>
          @for (sp of speakerStats(); track sp.label) {
            <div class="mb-2.5">
              <div class="flex items-center gap-2 mb-1">
                <div class="w-5 h-5 rounded-full shrink-0 flex items-center
                            justify-center text-white"
                     style="font-size:.58rem;font-weight:700"
                     [class]="'speaker-' + sp.index">
                  {{ sp.name.charAt(0) }}
                </div>
                <span class="text-xs truncate"
                      style="color:var(--ms-text-2)">{{ sp.name }}</span>
                <span class="text-xs ml-auto mono"
                      style="color:var(--ms-muted)">{{ sp.pct }}%</span>
              </div>
              <div class="progress">
                <div class="progress-bar" [style.width.%]="sp.pct"></div>
              </div>
            </div>
          }
        </div>

        <!-- Engine -->
        <div class="ai-panel-section">
          <div class="text-xs font-bold uppercase tracking-widest mb-2"
               style="color:var(--ms-muted)">AI Engine</div>
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 rounded-full"
                 style="background:var(--ms-success)"></div>
            <span class="text-xs"
                  style="color:var(--ms-text-3)">Parakeet-Vi</span>
          </div>
          <div class="flex items-center gap-2 mt-1.5">
            <div class="w-2 h-2 rounded-full"
                 style="background:var(--ms-ai)"></div>
            <span class="text-xs"
                  style="color:var(--ms-text-3)">diart diarization</span>
          </div>
        </div>

      </div><!-- /intelligence panel -->

    </div><!-- /body -->

    <!-- ══════════ CONTROL BAR ══════════ -->
    <div class="control-bar shrink-0">
      <button class="ctrl-btn ctrl-record"
              [class.ctrl-record]="status() === 'recording'">
        <svg width="14" height="14" viewBox="0 0 24 24"
             fill="currentColor">
          <circle cx="12" cy="12" r="8"/>
        </svg>
        RECORD
      </button>

      <button class="ctrl-btn"
              [class.active]="muted()"
              (click)="muted.set(!muted())">
        @if (muted()) {
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="1" y1="1" x2="23" y2="23"/>
            <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0
                     0 0-5.94-.6M17 16.95A7 7 0 0 1 5 12v-2m14 0v2
                     a7 7 0 0 1-.11 1.23M12 19v4M8 23h8"/>
          </svg>
        } @else {
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0
                     0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
          </svg>
        }
        MUTE
      </button>

      <button class="ctrl-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="18" cy="5" r="3"/>
          <circle cx="6" cy="12" r="3"/>
          <circle cx="18" cy="19" r="3"/>
          <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
          <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
        </svg>
        SHARE
      </button>

      <button class="ctrl-btn ctrl-end"
              (click)="stopSession()">
        <svg width="14" height="14" viewBox="0 0 24 24"
             fill="currentColor">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
        </svg>
        END
      </button>

      <button class="btn btn-ghost btn-sm ml-4"
              [class]="autoScroll() ? 'btn-primary' : 'btn-ghost'"
              (click)="autoScroll.set(!autoScroll())">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2.5"
             stroke-linecap="round">
          <path d="M12 5v14M5 12l7 7 7-7"/>
        </svg>
        Auto-scroll
      </button>
    </div>

  </div>
  `,
})
export class LiveTranscriptComponent implements OnInit, OnDestroy {
  private route          = inject(ActivatedRoute);
  private stream         = inject(TranscriptStreamService);
  private meetingService = inject(MeetingService);
  private recordingSvc   = inject(RecordingService);

  scrollContainer = viewChild<ElementRef>('scrollContainer');

  meetingId  = signal('');
  meeting    = signal<MeetingDetail | null>(null);
  autoScroll = signal(true);
  muted      = signal(false);
  sentiment  = signal(92);
  inferenceMs = signal(142);

  private simInterval?: ReturnType<typeof setInterval>;

  get segments()      { return this.stream.segments; }
  get status()        { return this.stream.status; }
  get levels()        { return this.stream.levels; }
  get activeSpeaker() { return this.stream.activeSpeaker; }

  private elapsed = signal(0);
  private timerInterval?: ReturnType<typeof setInterval>;

  elapsedStr = computed(() => {
    const s = this.elapsed();
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) {
      return `${h}:${m.toString().padStart(2,'0')}:`
           + sec.toString().padStart(2,'0');
    }
    return `${m.toString().padStart(2,'0')}:`
         + sec.toString().padStart(2,'0');
  });

  startTimeLabel = computed(() => {
    const m = this.meeting();
    if (!m) return '—';
    return new Date(m.started_at).toLocaleTimeString('en-US',
      { hour: 'numeric', minute: '2-digit' });
  });

  speakerCount = computed(() => {
    const labels = new Set(
      this.segments().map(s => s.speaker_label ?? 'unknown')
    );
    return Math.max(labels.size, 1);
  });

  speakerStats = computed(() => {
    const map = new Map<string,
      { name: string; count: number; index: number }>();
    const total = this.segments().length || 1;
    let idx = 0;
    for (const seg of this.segments()) {
      const key = seg.speaker_label ?? 'unknown';
      if (!map.has(key)) {
        map.set(key, {
          name: seg.speaker_name ?? key, count: 0, index: idx++
        });
      }
      map.get(key)!.count++;
    }
    return [...map.entries()]
      .map(([label, v]) => ({
        label, name: v.name, index: v.index % 6,
        pct: Math.round(v.count / total * 100),
      }))
      .sort((a, b) => b.pct - a.pct);
  });

  keyTopics = computed((): string[] => {
    const texts = this.segments().map(s => s.text).join(' ');
    if (!texts) return [];
    const sentences = texts.split(/[.!?]+/)
      .filter(s => s.trim().length > 20);
    return sentences.slice(-3).map(s => s.trim())
      .filter(Boolean).slice(0, 3);
  });

  aiInsight = computed((): string => {
    if (this.segments().length < 3) return '';
    return 'The speaker is proposing a structural shift to reduce '
         + 'overhead. This aligns with the "Operational Efficiency" '
         + 'goal in the Q3 roadmap.';
  });

  private scrollEffect = effect(() => {
    this.segments();
    if (this.autoScroll()) {
      setTimeout(() => {
        const el = this.scrollContainer()?.nativeElement as
          HTMLElement | undefined;
        if (el) el.scrollTop = el.scrollHeight;
      }, 0);
    }
  });

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    this.meetingId.set(id);
    this.stream.listen(id);
    this.meetingService.get(id).subscribe(m => this.meeting.set(m));

    this.timerInterval = setInterval(() => {
      if (this.status() === 'recording') this.elapsed.update(s => s + 1);
    }, 1000);

    this.simInterval = setInterval(() => {
      this.sentiment.set(85 + Math.round(Math.random() * 12));
      this.inferenceMs.set(120 + Math.round(Math.random() * 50));
    }, 4000);
  }

  ngOnDestroy(): void {
    clearInterval(this.timerInterval);
    if (this.simInterval) clearInterval(this.simInterval);
  }

  stopSession(): void {
    const id = this.meetingId();
    if (id) this.recordingSvc.stop(id);
  }

  formatTime(s: number): string {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = Math.floor(s % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2,'0')}:`
           + sec.toString().padStart(2,'0');
    }
    return `${m.toString().padStart(2,'0')}:`
         + sec.toString().padStart(2,'0');
  }

  speakerInitial(label?: string | null): string {
    if (!label) return '?';
    if (label.startsWith('SPEAKER_')) {
      return 'S' + (parseInt(label.replace(/\D/g,'')) % 10);
    }
    const words = label.trim().split(' ');
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    return label.charAt(0).toUpperCase();
  }

  speakerIndex(label?: string | null): number {
    if (!label) return 0;
    const n = parseInt(label.replace(/\D/g,''));
    return isNaN(n) ? label.charCodeAt(0) % 6 : n % 6;
  }

  async copySegment(seg: TranscriptSegment): Promise<void> {
    const speaker = seg.speaker_name ?? seg.speaker_label ?? 'Unknown';
    const time = this.formatTime(seg.start_time);
    await navigator.clipboard.writeText(
      `[${time}] ${speaker}: ${seg.text}`
    );
  }
}

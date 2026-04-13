/**
 * Screen 4 — Meeting Detail / AI Summary
 * Left: timestamped transcript
 * Right: AI Summary panel (Executive Overview, Key Decisions, Action Items, Topics, Sync)
 */
import {
  Component, ChangeDetectionStrategy, OnInit, inject, signal, computed
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MeetingService } from '../../core/services/meeting.service';
import { MeetingDetail, TranscriptSegment, ActionItem } from '../../core/models/meeting.model';

type SummaryTab = 'ai' | 'transcript' | 'actions';

@Component({
  selector: 'ms-summary-view',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterLink, FormsModule],
  template: `
  <div class="flex flex-col" style="height:100vh">

    <!-- ══════════════════ HEADER ══════════════════ -->
    <div class="flex items-center gap-3 px-5 py-3 shrink-0"
         style="background:var(--ms-surface);border-bottom:1px solid var(--ms-border)">

      <a [routerLink]="['/meetings']" class="btn btn-icon btn-ghost" data-tip="Back">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </a>

      <div class="flex-1 min-w-0">
        <div class="text-sm font-bold truncate" style="color:var(--ms-text)">
          {{ meeting()?.title ?? 'Loading…' }}
        </div>
        @if (meeting()) {
          <div class="flex items-center gap-2 mt-0.5">
            <span class="text-xs" style="color:var(--ms-muted)">
              {{ formatDate(meeting()!.started_at) }}
            </span>
            @if (meeting()!.duration_seconds) {
              <span class="text-xs" style="color:var(--ms-border-2)">·</span>
              <span class="text-xs" style="color:var(--ms-muted)">
                {{ formatDurationHMS(meeting()!.duration_seconds!) }}
              </span>
            }
          </div>
        }
      </div>

      <!-- Action buttons -->
      <div class="flex items-center gap-2 shrink-0">
        <button (click)="reprocess()" class="btn btn-ghost btn-sm gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
            <polyline points="1 4 1 10 7 10"/>
            <path d="M3.51 15a9 9 0 1 0 .49-5H1"/>
          </svg>
          Re-process
        </button>
        <button class="btn btn-primary btn-sm gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
            <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
          </svg>
          Share
        </button>
      </div>
    </div>

    <!-- ══════════════════ BODY ══════════════════ -->
    <div class="flex flex-1 overflow-hidden">

      <!-- ── Left: Transcript ── -->
      <div class="flex-1 flex flex-col overflow-hidden" style="min-width:0">

        <!-- Tabs -->
        <div class="flex shrink-0 px-4" style="border-bottom:1px solid var(--ms-border)">
          @for (tab of tabs; track tab.key) {
            <button class="px-4 py-3 text-xs font-700 uppercase tracking-widest transition-colors"
                    [style]="activeTab() === tab.key
                      ? 'color:var(--ms-text);border-bottom:2px solid var(--ms-primary)'
                      : 'color:var(--ms-muted);border-bottom:2px solid transparent'"
                    (click)="activeTab.set(tab.key)">
              {{ tab.label }}
            </button>
          }
        </div>

        <!-- Transcript tab -->
        @if (activeTab() === 'transcript') {
          <div class="flex-1 overflow-y-auto px-5 py-5">

            @if (loadingTranscript()) {
              <div class="space-y-4">
                @for (_ of [1,2,3,4]; track $index) {
                  <div class="flex gap-3">
                    <div class="skeleton w-8 h-8 rounded-full shrink-0"></div>
                    <div class="flex-1 space-y-2">
                      <div class="skeleton h-3 rounded" style="width:35%"></div>
                      <div class="skeleton h-3 rounded" style="width:90%"></div>
                      <div class="skeleton h-3 rounded" style="width:75%"></div>
                    </div>
                  </div>
                }
              </div>
            } @else if (segments().length === 0) {
              <div class="flex flex-col items-center justify-center h-52 text-center">
                <p class="text-sm font-medium" style="color:var(--ms-text)">No transcript available</p>
                <p class="text-xs mt-1" style="color:var(--ms-muted)">
                  Reprocess the meeting to generate a transcript
                </p>
              </div>
            } @else {
              <div class="space-y-5">
                @for (seg of segments(); track seg.start_time) {
                  <div class="flex gap-3 group fade-in">
                    <div class="shrink-0">
                      <div class="w-8 h-8 rounded-full flex items-center justify-center
                                  text-white font-bold"
                           style="font-size:.65rem"
                           [class]="'speaker-' + speakerIndex(seg.speaker_label)">
                        {{ speakerInitial(seg.speaker_name ?? seg.speaker_label) }}
                      </div>
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-baseline gap-2 mb-1.5">
                        <span class="text-xs font-semibold" style="color:var(--ms-text-2)">
                          {{ seg.speaker_name ?? seg.speaker_label ?? 'Unknown' }}
                        </span>
                        <span class="text-xs mono" style="color:var(--ms-muted)">
                          {{ formatTime(seg.start_time) }}
                        </span>
                        <button (click)="copySegment(seg)"
                                class="ml-auto btn btn-icon btn-ghost btn-sm opacity-0 group-hover:opacity-100 transition-opacity"
                                style="padding:2px 4px">
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                               stroke="currentColor" stroke-width="2" stroke-linecap="round">
                            <rect x="9" y="9" width="13" height="13" rx="2"/>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                          </svg>
                        </button>
                      </div>
                      <p class="transcript-text text-sm" style="color:var(--ms-text)">{{ seg.text }}</p>
                    </div>
                  </div>
                }
              </div>
            }
          </div>
        }

        <!-- Actions tab -->
        @if (activeTab() === 'actions') {
          <div class="flex-1 overflow-y-auto px-5 py-5">
            @if (actionItems().length === 0) {
              <div class="flex flex-col items-center justify-center h-52 text-center">
                <p class="text-sm font-medium" style="color:var(--ms-text)">No action items yet</p>
                <button (click)="generateSummary()" class="btn btn-primary btn-sm mt-3">Generate Summary</button>
              </div>
            } @else {
              <div class="space-y-2">
                @for (a of actionItems(); track a.id) {
                  <div class="card p-4 flex items-start gap-3">
                    <div [class]="a.status === 'done' ? 'mt-0.5' : 'mt-0.5'">
                      <div class="w-4 h-4 rounded flex items-center justify-center"
                           [style]="a.status === 'done'
                             ? 'background:var(--ms-success);'
                             : 'border:1.5px solid var(--ms-border-2)'">
                        @if (a.status === 'done') {
                          <svg width="9" height="9" viewBox="0 0 24 24" fill="none"
                               stroke="white" stroke-width="3" stroke-linecap="round">
                            <polyline points="20 6 9 17 4 12"/>
                          </svg>
                        }
                      </div>
                    </div>
                    <div class="flex-1 min-w-0">
                      <p class="text-sm" style="color:var(--ms-text)">{{ a.description }}</p>
                      <div class="flex items-center gap-3 mt-1">
                        @if (a.owner) {
                          <span class="text-xs" style="color:var(--ms-muted)">{{ a.owner }}</span>
                        }
                        @if (a.deadline) {
                          <span class="text-xs" style="color:var(--ms-muted)">· {{ a.deadline }}</span>
                        }
                        @if (a.status) {
                          <span class="text-xs badge badge-idle ml-auto">{{ a.status }}</span>
                        }
                      </div>
                    </div>
                  </div>
                }
              </div>
            }
          </div>
        }

      </div>

      <!-- ── Right: AI SUMMARY panel ── -->
      <div class="ai-panel flex flex-col shrink-0 overflow-y-auto" style="width:300px">

        <!-- Panel header -->
        <div class="px-4 pt-4 pb-3" style="border-bottom:1px solid var(--ms-border)">
          <div class="flex items-center gap-2 mb-1">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="color:var(--ms-ai)">
              <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
            </svg>
            <span class="text-xs font-bold uppercase tracking-widest" style="color:var(--ms-muted)">AI Summary</span>
            @if (loadingSummary()) {
              <span class="spin ml-auto text-xs" style="color:var(--ms-ai)">⚙</span>
            }
          </div>
        </div>

        <!-- Meeting metadata -->
        <div class="ai-panel-section">
          <div class="grid grid-cols-3 gap-2 text-center">
            <div>
              <div class="text-sm font-bold" style="color:var(--ms-text)">
                {{ meeting()?.duration_seconds ? formatDurationShort(meeting()!.duration_seconds!) : '—' }}
              </div>
              <div class="stat-label">Duration</div>
            </div>
            <div>
              <div class="text-sm font-bold" style="color:var(--ms-text)">
                {{ participantCount() }}
              </div>
              <div class="stat-label">Participants</div>
            </div>
            <div>
              <div class="text-sm font-bold" style="color:var(--ms-text)">
                {{ meeting() ? formatShortDate(meeting()!.started_at) : '—' }}
              </div>
              <div class="stat-label">Date</div>
            </div>
          </div>
        </div>

        <!-- Executive Overview -->
        @if (summaryText()) {
          <div class="ai-panel-section">
            <div class="text-xs font-bold uppercase tracking-widest mb-2" style="color:var(--ms-ai)">
              Executive Overview
            </div>
            <p class="text-xs leading-relaxed" style="color:var(--ms-text-2)">
              {{ summaryText() }}
            </p>
          </div>
        } @else {
          <div class="ai-panel-section">
            <div class="text-xs font-bold uppercase tracking-widest mb-2" style="color:var(--ms-ai)">
              Executive Overview
            </div>
            @if (loadingSummary()) {
              <div class="space-y-2">
                <div class="skeleton h-2.5 rounded" style="width:95%"></div>
                <div class="skeleton h-2.5 rounded" style="width:80%"></div>
                <div class="skeleton h-2.5 rounded" style="width:60%"></div>
              </div>
            } @else {
              <button (click)="generateSummary()" class="btn btn-ai btn-sm w-full">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
                </svg>
                Generate AI Summary
              </button>
            }
          </div>
        }

        <!-- Key Decisions -->
        @if (keyDecisions().length > 0) {
          <div class="ai-panel-section">
            <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color:var(--ms-ai)">
              Key Decisions
            </div>
            @for (d of keyDecisions(); track d) {
              <div class="key-decision-item">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
                     style="color:var(--ms-ai);flex-shrink:0;margin-top:1px">
                  <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26Z"/>
                </svg>
                <span>{{ d }}</span>
              </div>
            }
          </div>
        }

        <!-- Action Items preview -->
        @if (actionItems().length > 0) {
          <div class="ai-panel-section">
            <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color:var(--ms-ai)">
              Action Items
            </div>
            @for (a of actionItems().slice(0, 4); track a.id) {
              <div class="action-item">
                <div class="w-3.5 h-3.5 rounded shrink-0 flex items-center justify-center"
                     [style]="a.status === 'done' ? 'background:var(--ms-success)' : 'border:1.5px solid var(--ms-border-2)'">
                  @if (a.status === 'done') {
                    <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  }
                </div>
                <span class="flex-1 min-w-0 truncate text-xs" style="color:var(--ms-text-2)">{{ a.description }}</span>
                @if (a.owner) {
                  <span class="text-xs shrink-0" style="color:var(--ms-muted)">{{ a.owner.split(' ')[0] }}</span>
                }
                @if (a.deadline) {
                  <span class="text-xs shrink-0 badge badge-idle ml-1">{{ a.deadline }}</span>
                }
              </div>
            }
            @if (actionItems().length > 4) {
              <button (click)="activeTab.set('actions')"
                      class="text-xs mt-2" style="color:var(--ms-primary-h)">
                +{{ actionItems().length - 4 }} more items
              </button>
            }
          </div>
        }

        <!-- Topics tags -->
        @if (topics().length > 0) {
          <div class="ai-panel-section">
            <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color:var(--ms-muted)">
              Topics
            </div>
            <div class="flex flex-wrap gap-1.5">
              @for (t of topics(); track t) {
                <span class="tag">{{ t }}</span>
              }
            </div>
          </div>
        }

        <!-- Sync & Export -->
        <div class="ai-panel-section">
          <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color:var(--ms-muted)">
            Sync & Export
          </div>
          <div class="space-y-2">
            <button class="btn btn-ghost btn-sm w-full gap-2 justify-start">
              <span style="font-size:.75rem">💬</span> Slack
            </button>
            <button class="btn btn-ghost btn-sm w-full gap-2 justify-start">
              <span style="font-size:.75rem">📘</span> Confluence
            </button>
            <button (click)="exportMarkdown()" class="btn btn-ghost btn-sm w-full gap-2 justify-start">
              <span style="font-size:.75rem">📄</span> Markdown
            </button>
          </div>
        </div>

      </div>

    </div>
  </div>
  `,
})
export class SummaryViewComponent implements OnInit {
  private route          = inject(ActivatedRoute);
  private meetingService = inject(MeetingService);
  private http           = inject(HttpClient);

  meetingId       = signal('');
  meeting         = signal<MeetingDetail | null>(null);
  segments        = signal<TranscriptSegment[]>([]);
  actionItems     = signal<ActionItem[]>([]);
  activeTab       = signal<SummaryTab>('transcript');
  loadingTranscript = signal(true);
  loadingSummary  = signal(false);

  tabs = [
    { key: 'transcript' as SummaryTab, label: 'Transcript' },
    { key: 'actions' as SummaryTab,    label: 'Actions' },
  ];

  summaryText = computed(() => {
    const s = this.meeting()?.summary?.content;
    if (!s) return '';
    // Return first paragraph
    const lines = s.split('\n').filter((l: string) => l.trim() && !l.startsWith('#'));
    return lines[0] ?? '';
  });

  keyDecisions = computed((): string[] => {
    const s = this.meeting()?.summary?.content ?? '';
    const match = s.match(/###?\s*(?:Key Decisions|Quyết định)[^\n]*\n([\s\S]*?)(?=###?|$)/i);
    if (!match) return [];
    return match[1].split('\n')
      .filter((l: string) => l.trim().startsWith('-') || l.trim().startsWith('*'))
      .map((l: string) => l.replace(/^[-*]\s*/, '').trim())
      .filter(Boolean)
      .slice(0, 4);
  });

  topics = computed((): string[] => {
    const s = this.meeting()?.summary?.content ?? '';
    const texts = this.segments().map(seg => seg.text).join(' ');
    // Extract topics from summary or segment keywords
    const keywords = ['AI Integration', 'LLM Latency', 'Streaming', 'User Experience', 'Q3 Roadmap'];
    if (!s && !texts) return [];
    return keywords.filter(k => (s + texts).toLowerCase().includes(k.toLowerCase())).slice(0, 6);
  });

  participantCount = computed(() => {
    const labels = new Set(this.segments().map(s => s.speaker_label ?? 'unknown'));
    return Math.max(labels.size, 1);
  });

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    this.meetingId.set(id);

    this.meetingService.get(id).subscribe(m => this.meeting.set(m));

    this.http.get<{ segments: TranscriptSegment[] }>(`/api/meetings/${id}/transcript`).subscribe({
      next: (r) => { this.segments.set(r.segments ?? []); this.loadingTranscript.set(false); },
      error: ()  => this.loadingTranscript.set(false),
    });

    this.http.get<{ actions: ActionItem[] }>(`/api/meetings/${id}/actions`).subscribe({
      next: (r) => this.actionItems.set(r.actions ?? []),
      error: ()  => {},
    });
  }

  generateSummary(): void {
    const id = this.meetingId();
    if (!id || this.loadingSummary()) return;
    this.loadingSummary.set(true);
    this.meetingService.summarize(id, 'general', 'ollama').subscribe({
      next: () => {
        this.meetingService.get(id).subscribe(m => {
          this.meeting.set(m);
          this.loadingSummary.set(false);
        });
      },
      error: () => this.loadingSummary.set(false),
    });
  }

  reprocess(): void {
    const id = this.meetingId();
    this.http.post(`/api/meetings/${id}/reprocess`, {}).subscribe();
  }

  exportMarkdown(): void {
    const m = this.meeting();
    if (!m) return;
    const content = m.summary?.content ?? this.segments().map(s =>
      `[${this.formatTime(s.start_time)}] ${s.speaker_name ?? s.speaker_label ?? 'Unknown'}: ${s.text}`
    ).join('\n');
    const blob = new Blob([content], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${m.title.replace(/\s+/g,'-')}.md`;
    a.click();
  }

  formatTime(s: number): string {
    const m = Math.floor(s / 60); const sec = Math.floor(s % 60);
    return `${m.toString().padStart(2,'0')}:${sec.toString().padStart(2,'0')}`;
  }

  formatDate(dt: string): string {
    return new Date(dt).toLocaleDateString('en-US',
      { month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit' });
  }

  formatShortDate(dt: string): string {
    return new Date(dt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  formatDurationHMS(s: number): string {
    const h = Math.floor(s / 3600); const m = Math.floor((s % 3600) / 60); const sec = s % 60;
    return `${h.toString().padStart(2,'0')}:${m.toString().padStart(2,'0')}:${sec.toString().padStart(2,'0')}`;
  }

  formatDurationShort(s: number): string {
    const h = Math.floor(s / 3600); const m = Math.floor((s % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  }

  speakerInitial(label?: string | null): string {
    if (!label) return '?';
    const words = label.trim().split(' ');
    if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
    if (label.startsWith('SPEAKER_')) return 'S' + (parseInt(label.replace(/\D/g,'')) % 10);
    return label.charAt(0).toUpperCase();
  }

  speakerIndex(label?: string | null): number {
    if (!label) return 0;
    const n = parseInt(label.replace(/\D/g,''));
    return isNaN(n) ? label.charCodeAt(0) % 6 : n % 6;
  }

  async copySegment(seg: TranscriptSegment): Promise<void> {
    await navigator.clipboard.writeText(`[${this.formatTime(seg.start_time)}] ${seg.speaker_name ?? seg.speaker_label ?? 'Unknown'}: ${seg.text}`);
  }
}

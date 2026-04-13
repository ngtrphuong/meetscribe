import {
  Component, ChangeDetectionStrategy, OnInit, OnDestroy,
  inject, signal, computed
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MeetingService } from '../../core/services/meeting.service';
import { Meeting } from '../../core/models/meeting.model';

type Filter = 'all' | 'recording' | 'processing' | 'complete';

@Component({
  selector: 'ms-meeting-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterLink, FormsModule],
  template: `
  <div class="flex h-full overflow-hidden">

    <!-- ══════ MAIN CONTENT ══════ -->
    <div class="flex-1 flex flex-col overflow-hidden" style="min-width:0">

      <!-- Header -->
      <div class="px-6 pt-5 pb-4 shrink-0 flex items-center gap-3"
           style="border-bottom:1px solid var(--ms-border)">
        <div class="flex-1">
          <h1 class="font-bold text-base" style="color:var(--ms-text)">
            Dashboard
          </h1>
          <p class="text-xs mt-0.5" style="color:var(--ms-muted)">
            Meeting intelligence overview
          </p>
        </div>
        <a routerLink="/record" class="btn btn-primary btn-sm gap-1.5">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
               stroke="white" stroke-width="2.5" stroke-linecap="round">
            <circle cx="12" cy="12" r="9"/>
            <circle cx="12" cy="12" r="4" fill="white" stroke="none"/>
          </svg>
          New Meeting
        </a>
      </div>

      <!-- Search + Filters -->
      <div class="px-6 py-3 shrink-0 flex items-center gap-2"
           style="border-bottom:1px solid var(--ms-border)">
        <div class="relative flex-1">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round"
               style="position:absolute;left:10px;top:50%;
                      transform:translateY(-50%);color:var(--ms-muted)">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input [(ngModel)]="searchQ" placeholder="Search transcripts..."
            class="input" style="padding-left:2rem;font-size:.78rem;
                                  background:var(--ms-surface-2)" />
        </div>
        <button class="chip" [class.active]="filter()==='all'"
                (click)="setFilter('all')">All Types</button>
        <button class="chip" [class.active]="filter()==='recording'"
                (click)="setFilter('recording')">Live</button>
        <button class="chip" [class.active]="filter()==='complete'"
                (click)="setFilter('complete')">Completed</button>
        <button class="chip">Last 30 Days</button>
      </div>

      <!-- Meeting list -->
      <div class="flex-1 overflow-y-auto px-6 py-4">

        @if (loading()) {
          <div class="space-y-3">
            @for (_ of [1,2,3]; track $index) {
              <div class="card p-4 space-y-2">
                <div class="skeleton h-4 w-1/2"></div>
                <div class="skeleton h-3 w-1/3"></div>
              </div>
            }
          </div>
        } @else if (filtered().length === 0) {
          <div class="flex flex-col items-center justify-center h-48 gap-3">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="1.5"
                 style="color:var(--ms-muted)">
              <rect x="2" y="7" width="20" height="14" rx="2"/>
              <path d="M16 2v5M8 2v5M2 11h20"/>
            </svg>
            <p class="text-sm" style="color:var(--ms-muted)">
              No meetings found
            </p>
            <a routerLink="/record" class="btn btn-primary btn-sm">
              Start Recording
            </a>
          </div>
        } @else {

          <!-- Date groups -->
          <div class="mb-3 date-group-label">Recent Meetings</div>
          <div class="space-y-2">
            @for (m of filtered(); track m.id) {
              <a [routerLink]="['/meetings', m.id]"
                 class="card card-hover p-4 flex items-start gap-3 block">
                <!-- Status dot -->
                <div class="mt-1 shrink-0">
                  <div [style]="statusDot(m.status)"
                       style="width:8px;height:8px;border-radius:50%"></div>
                </div>

                <div class="flex-1 min-w-0">
                  <div class="flex items-start justify-between gap-2 mb-1">
                    <span class="font-semibold text-sm truncate"
                          style="color:var(--ms-text)">{{ m.title }}</span>
                    <div class="flex items-center gap-1.5 shrink-0">
                      @if (m.status === 'recording') {
                        <span class="badge badge-live-now">
                          <span class="recording-pulse"
                                style="width:5px;height:5px;border-radius:50%;
                                       background:currentColor;display:inline-block">
                          </span>
                          LIVE NOW
                        </span>
                      }
                      @if (m.llm_provider) {
                        <span class="badge badge-enhanced-ai">
                          <svg width="7" height="7" viewBox="0 0 24 24"
                               fill="none" stroke="currentColor" stroke-width="2.5">
                            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14
                                            18.18 21.02 12 17.77 5.82 21.02
                                            7 14.14 2 9.27 8.91 8.26 12 2"/>
                          </svg>
                          AI
                        </span>
                      }
                    </div>
                  </div>

                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="text-xs" style="color:var(--ms-muted)">
                      {{ formatDate(m.started_at) }}
                    </span>
                    @if (m.duration_seconds) {
                      <span style="color:var(--ms-border-2)">·</span>
                      <span class="text-xs" style="color:var(--ms-muted)">
                        {{ formatDur(m.duration_seconds) }}
                      </span>
                    }
                    @if (m.primary_language) {
                      <span style="color:var(--ms-border-2)">·</span>
                      <span class="text-xs uppercase font-semibold"
                            style="color:var(--ms-muted)">
                        {{ m.primary_language }}
                      </span>
                    }
                    <span class="badge text-xs ml-auto"
                          [class]="'badge-' + m.status"
                          style="font-size:.6rem">
                      {{ m.status }}
                    </span>
                  </div>
                </div>
              </a>
            }
          </div>
        }
      </div>
    </div>

    <!-- ══════ RIGHT: AI HIGHLIGHTS ══════ -->
    <div class="hw-panel flex flex-col" style="width:300px">

      <!-- Panel header -->
      <div class="px-4 pt-4 pb-3 shrink-0"
           style="border-bottom:1px solid var(--ms-border)">
        <div class="flex items-center gap-2">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5"
               style="color:var(--ms-ai)">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02
                             12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
          </svg>
          <span class="text-xs font-bold tracking-wider uppercase"
                style="color:var(--ms-text)">AI Highlights</span>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto">

        <!-- Executive Summary -->
        <div class="hw-panel-section">
          <p class="section-label" style="padding:.0 0 .5rem">
            Executive Summary
          </p>
          <div class="ai-insight-card">
            <div class="ai-insight-label">
              <svg width="9" height="9" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2.5">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 8v4l3 3"/>
              </svg>
              Latest Meeting
            </div>
            <p class="text-xs leading-relaxed" style="color:var(--ms-text-2)">
              The team reached a consensus to pivot the onboarding
              strategy. A "Shadow Validation" system will leverage
              real-time AI to process compliance in the background,
              significantly reducing user drop-off.
            </p>
          </div>
        </div>

        <!-- Action Items -->
        <div class="hw-panel-section">
          <div class="flex items-center justify-between mb-3">
            <p class="section-label" style="padding:0">Action Items</p>
            <span class="badge badge-primary">3 TASKS</span>
          </div>

          <div class="mb-2 date-group-label" style="font-size:.6rem">
            Yesterday
          </div>
          <div class="dash-action">
            <div class="dash-action-dot"
                 style="background:var(--ms-ai)"></div>
            <div class="flex-1 min-w-0">
              <div class="font-medium text-xs" style="color:var(--ms-text)">
                Product Sync: Search UX
              </div>
              <div style="color:var(--ms-muted);font-size:.68rem">
                Refining semantic search algorithm
              </div>
            </div>
          </div>

          <div class="mb-2 date-group-label" style="font-size:.6rem">
            Oct 22
          </div>
          <div class="dash-action">
            <div class="dash-action-dot"
                 style="background:var(--ms-danger)"></div>
            <div class="flex-1 min-w-0">
              <div class="font-medium text-xs" style="color:var(--ms-text)">
                Security Audit: Protocol AI Core
              </div>
              <div style="color:var(--ms-muted);font-size:.68rem">
                Encryption protocols review
              </div>
            </div>
          </div>

          <div class="dash-action mt-2">
            <div class="dash-action-dot"
                 style="background:var(--ms-warning)"></div>
            <div class="flex-1 min-w-0">
              <div class="font-medium text-xs" style="color:var(--ms-text)">
                Sync with Legal Team
              </div>
              <div class="flex items-center gap-1.5 mt-0.5">
                <span style="color:var(--ms-muted);font-size:.65rem">
                  Sarah Chen
                </span>
                <span class="badge" style="font-size:.55rem;
                  background:rgba(245,158,11,.1);color:var(--ms-warning);
                  border:1px solid rgba(245,158,11,.2)">By Tuesday</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Trending Topics -->
        <div class="hw-panel-section">
          <p class="section-label" style="padding:0 0 .6rem">
            Trending Topics
          </p>
          <div class="flex flex-wrap gap-1.5">
            @for (t of trendingTopics; track t) {
              <span class="trend-chip">{{ t }}</span>
            }
          </div>
        </div>

        <!-- Hardware summary -->
        <div class="hw-panel-section">
          <p class="section-label" style="padding:0 0 .6rem">
            Hardware Status
          </p>
          <div class="node-card mb-2">
            <div class="node-dot"></div>
            <div class="flex-1 min-w-0">
              <div class="text-xs font-semibold" style="color:var(--ms-text)">
                RTX 3090
              </div>
              <div class="text-xs" style="color:var(--ms-muted)">
                Load: Optimal · {{ gpuUtil() }}% utilization
              </div>
            </div>
            <div class="text-xs font-mono font-bold"
                 style="color:var(--ms-success)">
              {{ gpuTemp() }}°C
            </div>
          </div>
          <div class="perf-grid">
            <div class="perf-card">
              <div class="perf-val">{{ vramUsed() }}<span
                style="font-size:.65rem;color:var(--ms-muted)"> GB</span></div>
              <div class="perf-lbl">VRAM</div>
            </div>
            <div class="perf-card">
              <div class="perf-val">{{ latencyMs() }}<span
                style="font-size:.65rem;color:var(--ms-muted)"> ms</span></div>
              <div class="perf-lbl">Latency</div>
            </div>
          </div>
        </div>

      </div>
    </div>

  </div>
  `,
})
export class MeetingListComponent implements OnInit, OnDestroy {
  private meetingSvc = inject(MeetingService);
  private http = inject(HttpClient);

  meetings   = signal<Meeting[]>([]);
  loading    = signal(true);
  searchQ    = '';
  filter     = signal<Filter>('all');
  gpuUtil    = signal(64);
  gpuTemp    = signal(68);
  vramUsed   = signal(6.8);
  latencyMs  = signal(124);

  private simInterval?: ReturnType<typeof setInterval>;

  trendingTopics = [
    'Middleware', 'Q4 Roadmap', 'Vector DB',
    'NVIDIA Ecosystem', 'Resource Optimization',
    'Onboarding UX',
  ];

  filtered = computed(() => {
    let list = this.meetings();
    if (this.filter() !== 'all') {
      list = list.filter(m => m.status === this.filter());
    }
    const q = this.searchQ.toLowerCase();
    if (q) list = list.filter(m => m.title.toLowerCase().includes(q));
    return list;
  });

  ngOnInit(): void {
    this.meetingSvc.list().subscribe({
      next: r  => { this.meetings.set(r.meetings ?? []); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
    this.startTelemetry();
  }

  ngOnDestroy(): void {
    if (this.simInterval) clearInterval(this.simInterval);
  }

  setFilter(f: Filter): void { this.filter.set(f); }

  private startTelemetry(): void {
    this.simInterval = setInterval(() => {
      this.gpuUtil.set(55 + Math.round(Math.random() * 25));
      this.gpuTemp.set(64 + Math.round(Math.random() * 10));
      this.vramUsed.set(+(5.5 + Math.random() * 3).toFixed(1));
      this.latencyMs.set(110 + Math.round(Math.random() * 40));
    }, 3000);
  }

  statusDot(status: string): string {
    const map: Record<string, string> = {
      recording: 'background:var(--ms-danger)',
      processing: 'background:var(--ms-warning)',
      complete: 'background:var(--ms-success)',
    };
    return map[status] ?? 'background:var(--ms-muted)';
  }

  formatDate(dt: string): string {
    return new Date(dt).toLocaleDateString('en-US',
      { month: 'short', day: 'numeric', year: 'numeric' });
  }

  formatDur(s: number): string {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m} min`;
  }
}

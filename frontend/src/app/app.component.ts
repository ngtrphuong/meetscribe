import {
  Component, ChangeDetectionStrategy, inject, signal,
  computed, OnInit, OnDestroy
} from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { RecordingService } from './core/services/recording.service';
import { TranscriptStreamService } from './core/services/transcript-stream.service';
import { ThemeService } from './core/services/theme.service';

@Component({
  selector: 'ms-root',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, CommonModule],
  template: `
  <div class="flex h-screen overflow-hidden"
       style="background:var(--ms-bg)">

    <!-- ══════════════════════ SIDEBAR ══════════════════════ -->
    <aside class="flex flex-col shrink-0"
           style="width:var(--ms-sidebar-w);background:var(--ms-surface);
                  border-right:1px solid var(--ms-border)">

      <!-- Logo -->
      <div class="px-4 py-4 flex items-center gap-2.5"
           style="border-bottom:1px solid var(--ms-border)">
        <div class="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
             style="background:linear-gradient(135deg,#6366f1,#8b5cf6)">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
               stroke="white" stroke-width="2.5" stroke-linecap="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
          </svg>
        </div>
        <div>
          <span class="font-bold text-sm tracking-tight"
                style="color:var(--ms-text)">MeetScribe</span>
          <div class="text-xs" style="color:var(--ms-muted);font-size:.6rem;
               margin-top:1px">Intelligence Platform</div>
        </div>
      </div>

      <!-- Nav -->
      <nav class="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">

        <p class="section-label">Main</p>

        <a routerLink="/meetings" routerLinkActive="active"
           [routerLinkActiveOptions]="{exact:true}" class="nav-item">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <rect x="3" y="3" width="7" height="7"/>
            <rect x="14" y="3" width="7" height="7"/>
            <rect x="14" y="14" width="7" height="7"/>
            <rect x="3" y="14" width="7" height="7"/>
          </svg>
          Dashboard
        </a>

        <a routerLink="/meetings" routerLinkActive="active" class="nav-item">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <rect x="2" y="7" width="20" height="14" rx="2"/>
            <path d="M16 2v5M8 2v5M2 11h20"/>
          </svg>
          Meetings
        </a>

        <a routerLink="/meetings" class="nav-item">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
          </svg>
          Library
        </a>

        <a routerLink="/search" routerLinkActive="active" class="nav-item">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M18 20V10M12 20V4M6 20v-6"/>
          </svg>
          Analytics
        </a>

        <a routerLink="/search" routerLinkActive="active" class="nav-item">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="11" cy="11" r="8"/>
            <path d="m21 21-4.35-4.35"/>
          </svg>
          Search
          <span class="hotkey ml-auto">⌘F</span>
        </a>

        <p class="section-label mt-3">Workspace</p>

        <a routerLink="/record" routerLinkActive="active" class="nav-item">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="10"/>
            <circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>
          </svg>
          New Meeting
          @if (isRecording()) {
            <span class="ml-auto badge badge-live-now" style="font-size:.55rem">
              <span class="recording-pulse"
                    style="width:4px;height:4px;border-radius:50%;
                           background:currentColor;display:inline-block"></span>
              LIVE
            </span>
          }
        </a>

        <a routerLink="/settings" routerLinkActive="active" class="nav-item">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M12 2v3m0 14v3M4.22 4.22l2.12 2.12m11.32 11.32
                     2.12 2.12M2 12h3m14 0h3M4.22 19.78l2.12-2.12
                     M16.66 7.34l2.12-2.12"/>
          </svg>
          Settings
        </a>

      </nav>

      <!-- Active recording card -->
      @if (isRecording() || isProcessing()) {
        <div class="mx-3 mb-3 rounded-xl p-3 fade-in"
             [style]="isRecording()
               ? 'background:rgba(244,63,94,.07);border:1px solid rgba(244,63,94,.18)'
               : 'background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.18)'">
          <div class="flex items-center gap-1.5 mb-1.5">
            @if (isRecording()) {
              <span class="recording-pulse"
                    style="width:6px;height:6px;border-radius:50%;
                           background:var(--ms-danger);flex-shrink:0"></span>
              <span class="text-xs font-bold tracking-wide"
                    style="color:var(--ms-danger)">LIVE NOW</span>
            } @else {
              <span class="spin text-xs" style="color:var(--ms-warning)">⚙</span>
              <span class="text-xs font-bold tracking-wide"
                    style="color:var(--ms-warning)">PROCESSING</span>
            }
            <span class="ml-auto elapsed-sm">{{ elapsedStr() }}</span>
          </div>
          <div class="h-1 rounded-full overflow-hidden"
               style="background:rgba(0,0,0,.25)">
            <div class="level-bar h-full"
                 [style.width.%]="levels().system * 100"></div>
          </div>
        </div>
      }

      <!-- Footer -->
      <div class="px-3 py-3"
           style="border-top:1px solid var(--ms-border)">
        <!-- Theme toggle in footer -->
        <button class="nav-item w-full mb-1"
                (click)="themeService.toggle()">
          @if (themeService.isDark()) {
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <circle cx="12" cy="12" r="5"/>
              <line x1="12" y1="1" x2="12" y2="3"/>
              <line x1="12" y1="21" x2="12" y2="23"/>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
              <line x1="1" y1="12" x2="3" y2="12"/>
              <line x1="21" y1="12" x2="23" y2="12"/>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
            Light Mode
          } @else {
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
            Dark Mode
          }
        </button>
        <a class="nav-item" style="margin-bottom:.2rem">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="10"/>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          Help Center
        </a>
        <a class="nav-item">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
          Log Out
        </a>
      </div>
    </aside>

    <!-- ══════════════════════ MAIN ══════════════════════ -->
    <main class="flex-1 overflow-hidden">
      <router-outlet />
    </main>

  </div>
  `,
})
export class AppComponent implements OnInit, OnDestroy {
  themeService = inject(ThemeService);
  private recordingService = inject(RecordingService);
  private transcriptStream = inject(TranscriptStreamService);

  private timerInterval?: ReturnType<typeof setInterval>;
  private elapsed = signal(0);

  get levels()     { return this.transcriptStream.levels; }
  isRecording  = computed(
    () => this.recordingService.recordingStatus() === 'recording'
  );
  isProcessing = computed(
    () => this.recordingService.recordingStatus() === 'processing'
  );

  elapsedStr = computed(() => {
    const s = this.elapsed();
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) {
      return `${h}:${m.toString().padStart(2,'0')}:`
           + `${sec.toString().padStart(2,'0')}`;
    }
    return `${m.toString().padStart(2,'0')}:`
         + `${sec.toString().padStart(2,'0')}`;
  });

  ngOnInit(): void {
    this.timerInterval = setInterval(() => {
      if (this.isRecording()) this.elapsed.update(s => s + 1);
      else if (!this.isProcessing()) this.elapsed.set(0);
    }, 1000);
  }

  ngOnDestroy(): void {
    if (this.timerInterval) clearInterval(this.timerInterval);
  }
}

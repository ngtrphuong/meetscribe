import {
  Component, ChangeDetectionStrategy, inject, signal, ElementRef, viewChild
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { MeetingService } from '../../core/services/meeting.service';

@Component({
  selector: 'ms-search-bar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="p-6 max-w-3xl mx-auto">

      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-2xl font-bold" style="color:var(--ms-text)">Tìm kiếm</h1>
        <p class="text-sm mt-1" style="color:var(--ms-muted)">
          Tìm kiếm nội dung trong tất cả bản ghi cuộc họp
        </p>
      </div>

      <!-- Search form -->
      <div class="flex gap-2 mb-3">
        <div class="relative flex-1">
          <div class="absolute inset-y-0 left-3 flex items-center pointer-events-none">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                 style="color:var(--ms-muted)">
              <circle cx="11" cy="11" r="8"/>
              <path d="m21 21-4.35-4.35"/>
            </svg>
          </div>
          <input
            #searchInput
            [(ngModel)]="query"
            (keyup.enter)="search()"
            placeholder="Tìm trong bản ghi cuộc họp…"
            class="input pl-10"
          />
        </div>
        <select [(ngModel)]="searchType" class="input" style="width:auto;min-width:120px">
          <option value="fts">Từ khoá</option>
          <option value="semantic">AI (ngữ nghĩa)</option>
        </select>
        <button
          (click)="search()"
          [disabled]="!query.trim() || loading()"
          class="btn btn-primary"
        >
          @if (loading()) {
            <span class="spin-slow inline-block">⚙</span>
          } @else {
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/>
              <path d="m21 21-4.35-4.35"/>
            </svg>
          }
          Tìm
        </button>
      </div>

      <!-- Search type hint -->
      <p class="text-xs mb-6" style="color:var(--ms-muted)">
        @if (searchType === 'fts') {
          Tìm kiếm từ khoá chính xác trong bản ghi (FTS5)
        } @else {
          Tìm kiếm theo ngữ nghĩa bằng AI embedding (all-MiniLM-L6-v2)
        }
      </p>

      <!-- Loading -->
      @if (loading()) {
        <div class="space-y-3">
          @for (_ of [1,2,3]; track $index) {
            <div class="card p-4">
              <div class="skeleton h-3 w-1/4 rounded mb-2"></div>
              <div class="skeleton h-4 w-3/4 rounded mb-2"></div>
              <div class="skeleton h-3 w-1/3 rounded"></div>
            </div>
          }
        </div>
      }

      <!-- Results -->
      @else if (results().length > 0) {
        <div class="mb-3 text-xs" style="color:var(--ms-muted)">
          {{ results().length }} kết quả cho "{{ lastQuery() }}"
        </div>
        <div class="space-y-2">
          @for (result of results(); track result.id) {
            <a
              [routerLink]="['/meetings', result.meeting_id]"
              class="card card-hover block p-4 no-underline fade-in"
            >
              <!-- Meeting title breadcrumb -->
              <div class="flex items-center gap-1.5 mb-2">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                     style="color:var(--ms-primary)">
                  <rect x="2" y="7" width="20" height="14" rx="2"/>
                  <path d="M16 2v5M8 2v5M2 11h20"/>
                </svg>
                <span class="text-xs font-medium" style="color:var(--ms-primary)">
                  {{ result.meeting_title }}
                </span>
              </div>

              <!-- Transcript text -->
              <p class="text-sm leading-relaxed mb-2" style="color:var(--ms-text)">
                {{ result.text }}
              </p>

              <!-- Metadata -->
              <div class="flex items-center gap-3 text-xs" style="color:var(--ms-muted)">
                @if (result.speaker_name ?? result.speaker_label) {
                  <span class="flex items-center gap-1">
                    <span class="w-2 h-2 rounded-full"
                          style="background:var(--ms-primary);opacity:0.6"></span>
                    {{ result.speaker_name ?? result.speaker_label }}
                  </span>
                }
                <span>{{ formatTime(result.start_time) }}</span>
                @if (result.similarity) {
                  <span class="ml-auto" style="color:var(--ms-accent)">
                    {{ (result.similarity * 100).toFixed(0) }}% tương đồng
                  </span>
                }
              </div>
            </a>
          }
        </div>
      }

      <!-- Empty state -->
      @else if (searched()) {
        <div class="flex flex-col items-center justify-center py-16 text-center">
          <div class="w-12 h-12 rounded-xl flex items-center justify-center mb-3"
               style="background:var(--ms-surface-2)">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
                 style="color:var(--ms-muted)">
              <circle cx="11" cy="11" r="8"/>
              <path d="m21 21-4.35-4.35"/>
            </svg>
          </div>
          <p class="text-sm font-medium mb-1" style="color:var(--ms-text)">
            Không tìm thấy kết quả
          </p>
          <p class="text-xs" style="color:var(--ms-muted)">
            Thử từ khoá khác hoặc chuyển sang tìm kiếm AI
          </p>
        </div>
      }

      <!-- Initial state -->
      @else {
        <div class="flex flex-col items-center justify-center py-16 text-center">
          <div class="w-12 h-12 rounded-xl flex items-center justify-center mb-3"
               style="background:var(--ms-surface-2)">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
                 style="color:var(--ms-muted)">
              <circle cx="11" cy="11" r="8"/>
              <path d="m21 21-4.35-4.35"/>
            </svg>
          </div>
          <p class="text-sm" style="color:var(--ms-muted)">
            Nhập từ khoá để tìm trong bản ghi cuộc họp
          </p>
        </div>
      }
    </div>
  `,
})
export class SearchBarComponent {
  private meetingService = inject(MeetingService);

  query = '';
  searchType: 'fts' | 'semantic' = 'fts';

  results = signal<any[]>([]);
  loading = signal(false);
  searched = signal(false);
  lastQuery = signal('');

  search(): void {
    if (!this.query.trim()) return;
    this.loading.set(true);
    this.searched.set(false);
    this.lastQuery.set(this.query);

    this.meetingService.search(this.query, this.searchType).subscribe({
      next: (res) => {
        this.results.set(res.results ?? []);
        this.loading.set(false);
        this.searched.set(true);
      },
      error: () => {
        this.results.set([]);
        this.loading.set(false);
        this.searched.set(true);
      },
    });
  }

  formatTime(s: number): string {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
  }
}

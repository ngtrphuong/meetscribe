/**
 * Consent dialog — MUST appear before recording begins (Decree 356).
 * Two checkboxes: consent_recording + consent_voiceprint.
 */
import {
  Component, ChangeDetectionStrategy, Output, EventEmitter
} from '@angular/core';
import { FormsModule } from '@angular/forms';

export interface ConsentResult {
  recording: boolean;
  voiceprint: boolean;
}

@Component({
  selector: 'ms-consent-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule],
  template: `
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4"
         style="background:rgba(3,7,18,0.85);backdrop-filter:blur(8px)">
      <div class="glass rounded-2xl max-w-md w-full p-8 shadow-2xl fade-in">

        <!-- Icon -->
        <div class="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
             style="background:rgba(99,102,241,0.15)">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
               style="color:var(--ms-primary)">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>

        <h2 class="text-xl font-bold mb-2" style="color:var(--ms-text)">
          Xác nhận thu âm
        </h2>
        <p class="text-sm leading-relaxed mb-7" style="color:var(--ms-muted)">
          Theo <strong style="color:var(--ms-text)">Nghị định 356/2025</strong>,
          bạn cần đọc và đồng ý với các điều khoản dưới đây trước khi bắt đầu ghi âm.
          Dữ liệu được xử lý hoàn toàn trên thiết bị của bạn.
        </p>

        <div class="space-y-4 mb-8">
          <!-- Consent recording -->
          <label class="flex items-start gap-3 cursor-pointer rounded-xl p-3 transition-colors"
                 style="background:var(--ms-surface-2)">
            <input
              type="checkbox"
              [(ngModel)]="consentRecording"
              class="mt-0.5 shrink-0 cursor-pointer"
              style="width:18px;height:18px;accent-color:var(--ms-primary)"
            />
            <div>
              <div class="text-sm font-semibold" style="color:var(--ms-text)">
                Đồng ý ghi âm cuộc họp
              </div>
              <div class="text-xs mt-1 leading-relaxed" style="color:var(--ms-muted)">
                Âm thanh được xử lý và ghi lại. File WAV chỉ được lưu nếu bạn bật tuỳ chọn giữ lại.
              </div>
            </div>
          </label>

          <!-- Consent voiceprint -->
          <label class="flex items-start gap-3 cursor-pointer rounded-xl p-3 transition-colors"
                 style="background:var(--ms-surface-2)">
            <input
              type="checkbox"
              [(ngModel)]="consentVoiceprint"
              class="mt-0.5 shrink-0 cursor-pointer"
              style="width:18px;height:18px;accent-color:var(--ms-primary)"
            />
            <div>
              <div class="text-sm font-semibold" style="color:var(--ms-text)">
                Đồng ý nhận diện giọng nói (Voiceprint)
              </div>
              <div class="text-xs mt-1 leading-relaxed" style="color:var(--ms-muted)">
                Đặc trưng giọng nói được mã hoá AES-256. Bạn có thể xoá bất kỳ lúc nào theo
                quyền chủ thể dữ liệu.
              </div>
            </div>
          </label>
        </div>

        <!-- Actions -->
        <div class="flex gap-3">
          <button (click)="cancel()" class="btn btn-ghost flex-1">
            Huỷ
          </button>
          <button
            (click)="confirm()"
            class="btn btn-primary flex-1"
            [style.opacity]="consentRecording ? 1 : 0.5"
            [disabled]="!consentRecording"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/>
            </svg>
            Bắt đầu ghi âm
          </button>
        </div>

        <p class="text-center text-xs mt-4" style="color:var(--ms-muted)">
          Bạn phải đồng ý ghi âm để tiếp tục.
        </p>
      </div>
    </div>
  `,
})
export class ConsentDialogComponent {
  consentRecording = false;
  consentVoiceprint = false;

  @Output() confirmed = new EventEmitter<ConsentResult>();
  @Output() cancelled = new EventEmitter<void>();

  confirm(): void {
    if (!this.consentRecording) return;
    this.confirmed.emit({
      recording: this.consentRecording,
      voiceprint: this.consentVoiceprint,
    });
  }

  cancel(): void {
    this.cancelled.emit();
  }
}

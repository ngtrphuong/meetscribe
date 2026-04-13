/**
 * Tray icon state management (exported helpers for main.ts).
 * Tray colours: green=idle, red=recording, blue=processing.
 */

export type TrayState = 'idle' | 'recording' | 'processing';

export function getTrayIconName(state: TrayState): string {
  switch (state) {
    case 'recording': return 'tray-recording.png';   // Red dot
    case 'processing': return 'tray-processing.png'; // Blue spinner
    default: return 'tray-idle.png';                  // Green dot
  }
}

export function getTrayTooltip(state: TrayState): string {
  switch (state) {
    case 'recording': return 'MeetScribe — Đang ghi âm';
    case 'processing': return 'MeetScribe — Đang xử lý';
    default: return 'MeetScribe — Sẵn sàng';
  }
}

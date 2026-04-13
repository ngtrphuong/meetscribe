import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'meetings',
    pathMatch: 'full',
  },
  {
    path: 'meetings',
    loadComponent: () =>
      import('./features/meetings/meeting-list.component').then(m => m.MeetingListComponent),
    title: 'Cuộc họp — MeetScribe',
  },
  {
    path: 'record',
    loadComponent: () =>
      import('./features/recording/recording-controls.component').then(m => m.RecordingControlsComponent),
    title: 'Ghi âm — MeetScribe',
  },
  {
    path: 'meetings/:id',
    loadComponent: () =>
      import('./features/transcript/live-transcript.component').then(m => m.LiveTranscriptComponent),
    title: 'Bản ghi — MeetScribe',
  },
  {
    path: 'meetings/:id/summary',
    loadComponent: () =>
      import('./features/summary/summary-view.component').then(m => m.SummaryViewComponent),
    title: 'Tóm tắt — MeetScribe',
  },
  {
    path: 'search',
    loadComponent: () =>
      import('./features/search/search-bar.component').then(m => m.SearchBarComponent),
    title: 'Tìm kiếm — MeetScribe',
  },
  {
    path: 'settings',
    loadComponent: () =>
      import('./features/settings/settings-panel.component').then(m => m.SettingsPanelComponent),
    title: 'Cài đặt — MeetScribe',
  },
  {
    path: '**',
    redirectTo: 'meetings',
  },
];

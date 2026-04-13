import { ApplicationConfig, provideZonelessChangeDetection } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { apiBaseInterceptor } from './core/interceptors/api-base.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    // Zoneless — no zone.js (CLAUDE.md §8.3)
    provideZonelessChangeDetection(),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withInterceptors([apiBaseInterceptor])),
  ],
};

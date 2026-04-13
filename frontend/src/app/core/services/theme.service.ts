import { Injectable, signal, computed, effect } from '@angular/core';

export type Theme = 'dark' | 'light';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private _theme = signal<Theme>(this.getSavedTheme());

  readonly theme = this._theme.asReadonly();
  readonly isDark = computed(() => this._theme() === 'dark');
  readonly isLight = computed(() => this._theme() === 'light');

  constructor() {
    // Apply saved theme on init
    this.applyTheme(this._theme());
    // Persist on change
    effect(() => {
      const t = this._theme();
      localStorage.setItem('ms-theme', t);
      this.applyTheme(t);
    });
  }

  toggle(): void {
    this._theme.update(t => t === 'dark' ? 'light' : 'dark');
  }

  setTheme(t: Theme): void {
    this._theme.set(t);
  }

  private getSavedTheme(): Theme {
    const saved = localStorage.getItem('ms-theme');
    return saved === 'light' || saved === 'dark' ? saved : 'dark';
  }

  private applyTheme(t: Theme): void {
    document.documentElement.setAttribute('data-theme', t);
  }
}

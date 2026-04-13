/**
 * Screen 3 — Settings (Protocol AI design)
 * Left:  ASR Engine Selection, LLM Providers, Compliance
 * Right: System Performance metrics, Node Health, Compute Core
 * Footer: SAVE, RESET, HISTORY, DISCARD
 */
import {
  Component, ChangeDetectionStrategy, OnInit, OnDestroy,
  inject, signal
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

interface AsrEngine {
  id: string; label: string; latency: string;
  accuracy: string; enabled: boolean; active: boolean;
}

interface LlmProvider {
  id: string; icon: string; iconBg: string;
  label: string; endpoint: string; selected: boolean;
}

type SettingsTab = 'engines' | 'llm' | 'compliance' | 'audio';

@Component({
  selector: 'ms-settings-panel',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule],
  template: `
  <div class="flex flex-col" style="height:100vh">

    <!-- ══════════ HEADER ══════════ -->
    <div class="px-6 py-4 shrink-0 flex items-center gap-3"
         style="background:var(--ms-surface);
                border-bottom:1px solid var(--ms-border)">
      <div class="flex-1">
        <h1 class="font-bold text-sm" style="color:var(--ms-text)">
          Settings
        </h1>
        <p class="text-xs mt-0.5" style="color:var(--ms-muted)">
          Configure your computational stack, ASR models,
          and LLM infrastructure.
        </p>
      </div>
      <div class="flex items-center gap-2.5 px-3 py-1.5 rounded-full"
           style="background:var(--ms-surface-2);
                  border:1px solid var(--ms-border)">
        <div class="w-6 h-6 rounded-full flex items-center justify-center
                    text-white text-xs font-bold"
             style="background:linear-gradient(135deg,#6366f1,#8b5cf6)">
          A
        </div>
        <div>
          <div class="text-xs font-semibold"
               style="color:var(--ms-text)">Alex Sterling</div>
          <div class="text-xs" style="color:var(--ms-muted)">CTO</div>
        </div>
        <span class="badge badge-executive">Executive Suite</span>
      </div>
    </div>

    <!-- ══════════ BODY ══════════ -->
    <div class="flex flex-1 overflow-hidden">

      <!-- ── LEFT SETTINGS PANEL ── -->
      <div class="flex flex-col overflow-hidden" style="flex:1;min-width:0">

        <!-- Tab nav -->
        <div class="flex gap-1 px-5 pt-4 pb-0 shrink-0">
          @for (tab of tabs; track tab.key) {
            <button class="px-3 py-1.5 rounded-t text-xs font-semibold
                           transition-all"
                    [style]="activeTab() === tab.key
                      ? 'background:var(--ms-surface-2);color:var(--ms-text);'
                        + 'border:1px solid var(--ms-border);'
                        + 'border-bottom:1px solid var(--ms-surface-2);'
                        + 'position:relative;z-index:1'
                      : 'color:var(--ms-muted)'"
                    (click)="activeTab.set(tab.key)">
              {{ tab.label }}
            </button>
          }
        </div>

        <div class="flex-1 overflow-y-auto px-5 pt-3 pb-4"
             style="border-top:1px solid var(--ms-border);margin-top:-1px">

          <!-- ─ ASR Engine Selection ─ -->
          @if (activeTab() === 'engines') {
            <p class="text-xs font-semibold mb-1"
               style="color:var(--ms-text)">ASR Engine Selection</p>
            <p class="text-xs mb-3" style="color:var(--ms-muted)">
              Configure active automatic speech recognition models
              for various locales.
            </p>

            <p class="section-label" style="padding:0 0 .5rem">
              Compute Core
            </p>
            @for (e of engines(); track e.id) {
              <div class="engine-row" [class.active]="e.enabled">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="text-xs font-semibold"
                          style="color:var(--ms-text)">{{ e.label }}</span>
                    @if (e.active) {
                      <span class="badge badge-live-now"
                            style="font-size:.55rem">ACTIVE</span>
                    }
                  </div>
                  <div class="flex items-center gap-2 mt-0.5">
                    <span class="text-xs"
                          style="color:var(--ms-muted)">{{ e.latency }}</span>
                    <span style="color:var(--ms-border-2)">·</span>
                    <span class="text-xs font-semibold"
                          style="color:var(--ms-success)">
                      {{ e.accuracy }}
                    </span>
                  </div>
                </div>
                <div class="toggle-track shrink-0"
                     [class.on]="e.enabled"
                     (click)="toggleEngine(e.id)">
                  <div class="toggle-thumb"></div>
                </div>
              </div>
            }

            <p class="section-label" style="padding:.75rem 0 .4rem">
              Language Support
            </p>
            <div class="flex flex-wrap gap-1.5">
              @for (lang of languages; track lang) {
                <span class="trend-chip">{{ lang }}</span>
              }
            </div>
          }

          <!-- ─ LLM Providers ─ -->
          @if (activeTab() === 'llm') {
            <p class="text-xs font-semibold mb-1"
               style="color:var(--ms-text)">LLM Providers</p>
            <p class="text-xs mb-3" style="color:var(--ms-muted)">
              Manage API keys and local hosting endpoints for
              large language models.
            </p>

            @for (p of llmProviders(); track p.id) {
              <div class="llm-row" [class.selected]="p.selected"
                   (click)="selectLlm(p.id)">
                <div class="llm-icon"
                     [style]="'background:' + p.iconBg +
                              ';color:white'">
                  {{ p.icon }}
                </div>
                <div class="flex-1 min-w-0">
                  <div class="text-xs font-semibold"
                       style="color:var(--ms-text)">{{ p.label }}</div>
                  <div class="text-xs truncate"
                       style="color:var(--ms-muted)">{{ p.endpoint }}</div>
                </div>
                @if (p.selected) {
                  <svg width="12" height="12" viewBox="0 0 24 24"
                       fill="none" stroke="currentColor"
                       stroke-width="2.5" stroke-linecap="round"
                       style="color:var(--ms-primary-h);flex-shrink:0">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                }
              </div>
            }
            <button class="btn btn-ghost btn-sm mt-2 w-full">
              + ADD NEW PROVIDER
            </button>
          }

          <!-- ─ Compliance ─ -->
          @if (activeTab() === 'compliance') {
            <p class="text-xs font-semibold mb-1"
               style="color:var(--ms-text)">
              Compliance &amp; Governance
            </p>
            <p class="text-xs mb-3" style="color:var(--ms-muted)">
              Data residency, audit logging, and Vietnam Decree 356.
            </p>
            <div class="space-y-2.5">
              <div class="compliance-card">
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <div class="text-xs font-semibold mb-0.5"
                         style="color:var(--ms-text)">Data Residency</div>
                    <div class="text-xs" style="color:var(--ms-muted)">
                      Ensure all processed meeting data stays within
                      your geographical region.
                    </div>
                  </div>
                  <span class="badge badge-soc2 shrink-0">EU</span>
                </div>
                <div class="text-xs mt-1.5 font-semibold"
                     style="color:var(--ms-text-3)">
                  European Union (Frankfurt)
                </div>
                <div class="text-xs mt-0.5"
                     style="color:var(--ms-muted)">
                  Retention Period: 365 days
                </div>
              </div>

              <div class="compliance-card">
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <div class="text-xs font-semibold mb-0.5"
                         style="color:var(--ms-text)">Audit Logging</div>
                    <div class="text-xs" style="color:var(--ms-muted)">
                      Comprehensive tracking of all model invocations
                      and administrative changes.
                    </div>
                  </div>
                  <button class="btn btn-ghost btn-sm shrink-0">
                    VIEW LOGS
                  </button>
                </div>
              </div>

              <div class="compliance-card">
                <div class="text-xs font-semibold mb-1"
                     style="color:var(--ms-text)">Vietnam Decree 356</div>
                <div class="text-xs mb-2" style="color:var(--ms-muted)">
                  Biometric data classified as sensitive.
                  Voiceprints stored AES-256 encrypted.
                </div>
                <div class="flex items-center gap-2">
                  <div class="node-dot"
                       style="width:6px;height:6px"></div>
                  <span class="text-xs font-semibold"
                        style="color:var(--ms-success)">Compliant</span>
                </div>
              </div>
            </div>
          }

          <!-- ─ Audio ─ -->
          @if (activeTab() === 'audio') {
            <p class="text-xs font-semibold mb-1"
               style="color:var(--ms-text)">Audio Interface</p>
            <div class="space-y-3 mt-3">
              <div>
                <label class="section-label"
                       style="padding:0 0 .4rem">Input Device</label>
                <select class="input" [(ngModel)]="audioIn">
                  <option value="default">Default Microphone</option>
                  <option value="system">System Loopback</option>
                </select>
              </div>
              <div>
                <label class="section-label"
                       style="padding:0 0 .4rem">Output Device</label>
                <select class="input" [(ngModel)]="audioOut">
                  <option value="default">Default Output</option>
                  <option value="hdmi">HDMI Audio</option>
                </select>
              </div>
              <div>
                <label class="section-label"
                       style="padding:0 0 .4rem">
                  Signal Gain: {{ gainDb() }} dB
                </label>
                <input type="range" min="-20" max="20" step="1"
                       [value]="gainDb()"
                       (input)="gainDb.set(+$any($event.target).value)"
                       class="w-full"
                       style="accent-color:var(--ms-primary)"/>
              </div>
            </div>
          }

        </div>
      </div>

      <!-- ── RIGHT: TELEMETRY ── -->
      <div class="hw-panel flex flex-col" style="width:300px">

        <!-- System Performance -->
        <div class="hw-panel-section">
          <p class="section-label" style="padding:0 0 .65rem">
            System Performance
          </p>

          <!-- GPU Ring gauge -->
          <div class="flex items-center gap-3 mb-3">
            <div class="relative shrink-0"
                 style="width:80px;height:80px">
              <svg width="80" height="80" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="30" fill="none"
                        stroke="var(--ms-surface-3)" stroke-width="7"/>
                <circle cx="40" cy="40" r="30" fill="none"
                        stroke="var(--ms-primary)" stroke-width="7"
                        stroke-linecap="round"
                        stroke-dasharray="188.5"
                        [attr.stroke-dashoffset]="
                          188.5 * (1 - gpuUtil() / 100)"
                        transform="rotate(-90 40 40)"
                        style="transition:stroke-dashoffset .6s ease"/>
              </svg>
              <div style="position:absolute;inset:0;display:flex;
                          flex-direction:column;align-items:center;
                          justify-content:center">
                <span class="mono font-bold"
                      style="font-size:.9rem;color:var(--ms-text);
                             line-height:1">
                  {{ gpuUtil() }}%
                </span>
                <span style="font-size:.52rem;color:var(--ms-muted);
                             text-transform:uppercase;
                             letter-spacing:.06em">GPU</span>
              </div>
            </div>
            <div class="flex-1">
              <div class="text-xs font-semibold mb-0.5"
                   style="color:var(--ms-text)">RTX 3090</div>
              <div class="text-xs" style="color:var(--ms-muted)">
                UTILIZATION: {{ gpuUtil() }}%
              </div>
              <div class="text-xs" style="color:var(--ms-muted)">
                TEMP: {{ gpuTemp() }}°C
              </div>
              <div class="mt-1">
                <span class="badge"
                      style="font-size:.55rem;
                             background:rgba(34,197,94,.08);
                             color:var(--ms-success);
                             border:1px solid rgba(34,197,94,.2)">
                  Optimal
                </span>
              </div>
            </div>
          </div>

          <!-- 4-metric grid -->
          <div class="perf-grid">
            <div class="perf-card">
              <div class="perf-val">{{ cpuPct() }}<span
                style="font-size:.6rem;color:var(--ms-muted)">%</span>
              </div>
              <div class="perf-lbl">CPU Load</div>
            </div>
            <div class="perf-card">
              <div class="perf-val">{{ vramGb() }}<span
                style="font-size:.6rem;color:var(--ms-muted)"> GB</span>
              </div>
              <div class="perf-lbl">VRAM Usage</div>
            </div>
            <div class="perf-card">
              <div class="perf-val">{{ latMs() }}<span
                style="font-size:.6rem;color:var(--ms-muted)"> ms</span>
              </div>
              <div class="perf-lbl">Latency (ms)</div>
            </div>
            <div class="perf-card">
              <div class="perf-val">{{ gpuTemp() }}<span
                style="font-size:.6rem;color:var(--ms-muted)">°C</span>
              </div>
              <div class="perf-lbl">Temperature</div>
            </div>
          </div>
        </div>

        <!-- Node Health -->
        <div class="hw-panel-section">
          <p class="section-label" style="padding:0 0 .65rem">
            Real-Time Node Health
          </p>
          <div class="node-card mb-3">
            <div class="node-dot"></div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5 mb-0.5">
                <span class="text-xs font-bold"
                      style="color:var(--ms-text)">NODE-01</span>
                <span class="badge"
                      style="font-size:.53rem;
                             background:rgba(34,197,94,.08);
                             color:var(--ms-success);
                             border:1px solid rgba(34,197,94,.2)">
                  ACTIVE
                </span>
                <span class="badge badge-soc2"
                      style="font-size:.53rem">STABLE</span>
              </div>
              <div class="text-xs" style="color:var(--ms-muted)">
                Connected via Fiber-Z
              </div>
              <div class="text-xs" style="color:var(--ms-muted)">
                US-EAST-01
              </div>
            </div>
          </div>

          <div class="mb-2.5">
            <div class="flex justify-between mb-1">
              <span class="text-xs" style="color:var(--ms-muted)">
                Inference Latency
              </span>
              <span class="text-xs mono font-semibold"
                    style="color:var(--ms-text)">{{ latMs() }}ms</span>
            </div>
            <div class="progress">
              <div class="progress-bar"
                   [style.width.%]="clamp(latMs() / 3, 0, 100)">
              </div>
            </div>
          </div>

          <div>
            <div class="flex justify-between mb-1">
              <span class="text-xs" style="color:var(--ms-muted)">
                Processing Queue
              </span>
              <span class="badge"
                    style="font-size:.55rem;
                           background:rgba(34,197,94,.08);
                           color:var(--ms-success);
                           border:1px solid rgba(34,197,94,.2)">
                OPTIMAL
              </span>
            </div>
            <div class="progress">
              <div class="progress-bar progress-green"
                   style="width:12%"></div>
            </div>
          </div>
        </div>

        <!-- VRAM allocation -->
        <div class="hw-panel-section">
          <p class="section-label" style="padding:0 0 .65rem">
            VRAM Allocation
          </p>
          <div class="flex justify-between mb-1">
            <span class="text-xs" style="color:var(--ms-muted)">
              {{ vramGb() }} GB / 24 GB used
            </span>
            <span class="text-xs mono" style="color:var(--ms-text-3)">
              {{ (vramGb() / 24 * 100).toFixed(0) }}%
            </span>
          </div>
          <div class="h-2 rounded-full overflow-hidden"
               style="background:var(--ms-surface-3)">
            <div class="h-full rounded-full"
                 [style]="'width:' + (vramGb()/24*100).toFixed(0) + '%;'
                          + 'background:linear-gradient(90deg,'
                          + 'var(--ms-primary),var(--ms-ai));'
                          + 'transition:width .6s ease'">
            </div>
          </div>
          <div class="flex justify-between mt-2">
            @for (m of vramModels; track m.name) {
              <div class="text-xs">
                <div class="flex items-center gap-1 mb-0.5">
                  <div style="width:5px;height:5px;border-radius:50%"
                       [style.background]="m.color"></div>
                  <span style="color:var(--ms-text-3)">{{ m.name }}</span>
                </div>
                <span class="mono"
                      style="color:var(--ms-muted)">{{ m.gb }} GB</span>
              </div>
            }
          </div>
        </div>

      </div><!-- /telemetry -->

    </div><!-- /body -->

    <!-- ══════════ FOOTER ══════════ -->
    <div class="settings-footer shrink-0">
      <button class="btn btn-primary btn-sm">SAVE</button>
      <button class="btn btn-ghost btn-sm">RESET</button>
      <button class="btn btn-ghost btn-sm">HISTORY</button>
      <div class="flex-1"></div>
      <button class="btn btn-danger btn-sm">DISCARD</button>
    </div>

  </div>
  `,
})
export class SettingsPanelComponent implements OnInit, OnDestroy {
  private http = inject(HttpClient);

  activeTab = signal<SettingsTab>('engines');
  audioIn   = 'default';
  audioOut  = 'default';
  gainDb    = signal(0);
  gpuUtil   = signal(64);
  gpuTemp   = signal(68);
  vramGb    = signal(6.8);
  cpuPct    = signal(14.2);
  latMs     = signal(124);

  private simInterval?: ReturnType<typeof setInterval>;

  tabs: { key: SettingsTab; label: string }[] = [
    { key: 'engines',    label: 'Engine Management' },
    { key: 'llm',        label: 'LLM Providers' },
    { key: 'compliance', label: 'Compliance' },
    { key: 'audio',      label: 'Audio' },
  ];

  languages = [
    'English Global', 'Vietnamese (VI)', 'Spanish (ES)',
    'French (FR)', 'German (DE)', 'Japanese (JP)',
    'Mandarin (ZH)', 'Portuguese (BR)', 'Hindi (HI)',
    'Dutch (NL)', 'Italian (IT)',
  ];

  vramModels = [
    { name: 'Parakeet', gb: 2.0, color: '#6366f1' },
    { name: 'diart',    gb: 2.0, color: '#22d3ee' },
    { name: 'Qwen3',    gb: 5.0, color: '#a78bfa' },
  ];

  engines = signal<AsrEngine[]>([
    { id: 'parakeet-vi',    label: 'Parakeet-Vi Large',
      latency: '~80ms',  accuracy: '97.2%',
      enabled: true,  active: true },
    { id: 'faster-whisper', label: 'Whisper v3-Large',
      latency: '~120ms', accuracy: '96.5%',
      enabled: true,  active: false },
    { id: 'whisper-turbo',  label: 'Whisper v3-Turbo',
      latency: '~40ms',  accuracy: '94.1%',
      enabled: false, active: false },
    { id: 'conformer-2',    label: 'Conformer-2',
      latency: '~95ms',  accuracy: '95.8%',
      enabled: false, active: false },
    { id: 'vibevoice',      label: 'VibeVoice-ASR 7B',
      latency: '~200ms', accuracy: '98.1%',
      enabled: true,  active: false },
    { id: 'phowhisper',     label: 'PhoWhisper Large',
      latency: '~150ms', accuracy: '96.0%',
      enabled: false, active: false },
    { id: 'nemo-para',      label: 'Nemo-Para',
      latency: '~110ms', accuracy: '95.3%',
      enabled: false, active: false },
    { id: 'kaldi-base',     label: 'Kaldi Base',
      latency: '~35ms',  accuracy: '88.5%',
      enabled: false, active: false },
  ]);

  llmProviders = signal<LlmProvider[]>([
    { id: 'openai', icon: 'O', iconBg: '#f97316',
      label: 'OpenAI GPT-4o',
      endpoint: 'api.openai.com/v1', selected: false },
    { id: 'claude', icon: 'A', iconBg: '#22d3ee',
      label: 'Anthropic Claude 3.5',
      endpoint: 'api.anthropic.com/v1', selected: false },
    { id: 'ollama', icon: 'L', iconBg: '#8b5cf6',
      label: 'Local Llama 3 (8B)',
      endpoint: 'Self-Hosted: localhost:11434', selected: true },
  ]);

  ngOnInit(): void {
    this.loadSettings();
    this.simInterval = setInterval(() => {
      this.gpuUtil.set(55 + Math.round(Math.random() * 25));
      this.gpuTemp.set(64 + Math.round(Math.random() * 10));
      this.vramGb.set(+(5.5 + Math.random() * 3).toFixed(1));
      this.cpuPct.set(+(10 + Math.random() * 15).toFixed(1));
      this.latMs.set(100 + Math.round(Math.random() * 50));
    }, 4000);
  }

  ngOnDestroy(): void {
    if (this.simInterval) clearInterval(this.simInterval);
  }

  private loadSettings(): void {
    this.http.get<any>('/api/settings').subscribe({
      next: (cfg) => {
        this.llmProviders.update(list =>
          list.map(p => ({
            ...p,
            selected: p.id === cfg.llm_provider,
          }))
        );
      },
      error: () => {},
    });
  }

  toggleEngine(id: string): void {
    this.engines.update(list =>
      list.map(e => e.id === id ? { ...e, enabled: !e.enabled } : e)
    );
  }

  selectLlm(id: string): void {
    this.llmProviders.update(list =>
      list.map(p => ({ ...p, selected: p.id === id }))
    );
  }

  clamp(v: number, min: number, max: number): number {
    return Math.min(Math.max(v, min), max);
  }
}

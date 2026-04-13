# MeetScribe — Claude Code Master Instructions

> **This file is the single source of truth.** Claude Code reads this FIRST before any task.
> Every architectural decision, file location, coding pattern, and constraint is documented here.
> When in doubt, follow this file. When this file conflicts with other docs, this file wins.

---

## 1. PROJECT IDENTITY

**Name:** MeetScribe
**Purpose:** Vietnamese-first, AI-native meeting intelligence platform — captures, transcribes, diarizes, and summarizes meetings in real-time on local GPU hardware.
**License:** MIT (open source, personal + team use at TMA Solutions)
**Primary Language:** Vietnamese (vi), Secondary: English (en), Code-switching: VN↔EN supported
**Privacy:** Local-first. Biometric data (voiceprints) classified as sensitive under Vietnam Decree 356/2025.

---

## 2. ARCHITECTURE OVERVIEW

MeetScribe uses a **dual-mode** pipeline:

```
LIVE MODE (during meeting):
  Audio Capture → Maxine Preprocessing → Language Detection
    → Vietnamese: Parakeet-CTC-0.6B-Vi via SimulStreaming
    → English: faster-whisper large-v3 via SimulStreaming
  + diart (real-time speaker diarization, 500ms updates)
  → WebSocket → Angular/Electron/Flutter/IoT clients

POST MODE (after meeting ends):
  Full WAV → VibeVoice-ASR 7B (single-pass: ASR + diarization + timestamps)
  → Structured JSON [{Start, End, Speaker, Content}]
  → LLM Summarizer (Ollama Qwen3 or Claude API)
  → Structured meeting notes (decisions, action items, follow-ups)
  → Replace LIVE transcript with POST transcript in database
```

**Multi-platform clients share the same backend:**
```
                    FastAPI Backend (localhost:9876)
                    ├── REST API (/api/*)
                    ├── WebSocket (/ws/transcript/{id})
                    └── Static files (Angular build)
                         │
            ┌────────────┼────────────┬─────────────┐
            ▼            ▼            ▼             ▼
      Angular Web   Electron     Flutter        IoT/RPi
      (browser)     Desktop      Mobile         (WebSocket
                    (Win/Mac/    (iOS/Android)   audio stream)
                     Linux)
```

---

## 3. TECHNOLOGY STACK

### 3.1 Backend — Python 3.11+

| Component | Package/Tool | Version | Purpose |
|-----------|-------------|---------|---------|
| API Server | fastapi | >=0.115 | REST + WebSocket server |
| Event Loop | uvloop | latest | Replace asyncio event loop (Linux) |
| Serialization | orjson | latest | Fast JSON via ORJSONResponse |
| ASGI Server | uvicorn | latest | Production ASGI |
| Database | sqlcipher3 | latest | Encrypted SQLite (Decree 356) |
| Async DB | aiosqlite | latest | Non-blocking DB access |
| Audio | sounddevice | latest | System audio + mic capture |
| Audio Processing | ffmpeg-python | latest | Format conversion |
| ASR: Vietnamese | nemo_toolkit[asr] | latest | NVIDIA Parakeet-CTC-0.6B-Vi |
| ASR: English | faster-whisper | latest | CTranslate2 Whisper large-v3 |
| ASR: Vietnamese FB | transformers | latest | VinAI PhoWhisper-large |
| ASR: POST unified | vibevoice | latest | Microsoft VibeVoice-ASR 7B |
| ASR: Streaming | simulstreaming | git | ufal/SimulStreaming (AlignAtt) |
| ASR: CPU fallback | (gasr submodule) | git | Google SODA offline |
| Diarization LIVE | diart | latest | Real-time 500ms streaming |
| Diarization offline | pyannote.audio | >=3.1 | Fallback full-file diarization |
| LLM: Local | ollama (via httpx) | latest | Qwen3-8B/72B |
| LLM: Cloud | anthropic | latest | Claude Sonnet 4 |
| Embeddings | sentence-transformers | latest | all-MiniLM-L6-v2 |
| Logging | structlog | latest | JSON structured logging |
| Config | pydantic-settings | latest | Environment + file config |
| Testing | pytest, pytest-asyncio | latest | Backend tests |
| HTTP client | httpx | latest | Async HTTP for LLM/ASR APIs |

### 3.2 Web Frontend — Angular 21

| Component | Package | Purpose |
|-----------|---------|---------|
| Framework | @angular/core@21 | Zoneless, standalone components |
| CLI | @angular/cli@21 | Build, serve, generate |
| HTTP | @angular/common/http | HttpClient with functional interceptors |
| Forms | @angular/forms | Reactive forms for settings |
| Router | @angular/router | Lazy-loaded routes |
| State (sync) | Angular Signals (built-in) | UI state, DOM rendering |
| State (async) | rxjs@8 | WebSocket streams, backpressure |
| Styling | tailwindcss@4 | Utility-first CSS |
| Rich Text | @tiptap/angular (or ngx-tiptap) | Editable meeting notes |
| Icons | lucide-angular | Icon set |
| Testing | karma + jasmine (Angular default) | Unit tests |
| E2E | playwright | End-to-end tests |

### 3.3 Desktop — Electron 40

| Component | Package | Purpose |
|-----------|---------|---------|
| Shell | electron@40 | Native desktop wrapper |
| Build | electron-builder | Win (.exe), Mac (.dmg), Linux (.AppImage) |
| Auto-update | electron-updater | Auto-update support |

### 3.4 Mobile — Flutter (latest stable)

| Component | Package (pub.dev) | Purpose |
|-----------|-------------------|---------|
| State | riverpod | Reactive state management |
| Navigation | go_router | Declarative routing |
| Audio recording | record | Background PCM streaming |
| On-device ASR | fonnx | ONNX Runtime (CoreML/NNAPI) |
| On-device diarization | sherpa_onnx | PyAnnote ONNX on-device |
| WebSocket | web_socket_channel | Server streaming |
| HTTP | dio | REST API client |
| Permissions | permission_handler | Mic, notifications |
| Local storage | hive | Cached meeting data |

### 3.5 Docker Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| meetscribe-backend | (local build) | 9876 | FastAPI backend |
| whisper-asr | onerahmet/openai-whisper-asr-webservice:latest-gpu | 9000 | REST ASR microservice |

---

## 4. ASR ENGINE ARCHITECTURE

### 4.1 Abstract Interface — ALL engines implement this

```python
# File: backend/asr/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional
import time

@dataclass
class TranscriptSegment:
    """Single unit of transcribed speech."""
    text: str
    start_time: float                   # seconds from recording start
    end_time: float                     # seconds from recording start
    confidence: float = 0.9            # 0.0 - 1.0
    language: str = "vi"               # ISO 639-1
    is_final: bool = True              # False = interim/partial result
    speaker: Optional[str] = None      # SPEAKER_00, SPEAKER_01, etc.
    source: str = "live"               # "live" or "post"
    timestamp: float = field(default_factory=time.time)  # wall clock

class ASREngine(ABC):
    """All ASR engines MUST implement this interface."""

    @abstractmethod
    async def initialize(self, config: dict) -> None:
        """Load model, allocate GPU memory."""

    @abstractmethod
    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """LIVE mode: yield segments as audio streams in."""

    @abstractmethod
    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        """POST mode: process complete audio file."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Release GPU memory, cleanup."""

    @property
    @abstractmethod
    def capabilities(self) -> dict:
        """Return dict with keys:
        streaming: bool, languages: list[str], gpu_required: bool,
        gpu_vram_mb: int, has_diarization: bool, has_timestamps: bool,
        has_punctuation: bool, model_name: str
        """

    def supports_streaming(self) -> bool:
        return self.capabilities.get("streaming", False)

    def supports_language(self, lang: str) -> bool:
        return lang in self.capabilities.get("languages", [])
```

### 4.2 Engine Registry

```python
# File: backend/asr/engine_factory.py

ENGINE_REGISTRY: dict[str, type] = {
    "parakeet-vi":     "backend.asr.parakeet_engine.ParakeetVietnameseEngine",
    "faster-whisper":  "backend.asr.faster_whisper_engine.FasterWhisperEngine",
    "vibevoice":       "backend.asr.vibevoice_engine.VibeVoiceASREngine",
    "phowhisper":      "backend.asr.phowhisper_engine.PhoWhisperEngine",
    "qwen3-asr":       "backend.asr.qwen3_asr_engine.Qwen3ASREngine",
    "gasr":            "backend.asr.gasr_engine.GASREngine",
    "cloud":           "backend.asr.cloud_engine.CloudASREngine",
    "whisper-asr-api": "backend.asr.whisper_asr_client.WhisperASRClient",
    "whisperlivekit":  "backend.asr.whisperlivekit_engine.WhisperLiveKitEngine",
    "gemma4":          "backend.asr.gemma4_engine.Gemma4Engine",
}

# SimulStreaming is NOT an engine — it WRAPS engines for streaming policy.
# File: backend/asr/simulstreaming_engine.py wraps Parakeet or faster-whisper.
# WhisperLiveKit is a STANDALONE streaming frontend with its own web UI.
# Qwen3-ASR supports BOTH streaming and offline, with forced alignment.
```

### 4.3 Language Router Logic

```python
# File: backend/asr/language_router.py

class LanguageRouter:
    """Auto-detect language from first audio chunk, select optimal engine."""

    ROUTING_TABLE = {
        "vi": "parakeet-vi",       # Vietnamese → Parakeet (2GB, native PnC)
        "en": "faster-whisper",    # English → faster-whisper large-v3
        "mixed": "parakeet-vi",    # VN-EN code-switch → Parakeet (has CS support)
    }

    POST_ENGINE = "vibevoice"      # Always VibeVoice for POST (best unified)
    FALLBACK_ENGINE = "phowhisper" # If Parakeet unavailable

    async def detect_language(self, audio_chunk: bytes) -> str:
        """Use Whisper tiny (CPU, ~39MB) for language detection only."""
        # Returns "vi", "en", or "mixed"

    def select_live_engine(self, language: str) -> str:
        return self.ROUTING_TABLE.get(language, "faster-whisper")

    def select_post_engine(self) -> str:
        return self.POST_ENGINE
```

### 4.4 GPU Memory Budget (RTX 3090, 24GB)

```
LIVE mode (during meeting):
  Parakeet-CTC-0.6B-Vi:              ~2 GB
  diart (pyannote seg + embedding):   ~2 GB
  Maxine AEC/BNR:                     ~0.5 GB
  SimulStreaming overhead:             ~0.5 GB
  ─────────────────────────────────────────
  Total LIVE:                         ~5 GB     ✓ 19 GB headroom

POST mode (AFTER meeting — unload LIVE engines first):
  VibeVoice-ASR 7B (4-bit NF4):      ~7 GB
  Qwen3-8B via Ollama (Q4):          ~5 GB
  ─────────────────────────────────────────
  Total POST:                         ~12 GB    ✓ fits

RULE: Never load LIVE and POST engines simultaneously on RTX 3090.
      Pipeline orchestrator MUST unload LIVE before loading POST.
      On DGX Spark GB10 (128GB), both can coexist.
```

---

## 5. LLM SUMMARIZATION

### 5.1 Provider Interface

```python
# File: backend/llm/base.py

class LLMProvider(ABC):
    @abstractmethod
    async def summarize(self, transcript: str, system_prompt: str) -> str:
        """Generate summary from transcript using system prompt template."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify provider is reachable and model is loaded."""
```

### 5.2 Providers

```python
# backend/llm/ollama_provider.py — Qwen3-8B (local) or Qwen3-72B (DGX)
# backend/llm/claude_provider.py — Claude Sonnet 4 (cloud, highest quality)
```

### 5.3 Summary Templates

Located in `backend/llm/templates/`. YAML files with `name`, `language`, `prompt` fields.

**Built-in templates:**
```
general.yaml          general_vi.yaml         # General meeting
standup.yaml          standup_vi.yaml         # Daily standup
client_call.yaml      client_call_vi.yaml     # Client meeting
sprint_retro.yaml     sprint_retro_vi.yaml    # Sprint retrospective
one_on_one.yaml       one_on_one_vi.yaml      # 1-on-1
interview.yaml        interview_vi.yaml       # Interview
```

**Vietnamese template structure:**
```yaml
name: "Biên bản họp chung"
language: "vi"
prompt: |
  Bạn là trợ lý tạo biên bản họp chuyên nghiệp.
  Dựa trên bản ghi cuộc họp có nhãn người nói và dấu thời gian,
  hãy tạo bản tóm tắt theo cấu trúc:

  ## Cuộc họp: {tiêu đề}
  **Ngày:** {ngày} | **Thời lượng:** {thời lượng}
  **Người tham gia:** {danh sách}

  ### Tóm tắt (2-3 câu)
  ### Các điểm thảo luận chính (ghi rõ người nói, thời gian)
  ### Quyết định
  ### Công việc cần làm
  | # | Công việc | Phụ trách | Hạn | Trạng thái |
  ### Theo dõi tiếp
  ### Câu hỏi chưa giải quyết

  Quy tắc:
  - Luôn ghi rõ ai nói gì
  - Phân biệt quyết định vs thảo luận
  - Trích xuất action items có người phụ trách
  - Giữ nguyên tiếng Việt, không dịch sang tiếng Anh
```

---

## 6. DATABASE (SQLCipher — Decree 356 Compliant)

```sql
-- File: backend/database.py handles schema creation
-- Connection: PRAGMA key = '{user_passphrase_from_config}';
-- Encryption: AES-256-CBC via SQLCipher

CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    duration_seconds INTEGER,
    audio_retained BOOLEAN DEFAULT FALSE,
    audio_file_path TEXT,
    primary_language TEXT DEFAULT 'vi',
    asr_live_engine TEXT,
    asr_post_engine TEXT,
    llm_provider TEXT,
    template_name TEXT,
    consent_recording BOOLEAN NOT NULL DEFAULT FALSE,
    consent_voiceprint BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT DEFAULT 'recording',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    speaker_label TEXT,
    speaker_name TEXT,
    text TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    confidence REAL,
    language TEXT,
    source TEXT DEFAULT 'live',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_seg_meeting ON transcript_segments(meeting_id);
CREATE INDEX IF NOT EXISTS idx_seg_time ON transcript_segments(meeting_id, start_time);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    template_name TEXT,
    content TEXT NOT NULL,
    llm_provider TEXT,
    llm_model TEXT,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    owner TEXT,
    deadline TEXT,
    status TEXT DEFAULT 'open',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS speaker_voiceprints (
    id TEXT PRIMARY KEY,
    speaker_name TEXT NOT NULL,
    voice_embedding BLOB,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meeting_hotwords (
    meeting_id TEXT REFERENCES meetings(id) ON DELETE CASCADE,
    hotword TEXT NOT NULL,
    PRIMARY KEY (meeting_id, hotword)
);

CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts
    USING fts5(text, content=transcript_segments, content_rowid=id);

CREATE TABLE IF NOT EXISTS segment_embeddings (
    segment_id INTEGER PRIMARY KEY REFERENCES transcript_segments(id) ON DELETE CASCADE,
    embedding BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details TEXT,
    performed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 7. API ENDPOINTS

### 7.1 REST API (FastAPI, port 9876)

```
# Recording
POST   /api/recording/start          { device_ids, language, hotwords }
POST   /api/recording/stop           { meeting_id }
POST   /api/recording/pause          { meeting_id }

# Meetings
GET    /api/meetings                 ?page=1&per_page=20&language=vi
GET    /api/meetings/{id}            → meeting + summary + actions
GET    /api/meetings/{id}/transcript → full transcript segments
GET    /api/meetings/{id}/actions    → action items
POST   /api/meetings/{id}/summarize  { template, llm_provider }
POST   /api/meetings/{id}/reprocess  → re-run VibeVoice POST
DELETE /api/meetings/{id}/purge      → Decree 356 full purge (cascade)

# Search
GET    /api/search?q={query}&type=fts|semantic&language=vi

# Settings
GET    /api/settings
PUT    /api/settings                 { asr_engine, llm_provider, ... }
GET    /api/engines                  → list available engines + status
POST   /api/engines/{name}/benchmark → run accuracy benchmark

# Audio devices
GET    /api/audio/devices            → list system + mic devices

# Compliance (Decree 356)
GET    /api/compliance/consent/{meeting_id}
POST   /api/compliance/consent       { meeting_id, recording, voiceprint }
DELETE /api/compliance/voiceprints/{speaker_id}
GET    /api/compliance/audit-log     ?entity_type=meeting&entity_id=...

# Health
GET    /api/health                   → system status, GPU info, model status
```

### 7.2 WebSocket Endpoints

```
ws://localhost:9876/ws/transcript/{meeting_id}
  → Server sends:
    { "type": "segment",      "data": TranscriptSegment }
    { "type": "diarization",  "data": { "speaker", "start", "end" } }
    { "type": "status",       "data": { "state": "live"|"processing"|"complete", "message" } }
    { "type": "level",        "data": { "system": 0.0-1.0, "mic": 0.0-1.0 } }

ws://localhost:9876/ws/audio/{meeting_id}
  → Client sends: raw PCM 16-bit 16kHz mono bytes (for IoT devices)
```

---

## 8. ANGULAR PATTERNS (Mandatory)

### 8.1 Project Generation
```bash
ng new meetscribe-web --standalone --zoneless --style=css --routing --ssr=false
# Then add Tailwind:
npm install -D tailwindcss @tailwindcss/postcss postcss
```

### 8.2 Core Pattern: WebSocket → RxJS → Signal

```typescript
// MANDATORY PATTERN for all real-time data in MeetScribe Angular

// Step 1: RxJS handles WebSocket with backpressure
private ws$ = webSocket<any>(`ws://localhost:9876/ws/transcript/${meetingId}`);

private segments$ = this.ws$.pipe(
  filter(msg => msg.type === 'segment'),
  map(msg => msg.data as TranscriptSegment),
  bufferTime(200),                           // Batch every 200ms
  filter(batch => batch.length > 0),
  scan((acc, batch) => [...acc, ...batch], [] as TranscriptSegment[])
);

// Step 2: Signal for DOM rendering (zoneless, no zone.js)
segments = toSignal(this.segments$, { initialValue: [] });

// Step 3: Component reads Signal directly
// Template: @for (seg of segments(); track seg.start_time) { ... }
```

### 8.3 Rules
- **Standalone components ONLY** — no NgModules anywhere
- **Zoneless** — no zone.js imports, no zone.js polyfill
- **Signals** for all synchronous UI state (recording status, theme, active speaker)
- **RxJS** for all async streams (WebSocket, HTTP, timers)
- **toSignal()** to bridge RxJS → Signals at the boundary
- **OnPush** change detection (automatic with Signals)
- **Functional interceptors** for HTTP (not class-based)
- **inject()** function preferred over constructor injection
- **Lazy-loaded routes** via loadComponent
- All models in `core/models/`, all services in `core/services/`
- Feature folders: `features/recording/`, `features/transcript/`, etc.

---

## 9. FLUTTER PATTERNS (Mandatory)

### 9.1 Rules
- **Riverpod** for state management — no setState, no BLoC
- **GoRouter** for navigation
- **fonnx** for on-device ONNX inference (Whisper, Silero VAD)
- **sherpa_onnx** for on-device diarization
- **record** package for background audio (not just_audio or audioplayers)
- **Android**: Foreground Service with `FOREGROUND_SERVICE_TYPE_MICROPHONE`
- **iOS**: `UIBackgroundModes: audio` + `AVAudioSession(category: .playAndRecord)`
- **Consent dialog** MUST appear before mic access (Decree 356)
- **On-device mode**: audio + voiceprints NEVER leave device
- **Server mode**: stream audio via WebSocket, receive transcript back

---

## 10. ELECTRON PATTERNS (Mandatory)

### 10.1 Rules
- macOS: MUST set `app.commandLine.appendSwitch('enable-features', 'MacLoopbackAudioForScreenShare')`
- macOS: Info.plist MUST declare `NSAudioCaptureUsageDescription`
- macOS fallback: if desktopCapturer returns silent, use IPC audio tap (Rust/Swift child process)
- Windows: desktopCapturer with WASAPI loopback works natively
- Linux: PulseAudio monitor source
- System tray: green=idle, red=recording, blue=POST processing
- Global hotkey: Ctrl+Shift+R (configurable via settings)
- Electron wraps the Angular production build (`ng build` output)
- Backend: spawned as child process OR user runs separately

---

## 11. PIPELINE ORCHESTRATOR

```python
# File: backend/pipeline/orchestrator.py

class MeetingOrchestrator:
    """Coordinates the full meeting lifecycle across all components."""

    # LIVE: start audio → detect language → select ASR engine → start diart → stream to WS
    # END:  stop audio → save WAV → unload LIVE models → load VibeVoice → reprocess
    #       → parse structured output → save POST segments → load LLM → summarize
    #       → save summary + action items → notify clients via WS

    # CRITICAL RULES:
    # 1. GPU models loaded/unloaded via engine.initialize() / engine.shutdown()
    # 2. NEVER run LIVE and POST engines simultaneously on RTX 3090
    # 3. Raw audio in memory only — save WAV to disk only if consent_recording=True
    # 4. After POST processing, broadcast status "complete" via WebSocket
    # 5. If VibeVoice unavailable, fall back to PhoWhisper file transcribe + pyannote offline
```

---

## 12. COMPLIANCE RULES (Vietnam Decree 356)

**These are NON-NEGOTIABLE. Every PR is checked for compliance.**

1. **Consent BEFORE capture**: Angular consent dialog, Electron consent dialog, Flutter consent dialog — all MUST block mic access until consent granted. Two checkboxes: "I consent to recording" + "I consent to voiceprint extraction for speaker identification".
2. **Encrypted storage**: ALL database access via SQLCipher. Config key from environment variable `MEETSCRIBE_DB_KEY`. Never hardcode.
3. **Ephemeral audio**: Raw audio held in Python `bytearray` / `deque` during LIVE. Permanently destroyed after transcript committed. WAV file saved ONLY if `consent_recording=True` AND `audio_retained=True`.
4. **Voiceprint isolation**: `speaker_voiceprints` table is separate. DELETE `/api/compliance/voiceprints/{id}` purges embedding without affecting transcripts.
5. **Full purge**: DELETE `/api/meetings/{id}/purge` cascades to: segments, summaries, action_items, hotwords, embeddings, audio file. Audit logged.
6. **Audit trail**: Every data processing operation logged in `audit_log` table.
7. **Transport encryption**: WebSocket connections MUST use WSS (TLS 1.3) in production. Self-signed cert acceptable for localhost dev.
8. **Edge priority**: Flutter on-device mode is privacy-preferred — biometric data never leaves device.

---

## 13. FILE STRUCTURE

```
meetscribe/
├── CLAUDE.md                     ← THIS FILE
├── README.md                     ← Human setup guide
├── pyproject.toml                ← Python project config
├── docker-compose.yml            ← Backend + whisper-asr-webservice
├── .github/workflows/            ← CI/CD with Claude Code review
│   ├── ai-review.yml
│   ├── backend-ci.yml
│   ├── frontend-ci.yml
│   └── mobile-ci.yml
│
├── backend/                      ← Python FastAPI
│   ├── __init__.py
│   ├── main.py                   ← FastAPI app (uvloop, ORJSONResponse)
│   ├── config.py                 ← Pydantic settings
│   ├── database.py               ← SQLCipher setup + schema
│   ├── audio/
│   │   ├── capture.py            ← AudioCapture (system + mic)
│   │   ├── devices.py            ← Device enumeration
│   │   ├── recorder.py           ← WAV recording session
│   │   ├── file_import.py        ← Import audio/video files
│   │   └── maxine_preprocessor.py ← NVIDIA Maxine AEC + noise removal
│   ├── asr/
│   │   ├── base.py               ← ASREngine ABC + TranscriptSegment
│   │   ├── parakeet_engine.py    ← NVIDIA Parakeet Vietnamese (PRIMARY)
│   │   ├── simulstreaming_engine.py ← SimulStreaming AlignAtt wrapper
│   │   ├── vibevoice_engine.py   ← VibeVoice-ASR 7B (POST)
│   │   ├── faster_whisper_engine.py ← English LIVE
│   │   ├── phowhisper_engine.py  ← Vietnamese fallback
│   │   ├── gasr_engine.py        ← CPU-only SODA
│   │   ├── cloud_engine.py       ← Groq/OpenAI cloud
│   │   ├── whisper_asr_client.py ← whisper-asr-webservice REST client
│   │   ├── language_router.py    ← Auto-detect → engine selection
│   │   └── engine_factory.py     ← Registry + factory
│   ├── diarization/
│   │   ├── live_diarization.py   ← diart streaming
│   │   ├── offline_diarization.py ← pyannote fallback
│   │   └── speaker_profiles.py   ← Name assignment + voiceprints
│   ├── llm/
│   │   ├── base.py               ← LLMProvider ABC
│   │   ├── ollama_provider.py    ← Qwen3 via Ollama
│   │   ├── claude_provider.py    ← Claude Sonnet 4
│   │   ├── summarizer.py         ← Summary orchestration
│   │   └── templates/            ← YAML templates (VN + EN)
│   ├── pipeline/
│   │   └── orchestrator.py       ← MeetingOrchestrator
│   ├── compliance/
│   │   ├── consent.py            ← Consent management
│   │   ├── data_purge.py         ← Data subject rights
│   │   └── audit_log.py          ← Processing audit trail
│   ├── storage/
│   │   ├── models.py             ← Data models
│   │   ├── repository.py         ← CRUD operations
│   │   ├── search.py             ← FTS5 + semantic search
│   │   └── embeddings.py         ← sentence-transformers
│   ├── export/
│   │   ├── markdown.py
│   │   └── clipboard.py
│   └── api/
│       ├── meetings.py           ← Meeting CRUD endpoints
│       ├── recording.py          ← Recording control
│       ├── search.py             ← Search endpoints
│       ├── settings.py           ← Settings CRUD
│       ├── engines.py            ← Engine status + benchmark
│       ├── compliance.py         ← Consent + purge + audit
│       └── websocket.py          ← WebSocket handlers
│
├── engines/
│   ├── gasr/                     ← Git submodule: ngtrphuong/gasr
│   └── simulstreaming/           ← Git submodule: ufal/SimulStreaming
│
├── frontend/                     ← Angular 21 (zoneless, standalone)
│   ├── angular.json
│   ├── package.json
│   ├── tsconfig.json
│   └── src/app/
│       ├── app.component.ts
│       ├── app.routes.ts
│       ├── core/services/        ← TranscriptStreamService, etc.
│       ├── core/models/          ← TypeScript interfaces
│       ├── features/             ← Feature modules
│       │   ├── recording/
│       │   ├── transcript/
│       │   ├── summary/
│       │   ├── meetings/
│       │   ├── search/
│       │   ├── settings/
│       │   └── consent/
│       └── shared/               ← Shared components, pipes
│
├── electron/                     ← Electron 40 desktop
│   ├── main.ts
│   ├── preload.ts
│   ├── tray.ts
│   ├── audio-tap.ts             ← macOS CoreAudio fallback
│   └── package.json
│
├── mobile/                       ← Flutter
│   ├── pubspec.yaml
│   ├── lib/
│   │   ├── main.dart
│   │   ├── core/services/       ← Audio, transcriber, WebSocket
│   │   ├── core/models/
│   │   ├── core/providers/      ← Riverpod
│   │   ├── features/            ← Screens
│   │   └── genui/               ← Dynamic widget builder
│   ├── assets/                  ← ONNX models for on-device
│   └── test/
│
├── iot/                          ← IoT audio streamer
│   └── audio_streamer.py
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── tests/
│   ├── backend/
│   ├── e2e/
│   └── fixtures/
│
├── scripts/
│   ├── download_models.py
│   └── setup_sqlcipher.sh
│
└── docs/
```

---

## 14. KEY COMMANDS

```bash
# ── Backend ──────────────────────────────────────────────
pip install -e ".[dev]"
uvicorn backend.main:app --reload --host 0.0.0.0 --port 9876

# ── Angular Frontend ─────────────────────────────────────
cd frontend && npm install
ng serve --port 4200                    # Dev server (proxies to :9876)
ng build --configuration=production     # Production build
ng test --watch=false --code-coverage   # Unit tests

# ── Electron Desktop ─────────────────────────────────────
cd electron && npm install
npm run dev                             # Dev mode (loads Angular dev server)
npm run build                           # Build installers

# ── Flutter Mobile ───────────────────────────────────────
cd mobile && flutter pub get
flutter run                             # Run on connected device
flutter test                            # Unit tests
flutter build apk --release             # Android release
flutter build ios --release             # iOS release

# ── Docker ───────────────────────────────────────────────
docker-compose up -d                    # Start all services
docker-compose up -d whisper-asr        # Start ASR microservice only

# ── Model Downloads ──────────────────────────────────────
python scripts/download_models.py --engine parakeet-vi
python scripts/download_models.py --engine vibevoice --quantization 4bit
python scripts/download_models.py --engine faster-whisper --size large-v3
python scripts/download_models.py --engine phowhisper --size large

# ── GASR Setup ───────────────────────────────────────────
cd engines/gasr && python prep.py -s -l "en-us"

# ── Tests ────────────────────────────────────────────────
pytest tests/ -v --cov=backend
cd frontend && ng test
cd mobile && flutter test

# ── Linting ──────────────────────────────────────────────
ruff check backend/
cd frontend && ng lint
cd mobile && dart analyze
```

---

## 15. DEVELOPMENT SEQUENCE (for Claude Code)

When asked to "build MeetScribe" or "start development", follow this exact order:

```
Phase 1 — Backend Core (Day 1):
  1. pyproject.toml + requirements
  2. backend/config.py (Pydantic settings)
  3. backend/database.py (SQLCipher schema)
  4. backend/asr/base.py (ASREngine ABC)
  5. backend/asr/engine_factory.py
  6. backend/audio/capture.py + devices.py
  7. backend/audio/recorder.py
  8. backend/asr/faster_whisper_engine.py (quickest to test)
  9. backend/asr/parakeet_engine.py
  10. backend/asr/language_router.py
  11. backend/main.py (FastAPI + WebSocket)
  12. backend/api/websocket.py
  13. backend/api/recording.py

Phase 2 — Pipeline + Diarization (Day 2):
  14. backend/diarization/live_diarization.py (diart)
  15. backend/pipeline/orchestrator.py
  16. backend/asr/vibevoice_engine.py
  17. backend/asr/simulstreaming_engine.py
  18. backend/llm/base.py + ollama_provider.py + claude_provider.py
  19. backend/llm/summarizer.py + templates/
  20. backend/storage/repository.py
  21. backend/api/meetings.py + search.py
  22. backend/compliance/consent.py + data_purge.py + audit_log.py
  23. backend/api/compliance.py

Phase 3 — Angular Frontend (Day 3-4):
  24. ng new meetscribe-web --standalone --zoneless
  25. Tailwind CSS setup
  26. core/services/websocket.service.ts
  27. core/services/transcript-stream.service.ts (RxJS → Signal)
  28. core/services/recording.service.ts
  29. core/services/meeting.service.ts
  30. core/models/ (TypeScript interfaces matching backend)
  31. features/consent/consent-dialog.component.ts
  32. features/recording/recording-controls.component.ts
  33. features/transcript/live-transcript.component.ts
  34. features/summary/summary-view.component.ts
  35. features/meetings/meeting-list.component.ts
  36. features/search/search-bar.component.ts
  37. features/settings/settings-panel.component.ts
  38. app.routes.ts + app.component.ts (layout)

Phase 4 — Electron + Polish (Day 4-5):
  39. electron/main.ts + preload.ts + tray.ts
  40. electron/package.json + electron-builder.yml
  41. macOS audio fix (CoreAudio Tap flag)
  42. Export: markdown.py + clipboard.py
  43. backend/asr/gasr_engine.py
  44. backend/audio/file_import.py
  45. Tests: pytest + Angular karma
  46. .github/workflows/ (CI/CD)
  47. docker-compose.yml
  48. README.md

Phase 5 — Flutter Mobile (Week 2):
  49. Flutter project + pubspec.yaml
  50. On-device: fonnx Whisper + sherpa-onnx diarization
  51. Server mode: WebSocket streaming
  52. Android Foreground Service + iOS Audio Session
  53. Consent dialog
  54. IoT: iot/audio_streamer.py
```

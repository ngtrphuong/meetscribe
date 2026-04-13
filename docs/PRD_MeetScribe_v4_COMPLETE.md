# MeetScribe — Product Requirements Document v4.1 (FINAL)
# AI-First Meeting Intelligence Platform

**Version:** 4.1 (Final Consolidated)
**Date:** April 11, 2026
**Author:** Program 3 — TMA Solutions
**Status:** IMPLEMENTED — All 54 development steps completed via Claude Code

---

## Document Control

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Apr 8, 2026 | Initial PRD — faster-whisper + pyannote + Tauri + React |
| 2.0 | Apr 8, 2026 | Added VibeVoice-ASR, diart, PhoWhisper, dual-mode LIVE/POST architecture |
| 3.0 | Apr 9, 2026 | Added Parakeet-CTC-Vi, SimulStreaming, whisper-asr-webservice, Electron, React Native, IoT, 17 repos evaluated |
| 4.0 | Apr 9, 2026 | Angular 21, Flutter, AI-First SDLC, Decree 356 compliance, Electron 40 macOS fix, FastAPI GPU isolation |
| **4.1** | **Apr 11, 2026** | **Qwen3-ASR, WhisperLiveKit, multi-LLM (Gemini/MiniMax/Qwen Cloud), build fix, all 54 steps implemented** |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Vision & Goals](#2-product-vision--goals)
3. [Target Users & Personas](#3-target-users--personas)
4. [System Architecture](#4-system-architecture)
5. [Technology Stack](#5-technology-stack)
6. [ASR Engine Decision Matrix](#6-asr-engine-decision-matrix)
7. [Repository Assessment (20 Repos Evaluated)](#7-repository-assessment)
8. [GPU Memory Planning](#8-gpu-memory-planning)
9. [EPICs & User Stories](#9-epics--user-stories)
10. [Non-Functional Requirements](#10-non-functional-requirements)
11. [Compliance — Vietnam Decree 356](#11-compliance--vietnam-decree-356)
12. [AI-First SDLC](#12-ai-first-sdlc)
13. [Multi-Platform Strategy](#13-multi-platform-strategy)
14. [Risk & Mitigation](#14-risk--mitigation)
15. [Release Plan & Sprint Execution](#15-release-plan--sprint-execution)
16. [Implementation Status](#16-implementation-status)

---

## 1. Executive Summary

MeetScribe is a **Vietnamese-first, local-first, AI-native meeting intelligence platform** that captures audio from any meeting source (Zoom, Teams, Google Meet, in-person), transcribes it in real-time with GPU-accelerated ASR, identifies speakers via diarization, and generates structured meeting summaries using LLMs — all running on local hardware for maximum privacy and compliance with Vietnam's Personal Data Protection Law (Decree 356).

### Key Differentiators

| Feature | MeetScribe | Otter.ai | Fireflies | Notion AI Notes |
|---------|-----------|----------|-----------|-----------------|
| Vietnamese SOTA | ⃣ Parakeet + PhoWhisper + Qwen3-ASR | ❌ | ❌ | ❌ |
| VN-EN code-switching | ⃣ Native | ❌ | ❌ | ❌ |
| Local-first (no cloud) | ⃣ All processing on-device | ❌ Cloud | ❌ Cloud | ❌ Cloud |
| Real-time + Post-processing | ⃣ Dual-mode (LIVE+POST) | LIVE only | LIVE only | POST only |
| Built-in diarization | ⃣ diart + VibeVoice | ⃣ | ⃣ | ❌ |
| Open source engines | ⃣ 10 pluggable engines | ❌ | ❌ | ❌ |
| Decree 356 compliant | ⃣ Architecture-level | ❌ | ❌ | ❌ |
| Multi-platform | ⃣ Web + Desktop + Mobile + IoT | Web + Mobile | Web + Mobile | Web |
| Multi-LLM summarization | ⃣ 7 providers | ❌ | ❌ | ❌ GPT only |

### Architecture Summary

```
LIVE MODE (during meeting):
  Audio → Maxine noise removal → Language detection
    → Vietnamese: Parakeet-CTC / Qwen3-ASR / PhoWhisper
    → English: faster-whisper large-v3
    → Streaming policy: SimulStreaming AlignAtt / WhisperLiveKit
  + diart (real-time speaker diarization, 500ms)
  → WebSocket → Angular / Electron / Flutter / IoT clients

POST MODE (after meeting):
  Full WAV → VibeVoice-ASR 7B (unified ASR + diarization + timestamps)
  → Structured JSON → LLM Summarizer (7 providers) → Meeting notes
  → Replaces LIVE transcript with POST transcript
```

---

## 2. Product Vision & Goals

**Vision:** The most accurate, privacy-first, open-source AI meeting notes tool optimized for Vietnamese-English bilingual meetings, running on local GPU hardware.

### Goals

| ID | Goal | Metric | Target |
|----|------|--------|--------|
| G1 | Vietnamese ASR accuracy | WER | < 10% (Parakeet/Qwen3-ASR) |
| G2 | English ASR accuracy | WER | < 5% (faster-whisper/VibeVoice) |
| G3 | Real-time transcription latency | Speech → screen | < 3 seconds |
| G4 | Speaker diarization accuracy | Attribution | ≥ 90% |
| G5 | Summary generation speed | Time after meeting end | < 30 seconds (1hr meeting) |
| G6 | Cross-platform | Platforms supported | Web + Desktop + Mobile + IoT |
| G7 | Full offline capability | Internet required | No (for core pipeline) |
| G8 | Pluggable ASR engines | Engine count | 10 engines |
| G9 | Pluggable LLM providers | Provider count | 7 providers |
| G10 | Decree 356 compliance | Audit pass | Full compliance |

---

## 3. Target Users & Personas

### 3.1 Primary — TMA Program Managers (Phuong's team)
- Back-to-back client meetings (GoodNotes, CBN, Sphera)
- Vietnamese + English bilingual meetings with code-switching
- Need action items extracted automatically
- Share notes via Confluence/Slack

### 3.2 Secondary — TMA Developers
- Sprint planning, retrospectives, technical discussions
- Searchable meeting history
- Technical vocabulary accuracy matters (API names, framework terms)

### 3.3 Tertiary — TMA Clients (Enterprise)
- Strict data sovereignty requirements
- Self-hosted deployment on their infrastructure
- Audit trail of decisions
- Decree 356 compliance mandatory

---

## 4. System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    MeetScribe System Architecture                        │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────── BACKEND (Python 3.11+) ────────────────────┐  │
│  │                                                                    │  │
│  │  FastAPI + uvloop + ORJSONResponse (port 9876)                     │  │
│  │  ├── REST API (/api/*)                                             │  │
│  │  ├── WebSocket (/ws/transcript/{id}, /ws/audio/{id})               │  │
│  │  └── Static files (Angular production build)                       │  │
│  │                                                                    │  │
│  │  ┌─── Audio Pipeline ──────────────────────────────────────────┐   │  │
│  │  │ Capture (WASAPI/PulseAudio) → Maxine AEC/BNR → Recorder     │   │  │
│  │  └─────────────────────────────────────────────────────────────┘   │  │
│  │                                                                    │  │
│  │  ┌─── ASR Engines (10 pluggable, adapter pattern) ─────────────┐   │  │
│  │  │ Parakeet-Vi │ Qwen3-ASR │ faster-whisper │ VibeVoice-ASR    │   │  │
│  │  │ PhoWhisper │ SimulStreaming │ WhisperLiveKit │ GASR         │   │  │
│  │  │ Cloud (Groq/OpenAI) │ whisper-asr-webservice (Docker)       │   │  │
│  │  └─────────────────────────────────────────────────────────────┘   │  │
│  │                                                                    │  │
│  │  ┌─── Diarization ───────┐  ┌──── LLM Summarization ────────────┐  │  │
│  │  │ diart (LIVE 500ms)    │  │  Ollama (Qwen3-8B/72B)            │  │  │
│  │  │ VibeVoice (POST)      │  │  Claude API (Sonnet 4)            │  │  │
│  │  │ pyannote (offline)    │  │  OpenAI (GPT-4.1)                 │  │  │
│  │  │ pyannote-onnx (edge)  │  │  Google Gemini                    │  │  │
│  │  └───────────────────────┘  │  MiniMax (M2.5)                   │  │  │
│  │                             │  Alibaba Qwen Cloud               │  │  │
│  │  ┌─── Storage ───────────┐  │  Groq                             │  │  │
│  │  │ SQLCipher (encrypted) │  └───────────────────────────────────┘  │  │
│  │  │ FTS5 full-text search │                                         │  │
│  │  │ Semantic embeddings   │  ┌─── Compliance (Decree 356) ───────┐  │  │
│  │  └───────────────────────┘  │ Consent, Purge, Audit Log         │  │  │
│  │                             └───────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│           │              │              │              │                 │
│           ▼              ▼              ▼              ▼                 │
│    ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────────┐      │
│    │ Angular 21 │ │ Electron   │ │ Flutter    │ │ IoT / RPi       │      │
│    │ Web UI     │ │ 40 Desktop │ │ Mobile     │ │ Audio Streamer  │      │
│    │ (Zoneless  │ │ (Win/Mac/  │ │ (iOS/      │ │ (WebSocket      │      │
│    │  Signals   │ │  Linux)    │ │  Android)  │ │  client)        │      │
│    │  +RxJS)    │ │            │ │            │ │                 │      │
│    └────────────┘ └────────────┘ └────────────┘ └─────────────────┘      │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Technology Stack

### 5.1 Backend — Python 3.11+

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API Gateway | FastAPI + uvloop + httptools | Non-blocking REST + WebSocket |
| Serialization | ORJSONResponse | 20-50% faster JSON |
| GPU Isolation | Subprocess / Ray Serve | Prevent event loop blocking |
| Pre-processing | NVIDIA Maxine SDK | AEC + noise removal |
| **ASR: Vietnamese PRIMARY** | **NVIDIA Parakeet-CTC-0.6B-Vi** | 600M, 2GB VRAM, VN-EN CS, auto-PnC |
| **ASR: Multilingual SOTA** | **Qwen3-ASR-1.7B** | 52 languages, streaming+offline, forced alignment |
| ASR: LIVE Streaming | SimulStreaming (AlignAtt) | SOTA 2025 IWSLT simultaneous policy |
| ASR: Web Streaming | WhisperLiveKit | Browser-based streaming + diarization + web UI |
| ASR: POST Unified | VibeVoice-ASR 7B | 60-min single-pass + diarization + timestamps |
| ASR: English LIVE | faster-whisper large-v3 | CTranslate2 GPU-accelerated |
| ASR: Vietnamese FB | PhoWhisper-large | VinAI fine-tune, 844hrs VN data |
| ASR: CPU fallback | GASR (ngtrphuong/gasr) | Google SODA offline |
| ASR: Cloud | Groq / OpenAI Whisper API | Cloud fallback |
| ASR: Docker | whisper-asr-webservice | REST microservice + WhisperX diarization |
| Diarization LIVE | diart | 500ms streaming, pyannote-based, overlap-aware |
| Diarization POST | VibeVoice-ASR built-in | Part of unified inference |
| Diarization Offline | pyannote-audio 3.x | Full-file fallback |
| Diarization Edge | pyannote-onnx | Mobile/IoT, no PyTorch |
| LLM: Local | Ollama (Qwen3-8B/72B) | Local summarization |
| LLM: Cloud | Claude Sonnet 4, GPT-4.1, Gemini, MiniMax M2.5, Qwen Cloud, Groq | Multi-provider |
| Database | SQLCipher (encrypted SQLite) + FTS5 | Decree 356 encryption-at-rest |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Semantic search |

### 5.2 Web Frontend — Angular 21

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | Angular 21 (zoneless, standalone) | Enterprise-grade, XSS/CSP built-in |
| State (sync) | Angular Signals | UI state, DOM rendering |
| State (async) | RxJS 8 | WebSocket streams, backpressure management |
| Styling | Tailwind CSS 4 | Utility-first (dark theme: gray-950) |
| Rich Text | TipTap (Angular wrapper) | Editable meeting notes |
| GenUI | Genkit + Angular SSR | LLM-generated dynamic components |
| Build | esbuild (Angular CLI) | Fast builds |

**Core pattern (implemented):**
```typescript
// WebSocket → RxJS bufferTime → toSignal → @for rendering
private segments$ = this.ws$.pipe(
  filter(msg => msg.type === 'segment'),
  bufferTime(200),
  filter(batch => batch.length > 0),
  scan((acc, batch) => [...acc, ...batch], [])
);
segments = toSignal(this.segments$, { initialValue: [] });
```

### 5.3 Desktop — Electron 40

| Component | Technology | Notes |
|-----------|-----------|-------|
| Shell | Electron 40 | Wraps Angular build |
| Audio (macOS) | desktopCapturer + CoreAudio Tap flag | `#mac-loopback-audio-for-screen-share` |
| Tray | System tray (green/red/blue) | Recording status indicator |
| Hotkey | Ctrl+Shift+R | Global hotkey |
| Build | electron-builder | Win .exe, Mac .dmg, Linux .AppImage |

### 5.4 Mobile — Flutter (Latest Stable)

| Component | Package | Purpose |
|-----------|---------|---------|
| State | Riverpod | Reactive state |
| On-device ASR | fonnx (ONNX Runtime) | Whisper via CoreML/NNAPI |
| On-device VAD | fonnx + Silero VAD | Save battery |
| On-device Diarization | sherpa-onnx | PyAnnote ONNX |
| Audio | record package | Background PCM streaming |
| Background (Android) | Foreground Service (MICROPHONE) | Prevent OS kill |
| Background (iOS) | AVAudioSession (playAndRecord) | Keep mic active |
| GenUI | GenUI SDK for Flutter | Dynamic meeting widgets |

### 5.5 IoT / Conference Room

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Client | Python sounddevice + websockets | Audio → WebSocket stream |
| Target | Raspberry Pi 4/5, Linux SBC | Smart microphone |

---

## 6. ASR Engine Decision Matrix

| Scenario | LIVE Engine | POST Engine | Diarization |
|----------|-----------|------------|-------------|
| Vietnamese meeting | Parakeet-Vi OR Qwen3-ASR via SimulStreaming | VibeVoice-ASR 7B OR Parakeet file | diart (live) / VV built-in (post) |
| English meeting | faster-whisper large-v3 via SimulStreaming | VibeVoice-ASR 7B | diart (live) / VV built-in (post) |
| Mixed VN+EN (code-switching) | Parakeet-Vi (native CS) OR Qwen3-ASR via SimulStreaming | VibeVoice-ASR 7B (native CS) | diart (live) / VV built-in (post) |
| CPU-only / low resource | GASR/SODA | (skip POST) | GASR diarization |
| Cloud fallback | Groq Whisper API | (skip POST) | WhisperX (Docker) |
| Docker/Server deployment | whisper-asr-webservice | VibeVoice container | WhisperX |
| Mobile on-device | fonnx Whisper small (ONNX) | Send to server | sherpa-onnx (on-device) |
| IoT / Embedded | Stream audio → server WebSocket | Server-side | Server-side |
| Browser streaming | WhisperLiveKit (web UI) | N/A | WhisperLiveKit built-in |
| Ollama/OpenWebUI LLM | — (LLM only, not ASR) | — | — |

### Engine Comparison (Vietnamese)

| Engine | Vietnamese WER | VRAM | Streaming | Timestamps | Auto-PnC | CS |
|--------|---------------|------|-----------|-----------|---------|-----|
| Parakeet-CTC-0.6B-Vi | ~9.3% | ~2GB | ⃣ (NeMo) | word+seg+char | ⃣ Qwen3 | ⃣ VN-EN |
| Qwen3-ASR-1.7B | SOTA (competitive w/ commercial) | ~4GB | ⃣ | ⃣ forced align | ⃣ | ⃣ 52 langs |
| PhoWhisper-large | SOTA on VN benchmarks | ~10GB | ⃣ (sliding) | word | ❌ | ❌ VN only |
| VibeVoice-ASR 7B | Evaluated on MLC-Challenge | ~7-24GB | ❌ (POST only) | ⃣ | ⃣ | ⃣ 50+ langs |
| faster-whisper large-v3 | ~12% (VN not primary) | ~10GB | ⃣ (sliding) | word | ❌ | ⃣ 99 langs |

---

## 7. Repository Assessment (20 Repos Evaluated)

### ⃣ PICKED — Integrated into MeetScribe (11 repos)

| # | Repository | Role | License |
|---|-----------|------|---------|
| 1 | nvidia/parakeet-ctc-0.6b-Vietnamese | Primary Vietnamese ASR | NVIDIA Open |
| 2 | Qwen/Qwen3-ASR-1.7B | SOTA multilingual ASR (52 langs) | Apache 2.0 |
| 3 | QuentinFuxa/WhisperLiveKit | Browser streaming with SimulStreaming + diarization | MIT |
| 4 | ufal/SimulStreaming | AlignAtt streaming policy (IWSLT 2025 winner) | MIT |
| 5 | ahmetoner/whisper-asr-webservice | Docker REST ASR microservice | MIT |
| 6 | microsoft/VibeVoice-ASR | POST-mode unified ASR+diarization+timestamps | MIT |
| 7 | juanmc2005/diart | Real-time 500ms streaming diarization | MIT |
| 8 | ngtrphuong/gasr | CPU-only offline Google SODA | MIT |
| 9 | vinai/PhoWhisper | Vietnamese ASR fallback (844hrs fine-tune) | MIT |
| 10 | dangvansam/pyannote-onnx | Edge/mobile diarization (no PyTorch) | MIT |
| 11 | QwenLM/Qwen3-ASR | Toolkit for Qwen3-ASR inference + streaming | Apache 2.0 |

### ⏭️ REFERENCE — Patterns borrowed (4 repos)

| # | Repository | What Borrowed |
|---|-----------|---------------|
| 12 | vocodedev/vocode-core | Modular transcriber/agent/synthesizer pattern |
| 13 | gnolnos/Wyoming-Vietnamese-ASR | FastAPI wrapper pattern for VN ASR |
| 14 | segment-any-text/wtpsplit | Sentence segmentation for transcript formatting |
| 15 | ufal/whisper_streaming | WhisperStreaming predecessor (evolved into SimulStreaming) |

### ❌ SKIPPED — Evaluated and excluded (5 repos)

| # | Repository | Why Skipped |
|---|-----------|-------------|
| 16 | dangvansam/viet-asr | 13M params, 100hrs, QuartzNet outdated |
| 17 | mad1999/realtime-stt-vietnamese | No benchmarks, no community traction |
| 18 | compulim/web-speech-cognitive-services | Azure-locked, doesn't fit local-first |
| 19 | TensorSpeech/TensorFlowASR | TF2 ecosystem, PyTorch is our stack |
| 20 | biemster/gasr (original) | Using ngtrphuong fork with diarization |

---

## 8. GPU Memory Planning

### RTX 3090 (24GB VRAM) — Primary Workstation

```
LIVE mode (during meeting):
  Parakeet-CTC-0.6B-Vi:     ~2 GB
  OR Qwen3-ASR-1.7B:        ~4 GB
  diart (seg + embedding):   ~2 GB
  Maxine AEC/BNR:            ~0.5 GB
  SimulStreaming overhead:    ~0.5 GB
  ─────────────────────────────────
  Total LIVE (Parakeet):     ~5 GB    ✓ 19 GB headroom
  Total LIVE (Qwen3-ASR):   ~7 GB    ✓ 17 GB headroom

POST mode (AFTER meeting — unload LIVE first):
  VibeVoice-ASR 7B (4-bit): ~7 GB
  Qwen3-8B via Ollama (Q4): ~5 GB
  ─────────────────────────────────
  Total POST:                ~12 GB   ✓ fits

⚠️ RULE: Never load LIVE and POST engines simultaneously on RTX 3090.
```

### DGX Spark GB10 (128GB) — Heavy Processing

```
Everything simultaneously:   ~78 GB   ✓ abundant headroom
```

### Mobile On-Device

```
Whisper small Q4 (fonnx):   ~100 MB
Silero VAD (fonnx):          ~10 MB
pyannote (sherpa-onnx):      ~20 MB
Total:                       ~130 MB  ✓ any modern phone
```

---

## 9. EPICs & User Stories

### EPIC 1: Audio Capture & Recording [P0 — Day 1]

#### US-1.1: System Audio Loopback Capture
**As a** meeting participant, **I want** MeetScribe to capture system audio output, **so that** remote participants from Zoom/Teams/Meet are transcribed.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-1.1.1 | Windows: WASAPI loopback via sounddevice | ⃣ |
| AC-1.1.2 | Linux: PulseAudio/PipeWire monitor source | ⃣ |
| AC-1.1.3 | macOS: CoreAudio via Electron desktopCapturer | ⃣ |
| AC-1.1.4 | Output: 16-bit PCM, mono, 16kHz (resampled if needed) | ⃣ |
| AC-1.1.5 | Latency: audio output → capture buffer < 100ms | ⃣ |
| AC-1.1.6 | Audio level meter data sent via WebSocket | ⃣ |

**Files:** `backend/audio/capture.py`, `backend/audio/devices.py`

#### US-1.2: Microphone Input Capture
**As a** user, **I want** my own voice captured via microphone in parallel, **so that** my speech is transcribed and I'm identified as "self" speaker.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-1.2.1 | List available mic devices in settings | ⃣ |
| AC-1.2.2 | Parallel capture with system audio (separate streams) | ⃣ |
| AC-1.2.3 | Label mic channel as "self" for diarization hint | ⃣ |
| AC-1.2.4 | Optional noise suppression | ⃣ |

**File:** `backend/audio/capture.py`

#### US-1.3: Audio File Import
**As a** user with pre-recorded meetings, **I want** to import audio/video files, **so that** past meetings are processed through the same pipeline.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-1.3.1 | Formats: WAV, MP3, M4A, OGG, FLAC, MP4, WEBM, MKV | ⃣ |
| AC-1.3.2 | Extract audio via FFmpeg to 16kHz mono PCM | ⃣ |
| AC-1.3.3 | Progress indicator | ⃣ |
| AC-1.3.4 | Batch import support | ⃣ |

**File:** `backend/audio/file_import.py` (Phase 4)

#### US-1.4: Recording Session Control
**As a** user, **I want** start/stop/pause controls, **so that** I control what gets captured.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-1.4.1 | REST API: POST /api/recording/start, /stop, /pause, /resume | ⃣ |
| AC-1.4.2 | Auto-save raw WAV every 30s (crash recovery) — only if consent=True | ⃣ |
| AC-1.4.3 | Auto-stop after 5min silence (configurable) | ⃣ |
| AC-1.4.4 | Max duration: 4 hours | ⃣ |
| AC-1.4.5 | States: idle → recording → paused → processing → complete | ⃣ |
| AC-1.4.6 | Global hotkey: Ctrl+Shift+R (Electron) | ⃣ |

**File:** `backend/audio/recorder.py`

#### US-1.5: Audio Pre-Processing (NVIDIA Maxine)
**As a** user in a noisy environment, **I want** audio cleaned before ASR, **so that** noise doesn't degrade accuracy.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-1.5.1 | Acoustic Echo Cancellation (AEC) | ⬜ Stub |
| AC-1.5.2 | Background Noise Removal (BNR) | ⬜ Stub |
| AC-1.5.3 | Bypass option if Maxine unavailable | ⃣ |
| AC-1.5.4 | Processed audio fed to ASR engine (not raw) | ⃣ |

**File:** `backend/audio/maxine_preprocessor.py` (stub — requires NVIDIA Maxine SDK)

---

### EPIC 2: ASR Engine — Pluggable Architecture [P0 — Day 1-2]

#### US-2.1: ASR Engine Abstract Interface
**As a** developer, **I want** a unified interface for all ASR engines, **so that** engines are swappable without pipeline changes.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.1.1 | `ASREngine` ABC with: initialize, transcribe_stream, transcribe_file, shutdown, capabilities | ⃣ |
| AC-2.1.2 | `TranscriptSegment` dataclass with: text, start_time, end_time, confidence, language, is_final, speaker, source | ⃣ |
| AC-2.1.3 | All 10 engines implement this interface | ⃣ |
| AC-2.1.4 | Engine selection via config + UI dropdown | ⃣ |

**File:** `backend/asr/base.py`

#### US-2.2: Engine Factory & Registry
**As a** developer, **I want** a factory that creates engines by name from a registry, **so that** engine selection is configuration-driven.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.2.1 | Registry maps 10 engine names to (module, class) tuples | ⃣ |
| AC-2.2.2 | `create(name, config)` returns ASREngine instance | ⃣ |
| AC-2.2.3 | `list_engines()` shows availability status | ⃣ |
| AC-2.2.4 | Lazy imports — heavy deps not loaded at startup | ⃣ |
| AC-2.2.5 | Hot-swap support (shutdown old, initialize new) | ⃣ |

**File:** `backend/asr/engine_factory.py`

#### US-2.3: NVIDIA Parakeet-CTC-0.6B-Vietnamese Engine (PRIMARY Vietnamese)
**As a** Vietnamese speaker, **I want** NVIDIA Parakeet for highest Vietnamese accuracy with auto-punctuation, **so that** meetings produce production-quality text.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.3.1 | Load nvidia/parakeet-ctc-0.6b-vi via NeMo | ⃣ |
| AC-2.3.2 | Word + segment + character timestamps | ⃣ |
| AC-2.3.3 | Auto punctuation and capitalization (Qwen3-trained) | ⃣ |
| AC-2.3.4 | Vietnamese-English code-switching | ⃣ |
| AC-2.3.5 | KenLM language model boosting | ⃣ |
| AC-2.3.6 | ~2GB VRAM | ⃣ |
| AC-2.3.7 | NeMo chunked streaming inference | ⃣ |

**File:** `backend/asr/parakeet_engine.py`

#### US-2.4: Qwen3-ASR Engine (SOTA Multilingual)
**As a** user, **I want** Qwen3-ASR for SOTA multilingual recognition across 52 languages, **so that** I get the best accuracy available for any language.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.4.1 | Load Qwen/Qwen3-ASR-1.7B or 0.6B via qwen-asr package | ⃣ |
| AC-2.4.2 | 52 languages including Vietnamese auto-detection | ⃣ |
| AC-2.4.3 | Streaming + offline unified inference | ⃣ |
| AC-2.4.4 | Forced alignment timestamps via Qwen3-ForcedAligner-0.6B | ⃣ |
| AC-2.4.5 | vLLM backend option for production throughput | ⃣ |
| AC-2.4.6 | ~4GB VRAM (1.7B), ~2GB (0.6B) | ⃣ |

**File:** `backend/asr/qwen3_asr_engine.py`

#### US-2.5: faster-whisper Engine (English LIVE)
**As a** user in an English meeting, **I want** GPU-accelerated Whisper, **so that** I get < 3s latency.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.5.1 | Models: tiny through large-v3-turbo | ⃣ |
| AC-2.5.2 | CUDA + cuDNN acceleration via CTranslate2 | ⃣ |
| AC-2.5.3 | VAD filtering, beam search, word timestamps | ⃣ |
| AC-2.5.4 | 30s sliding window with 5s overlap streaming | ⃣ |
| AC-2.5.5 | Beam search (beam_size=5 for accuracy, 1 for speed) | ⃣ |
| AC-2.5.6 | Word-level timestamps | ⃣ |
| AC-2.5.7 | Language auto-detection | ⃣ |

**File:** `backend/asr/faster_whisper_engine.py`

#### US-2.6: VibeVoice-ASR 7B Engine (POST Unified)
**As a** user, **I want** VibeVoice to reprocess the full recording after meeting, **so that** I get the highest accuracy with built-in diarization and timestamps.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.6.1 | Load microsoft/VibeVoice-ASR with bf16/8bit/4bit quantization | ⃣ |
| AC-2.6.2 | Process up to 60 minutes in single pass | ⃣ |
| AC-2.6.3 | Parse structured JSON: [{Start, End, Speaker, Content}] | ⃣ |
| AC-2.6.4 | Custom hotwords support | ⃣ |
| AC-2.6.5 | Auto-detect language (50+ languages) | ⃣ |

**File:** `backend/asr/vibevoice_engine.py`

#### US-2.7: SimulStreaming Engine (LIVE Streaming Policy)
**As a** user, **I want** stable, non-flickering real-time text via AlignAtt policy, **so that** confirmed text doesn't change.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.7.1 | AlignAtt policy wrapping Whisper/Parakeet | ⃣ |
| AC-2.7.2 | Silero VAD for silence detection | ⃣ |
| AC-2.7.3 | Prompt injection for hotwords | ⃣ |
| AC-2.7.4 | TCP server mode | ⃣ |
| AC-2.7.5 | < 3 second commit latency | ⃣ |

**File:** `backend/asr/simulstreaming_engine.py`

#### US-2.8: WhisperLiveKit Engine (Browser Streaming)
**As a** user, **I want** a browser-based streaming option with its own web UI, **so that** I can stream from any browser.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.8.1 | SimulStreaming + LocalAgreement policies | ⃣ |
| AC-2.8.2 | Built-in diarization option | ⃣ |
| AC-2.8.3 | Web UI with WebSocket audio streaming | ⃣ |
| AC-2.8.4 | Multiple backends: faster-whisper, mlx-whisper, voxtral | ⃣ |

**File:** `backend/asr/whisperlivekit_engine.py`

#### US-2.9: PhoWhisper Engine (Vietnamese Fallback)
**As a** user when Parakeet is unavailable, **I want** PhoWhisper as fallback, **so that** I still get SOTA Vietnamese transcription.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.9.1 | Models: vinai/PhoWhisper-{tiny|base|small|medium|large} | ⃣ |
| AC-2.9.2 | Load via transformers or faster-whisper | ⃣ |
| AC-2.9.3 | Streaming via 30s sliding window | ⃣ |
| AC-2.9.4 | Word-level timestamps | ⃣ |

**File:** `backend/asr/phowhisper_engine.py`

#### US-2.10: GASR Engine (CPU Fallback)
**As a** user without a GPU, **I want** Google SODA offline ASR, **so that** I can transcribe on CPU.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.10.1 | Integrate ngtrphuong/gasr as git submodule | ⃣ |
| AC-2.10.2 | Auto-download libsoda + language model | ⃣ |
| AC-2.10.3 | Windows: WSL2 path via gasr_diarized_wsl2.py | ⃣ |
| AC-2.10.4 | Stream audio via subprocess stdin | ⃣ |
| AC-2.10.5 | Parse SODA protobuf responses into TranscriptSegment | ⃣ |

**File:** `backend/asr/gasr_engine.py`

#### US-2.11: Cloud ASR Engine
**As a** user, **I want** cloud ASR fallback (Groq/OpenAI/Claude/Gemini/Others), **so that** I get quality when local GPU is unavailable.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.11.1 | Support Groq Whisper + OpenAI Whisper API | ⃣ |
| AC-2.11.2 | Clear UI warning about cloud data transmission, "Audio will be sent to external servers" | ⃣ |
| AC-2.11.3 | API keys stored in encrypted config | ⃣ |
| AC-2.11.4 | Auto-fallback to local if API unreachable | ⃣ |

**File:** `backend/asr/cloud_engine.py`

#### US-2.12: whisper-asr-webservice REST Client
**As a** mobile/IoT client, **I want** to POST audio to the Docker ASR microservice, **so that** I get transcription via REST.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.12.1 | POST audio to http://localhost:9000/asr | ⃣ |
| AC-2.12.2 | Parse JSON with timestamps + segments | ⃣ |
| AC-2.12.3 | Support word_timestamps and vad_filter parameters | ⃣ |

**File:** `backend/asr/whisper_asr_client.py`

#### US-2.13: Language Auto-Detection & Router
**As a** bilingual user (VN/EN), **I want** auto-detection of spoken language, **so that** the best engine is selected automatically.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-2.13.1 | Detect language from first 10s (Whisper tiny, CPU) | ⃣ |
| AC-2.13.2 | Route: vi → Parakeet, en → faster-whisper, mixed → Parakeet | ⃣ |
| AC-2.13.3 | POST mode: always VibeVoice-ASR | ⃣ |
| AC-2.13.4 | User override in settings | ⃣ |

**File:** `backend/asr/language_router.py`

---

### EPIC 3: Speaker Diarization — Dual Mode [P0 — Day 2]

#### US-3.1: LIVE Diarization with diart
**As a** user, **I want** real-time speaker ID updating every 500ms, **so that** I see who speaks as it happens.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-3.1.1 | diart.SpeakerDiarization pipeline with pyannote/segmentation-3.0 + pyannote/embedding | ⃣ |
| AC-3.1.2 | 500ms update interval, overlap-aware | ⃣ |
| AC-3.1.3 | Up to 10 speakers, GPU ~2GB | ⃣ |
| AC-3.1.4 | Output via WebSocket: { type: "diarization", data: { speaker, start, end } } | ⃣ |
| AC-3.1.5 | GPU acceleration (~2GB VRAM) | ⃣ |

**File:** `backend/diarization/live_diarization.py`

#### US-3.2: POST Diarization via VibeVoice-ASR
**As a** user, **I want** accurate POST speaker labels from VibeVoice, **so that** the final transcript is correctly attributed.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-3.2.1 | VibeVoice JSON includes Speaker field natively | ⃣ |
| AC-3.2.2 | Fallback: pyannote offline if VibeVoice unavailable | ⃣ |

**Files:** `backend/asr/vibevoice_engine.py`, `backend/diarization/offline_diarization.py`

#### US-3.3: Speaker Name Assignment
**As a** user, **I want** to assign names to speaker labels, **so that** transcripts use real names.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-3.3.1 | Map SPEAKER_00 → "Nguyễn Văn A" in UI | ⃣ |
| AC-3.3.2 | Persist speaker-name mappings per meeting | ⃣ |
| AC-3.3.3 | VibeVoice hotwords: inject participant names for better speaker naming | ⃣ |
| AC-3.3.4 | Play audio sample per speaker for identification | ⃣ |

**File:** `backend/diarization/speaker_profiles.py`

#### US-3.4: Live-Post Transcript Alignment
**As a** user, **I want** LIVE transcript replaced by POST transcript after meeting, **so that** final notes are best quality.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-3.4.1 | LIVE transcript displayed during meeting (source='live') | ⃣ |
| AC-3.4.2 | POST transcript replaces LIVE after reprocessing (source='post') | ⃣ |
| AC-3.4.3 | User notified via WebSocket status broadcast "Transcript upgraded with high-accuracy processing" | ⃣ |
| AC-3.4.4 | Both versions stored; live archived | ⃣ |

**File:** `backend/pipeline/orchestrator.py`

---

### EPIC 4: LLM Summarization [P0 — Day 2]

#### US-4.1: Meeting Summary Generation
**As a** user who just finished a meeting, **I want** structured summary within 30 seconds of meeting end, **so that** I have actionable notes without any manual efforts.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-4.1.1 | Output: Title, Date, Participants, Summary, Discussion, Decisions, Actions, Follow-ups, Open Question | ⃣ |
| AC-4.1.2 | Speaker attribution in discussion points | ⃣ |
| AC-4.1.3 | Vietnamese summary for Vietnamese meetings | ⃣ |
| AC-4.1.4 | < 30s for 1hr meeting on RTX 3090 | ⃣ |

**File:** `backend/llm/summarizer.py`

#### US-4.2: Custom Summary Templates (12 Templates)
**As a** user, **I want** templates per meeting type, **so that** standup notes differ from client notes and so on.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-4.2.1 | 12 templates: general, standup, client_call, sprint_retro, one_on_one, interview (VN+EN) | ⃣ |
| AC-4.2.2 | YAML format with name, language, prompt | ⃣ |
| AC-4.2.3 | Template editor in settings UI | ⃣ |
| AC-4.2.4 | Auto-detect meeting type from keywords (stretch) | ⃣ |

**Files:** `backend/llm/templates/*.yaml` (12 files)

#### US-4.3: Multi-Provider LLM Backend (7 Providers)
**As a** user, **I want** multiple LLM options, **so that** I choose cost, security, privacy, speed, or quality.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-4.3.1 | Ollama (Qwen3.5-9B local, Qwen3-72B DGX) | ⃣ |
| AC-4.3.2 | Claude API (Sonnet 4) | ⃣ |
| AC-4.3.3 | OpenAI (GPT-4.1) | ⃣ |
| AC-4.3.4 | Google Gemini | ⃣ |
| AC-4.3.5 | MiniMax (M2.7) | ⃣ |
| AC-4.3.6 | Alibaba Qwen Cloud (DashScope) | ⃣ |
| AC-4.3.7 | Groq (fast inference) | ⃣ |
| AC-4.3.8 | Provider selection in settings UI | ⃣ |
| AC-4.3.9 | Fallback chain: local → cloud | ⃣ |

**Files:** `backend/llm/base.py`, `ollama_provider.py`, `claude_provider.py`, `multi_providers.py`

#### US-4.4: Real-time Summary Updates
**As a** user in a long meeting, **I want** running summary every 10 min, **so that** I track key points during meeting.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-4.4.1 | Incremental summary every N minutes (configurable) | ⃣ |
| AC-4.4.2 | Final summary consolidates incremental updates | ⃣ |
| AC-4.4.3 | Running summary panel alongside live transcript | ⃣ |
| AC-4.4.4 | This feature can be toggle ON/OFF in either Settings UI and current recording UI | ⃣ |

---

### EPIC 5: Data Storage & Search [P0 — Day 3]

#### US-5.1: SQLCipher Encrypted Database (Decree 356)
**As a** user, **I want** all data encrypted at rest, **so that** I comply with Decree 356.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-5.1.1 | SQLCipher with AES-256-CBC encryption (or plain SQLite fallback) | ⃣ |
| AC-5.1.2 | Key from MEETSCRIBE_DB_KEY environment variable | ⃣ |
| AC-5.1.3 | Full schema: 12 tables + FTS5 + indexes | ⃣ |
| AC-5.1.4 | WAL mode, CASCADE DELETE | ⃣ |
| AC-5.1.5 | Audit log table (append-only) | ⃣ |

**File:** `backend/database.py`

#### US-5.2: Full-Text Search (FTS5)
**As a** user, **I want** to search transcripts by keyword, **so that** I find specific discussions quickly.

| AC | Criteria | Status |
|----|---------|--------|
| AC-5.2.1 | SQLite FTS5 index on transcript segments | ⃣ |
| AC-5.2.2 | Results with surrounding context | ⃣ |
| AC-5.2.3 | Filter by date, speaker, meeting, language | ⃣ |
| AC-5.2.4 | Response < 500ms for 1000 meetings | ⃣ |

**File:** `backend/storage/search.py`

#### US-5.3: Semantic Search
**As a** user, **I want** to search by meaning (e.g. "deployment timeline discussions"), **so that** I find relevant content without exact keywords.

| AC | Criteria | Status |
|----|---------|--------|
| AC-5.3.1 | sentence-transformers all-MiniLM-L6-v2 embeddings or any emdding models which can be configurable on Settings UI | ⃣ |
| AC-5.3.2 | Cosine similarity + hybrid FTS5 combination | ⃣ |

**File:** `backend/storage/embeddings.py`

#### US-5.4: Meeting Repository (CRUD)
**As a** developer, **I want** a clean repository layer for all database operations, **so that** no raw SQL appears in API routes.

| AC | Criteria | Status |
|----|---------|--------|
| AC-5.4.1 | Full CRUD for all 12 tables | ⃣ |
| AC-5.4.2 | Async via aiosqlite | ⃣ |
| AC-5.4.3 | Pagination for list queries | ⃣ |
| AC-5.4.4 | No raw SQL in API routes | ⃣ |
| AC-5.4.5 | Cascade delete support | ⃣ |

**File:** `backend/storage/repository.py`

---

### EPIC 6: Pipeline Orchestration [P0 — Day 2]

#### US-6.1: Meeting Lifecycle Orchestrator
**As the** system, **I want** a pipeline coordinating audio → ASR → diarization → storage → POST → summarization, **so that** all components work seamlessly.

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-6.1.1 | LIVE path: audio → language detect → engine select → start diart → stream to WS | ⃣ |
| AC-6.1.2 | POST path: stop audio → save WAV → unload LIVE → load VibeVoice → reprocess → load LLM → summarize | ⃣ |
| AC-6.1.3 | GPU lifecycle: NEVER LIVE + POST simultaneously on RTX 3090 | ⃣ |
| AC-6.1.4 | Raw audio ephemeral in-memory only, destroy after commit (unless opted-in) | ⃣ |
| AC-6.1.5 | WebSocket status: "live" → "processing" → "complete" | ⃣ |
| AC-6.1.6 | Fallback: if VibeVoice fails → PhoWhisper + pyannote offline | ⃣ |

**File:** `backend/pipeline/orchestrator.py`

---

### EPIC 7: Angular 21 Web Frontend [P0 — Day 3-4]

#### US-7.1: TranscriptStreamService (Critical Path: WebSocket → RxJS → Signal)
**As a** developer, **I want** the RxJS → Signal pipeline working correctly, **so that** high-frequency ASR data renders without freezing the UI.

| AC | Criteria | Status |
|----|---------|--------|
| AC-7.1.1 | WebSocket connection via rxjs/webSocket | ⃣ |
| AC-7.1.2 | bufferTime(200ms) for backpressure to batch ASR segments | ⃣ |
| AC-7.1.3 | toSignal() for zoneless rendering | ⃣ |
| AC-7.1.4 | Zero zone.js dependency (zoneless mode) | ⃣ |
| AC-7.1.5 | Tear-free rendering at 500ms ASR commit rate | ⃣ |

**File:** `frontend/src/app/core/services/transcript-stream.service.ts`

#### US-7.2: Recording Controls Component
**As a** user, **I want** prominent record/stop/pause/resume buttons with audio levels, **so that** I control recording with one click.

| AC | Criteria | Status |
|----|---------|--------|
| AC-7.2.1 | Large record button (red pulsing when active) to record/stop/pause/resume | ⃣ |
| AC-7.2.2 | Audio level meters (system + mic) | ⃣ |
| AC-7.2.3 | Device selector dropdowns | ⃣ |
| AC-7.2.4 | Engine selector (Auto / Parakeet / Whisper / GASR) | ⃣ |
| AC-7.2.5 | Language indicator (auto-detected) | ⃣ |
| AC-7.2.6 | Duration timer with clear view HH:MM:SS | ⃣ |

**File:** `frontend/src/app/features/recording/recording-controls.component.ts`

#### US-7.3: Live Transcript
**As a** user during a meeting, **I want** real-time transcript with speaker colors, **so that** I follow along.

| AC | Criteria | Status |
|----|---------|--------|
| AC-7.3.1 | Auto-scrolling (Default: latest on top) | ⃣ |
| AC-7.3.2 | "LIVE" badge during meeting, "Enhanced" after POST | ⃣ |
| AC-7.3.3 | Speaker labels color-coded (consistent per speaker) | ⃣ |
| AC-7.3.4 | Timestamps toggleable | ⃣ |
| AC-7.3.5 | Inline edit: click/tap to correct | ⃣ |
| AC-7.3.6 | Vietnamese diacritics rendered correctly | ⃣ |
| AC-7.3.7 | @for with track by start_time (Angular 21 syntax) | ⃣ |

**File:** `frontend/src/app/features/transcript/live-transcript.component.ts`

#### US-7.4: Summary View Component
**As a** user after a meeting, **I want** the summary displayed with interactive action items, **so that** I can review and share.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-7.4.1 | Rendered Markdown support for summary body | ⃣ |
| AC-7.4.2 | Action items presented as an interactive checklist | ⃣ |
| AC-7.4.3 | Option to re-generate summary using different templates or LLM models | ⃣ |
| AC-7.4.4 | Copy to clipboard functionality (Markdown and plain text formats) | ⃣ |
| AC-7.4.5 | "Enhance" button for VibeVoice POST reprocessing | ⃣ |

**File:** `frontend/src/app/features/summary/summary-view.component.ts`

---

#### US-7.5: Meeting List & Library
**As a** user, **I want** a browsable list of all past meetings, **so that** I can find any meeting quickly.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-7.5.1 | Chronological list displayed in sidebar | ⃣ |
| AC-7.5.2 | Filter by date, language, and speaker | ⃣ |
| AC-7.5.3 | Search bar supporting keyword and semantic search | ⃣ |
| AC-7.5.4 | Quick preview panel accessible on click | ⃣ |

**File:** `frontend/src/app/features/meetings/meeting-list.component.ts`

---

#### US-7.6: Settings Panel
**As a** user, **I want** to configure all settings in one place, **so that** I optimize for my hardware.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-7.6.1 | Audio: system device selection, mic input, and test levels | ⃣ |
| AC-7.6.2 | ASR: engine picker with VRAM usage and VibeVoice quantization | ⃣ |
| AC-7.6.3 | LLM: Ollama model picker, Claude API key, and connection test | ⃣ |
| AC-7.6.4 | Language: default selection (vi/en/auto) | ⃣ |
| AC-7.6.5 | Hotwords: global keyword list management | ⃣ |
| AC-7.6.6 | GPU: real-time VRAM usage and loaded models display | ⃣ |

**File:** `frontend/src/app/features/settings/settings-panel.component.ts`

---

#### US-7.7: Consent Dialog (Decree 356)
**As a** user, **I want** to be asked for consent before any audio capture, **so that** MeetScribe complies with Decree 356.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-7.7.1 | Modal dialog that blocks all other interaction | ⃣ |
| AC-7.7.2 | Separate checkboxes for "Recording Consent" and "Voiceprint Extraction" | ⃣ |
| AC-7.7.3 | Cannot proceed until at least recording consent is given | ⃣ |
| AC-7.7.4 | Voiceprint consent optional (diarization disabled if declined) | ⃣ |
| AC-7.7.5 | Consent status stored per meeting in database | ⃣ |

**File:** `frontend/src/app/features/consent/consent-dialog.component.ts`

---

#### US-7.8: Application Layout
**As a** user, **I want** a clean three-panel layout, **so that** I manage meetings efficiently.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-7.8.1 | Left sidebar: meeting list | ⃣ |
| AC-7.8.2 | Center: transcript/summary display | ⃣ |
| AC-7.8.3 | Right: details, action items, and speaker map | ⃣ |
| AC-7.8.4 | Dark/light mode toggle implementation | ⃣ |
| AC-7.8.5 | Responsive design (min 1024x768) | ⃣ |
| AC-7.8.6 | Implementation of lazy-loaded routes | ⃣ |

**File:** `frontend/src/app/app.component.ts` + `app.routes.ts`

---

## EPIC 8: Export & Integration

### US-8.1: Export to Markdown
**As a** user, **I want** to export meeting notes as Markdown, **so that** I paste into Confluence, Notion, or docs.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-8.1.1 | Export full summary and transcript in .md format | ⃣ |
| AC-8.1.2 | Support both direct file download and copy-to-clipboard | ⃣ |
| AC-8.1.3 | Preservation of speaker labels, timestamps, and action items | ⃣ |

**File:** `backend/export/markdown.py`

### US-8.2: REST API Documentation
**As a** developer, **I want** auto-generated API docs, **so that** I build integrations.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-8.2.1 | Swagger UI available at `/docs` (FastAPI default) | ⃣ |
| AC-8.2.2 | Full documentation of endpoints with request/response schemas | ⃣ |
| AC-8.2.3 | WebSocket protocol specific documentation in `docs/` | ⃣ |

### US-8.3: Action Item Tracker
**As a** user, **I want** a consolidated view of all action items across meetings, **so that** I track follow-ups.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-8.3.1 | Aggregated dashboard of action items from all meetings | ⃣ |
| AC-8.3.2 | Filtering by owner, status, meeting, and date | ⃣ |
| AC-8.3.3 | Ability to mark items as done or in-progress | ⃣ |
| AC-8.3.4 | Deep-link back to source meeting and specific timestamp | ⃣ |

---

## EPIC 9: SimulStreaming LIVE Policy

### US-9.1: SimulStreaming AlignAtt Integration
**As a** user, **I want** stable, non-flickering real-time transcription, **so that** text doesn't constantly change while I read.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-9.1.1 | AlignAtt policy: emit only confirmed/stable text segments | ⃣ |
| AC-9.1.2 | Backend wrapper for Whisper large-v3 or Parakeet | ⃣ |
| AC-9.1.3 | Silero VAD integration for silence detection | ⃣ |
| AC-9.1.4 | Prompt injection support for hotwords/terminology | ⃣ |
| AC-9.1.5 | Context maintenance across 30s audio buffers | ⃣ |
| AC-9.1.6 | TCP server mode for direct audio input | ⃣ |
| AC-9.1.7 | Sub-3 second commit latency for live text | ⃣ |
| AC-9.1.8 | Unbounded long-form support (no OOM on 3-hour+ meetings) | ⃣ |

**File:** `backend/asr/simulstreaming_engine.py`

---

## EPIC 10: NVIDIA Parakeet Vietnamese ASR

### US-10.1: Parakeet-CTC-0.6B-Vietnamese Engine
**As a** Vietnamese speaker, **I want** the best Vietnamese ASR with auto-punctuation, **so that** my meetings produce production-quality text.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-10.1.1 | Load nvidia/parakeet-ctc-0.6b-vi via NeMo/Transformers | ⃣ |
| AC-10.1.2 | Timestamps for words, segments, and characters | ⃣ |
| AC-10.1.3 | Qwen3-trained auto punctuation and capitalization | ⃣ |
| AC-10.1.4 | Support for Vietnamese-English code-switching | ⃣ |
| AC-10.1.5 | KenLM language model boosting (Vietnamese Wikipedia) | ⃣ |
| AC-10.1.6 | Optimized performance within ~2GB VRAM | ⃣ |
| AC-10.1.7 | NeMo chunked streaming inference implementation | ⃣ |
| AC-10.1.8 | Compliance with NVIDIA Open Model License | ⃣ |

**File:** `backend/asr/parakeet_engine.py`

---

## EPIC 11: whisper-asr-webservice Microservice

### US-11.1: Docker ASR Container
**As a** deployer, **I want** a Docker container with REST ASR API, **so that** any client can POST audio and get transcription.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-11.1.1 | docker-compose service configuration on port 9000 | ⃣ |
| AC-11.1.2 | NVIDIA GPU passthrough for CUDA acceleration | ⃣ |
| AC-11.1.3 | Support for faster-whisper and WhisperX (diarization) | ⃣ |
| AC-11.1.4 | REST endpoint: POST `/asr` returns transcript JSON | ⃣ |
| AC-11.1.5 | Model caching via persistent volume mounts | ⃣ |

**File:** `docker-compose.yml`

---

## EPIC 12: Electron Desktop App

### US-12.1: Electron Shell with System Audio
**As a** desktop user, **I want** a native app with system tray, hotkeys, and system audio capture, **so that** MeetScribe feels like a native app.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-12.1.1 | Wrap Angular production build in Electron shell | ⃣ |
| AC-12.1.2 | System tray indicators: Green (Idle), Red (Rec), Blue (Proc) | ⃣ |
| AC-12.1.3 | Configurable global hotkey (Default: Ctrl+Shift+R) | ⃣ |
| AC-12.1.4 | desktopCapturer integration for system audio | ⃣ |
| AC-12.1.5 | Enforce macOS loopback audio flag | ⃣ |
| AC-12.1.6 | Fallback to Rust/Swift IPC audio tap for macOS silent streams | ⃣ |
| AC-12.1.7 | Native OS notification for "Meeting notes ready!" | ⃣ |
| AC-12.1.8 | Auto-start functionality with OS boot | ⃣ |
| AC-12.1.9 | Build installers for .exe (Win), .dmg (Mac), .AppImage (Linux) | ⃣ |

**Files:** `electron/main.ts`, `electron/tray.ts`, `electron/audio-tap.ts`

---

## EPIC 13: Flutter Mobile App

### US-13.1: On-Device Vietnamese Transcription
**As a** mobile user, **I want** offline Vietnamese transcription on my phone, **so that** I capture meetings without a server.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-13.1.1 | Whisper small (Q4 quantized) via fonnx (~100MB) | ⃣ |
| AC-13.1.2 | Silero VAD via fonnx for silence skipping/battery saving | ⃣ |
| AC-13.1.3 | CoreML (iOS) and NNAPI (Android) acceleration | ⃣ |
| AC-13.1.4 | Keep total on-device model footprint around ~130MB | ⃣ |

**File:** `mobile/lib/core/services/on_device_transcriber.dart`

### US-13.2: On-Device Speaker Diarization
**As a** mobile user, **I want** basic speaker identification on-device, **so that** I know who said what without a server.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-13.2.1 | sherpa-onnx integration with PyAnnote ONNX models | ⃣ |
| AC-13.2.2 | Utterance-based speaker segmentation (1-10 seconds) | ⃣ |
| AC-13.2.3 | Optimized model size (~20MB) | ⃣ |

**File:** `mobile/lib/core/services/on_device_diarizer.dart`

### US-13.3: Server Streaming Mode
**As a** mobile user on WiFi, **I want** to stream audio to the MeetScribe server, **so that** I get full features.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-13.3.1 | PCM 16kHz mono streaming via WebSocket to backend | ⃣ |
| AC-13.3.2 | Real-time receipt of live transcript and diarization | ⃣ |
| AC-13.3.3 | Post-meeting full summary generation | ⃣ |
| AC-13.3.4 | Push notification on POST processing completion | ⃣ |

**File:** `mobile/lib/core/services/server_stream_service.dart`

### US-13.4: Background Audio Recording
**As a** mobile user, **I want** recording to continue when I switch apps, **so that** I don't lose meeting audio.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-13.4.1 | Android Foreground Service (Microphone type) | ⃣ |
| AC-13.4.2 | Request POST_NOTIFICATIONS permission | ⃣ |
| AC-13.4.3 | iOS BackgroundModes audio configuration in Info.plist | ⃣ |
| AC-13.4.4 | iOS AVAudioSession set to .playAndRecord category | ⃣ |
| AC-13.4.5 | Persistent notification showing active recording status | ⃣ |

**File:** `mobile/lib/core/services/background_service.dart`

### US-13.5: Flutter Consent Dialog
**As a** mobile user in Vietnam, **I want** consent requested before mic access, **so that** the app complies with Decree 356.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-13.5.1 | Modal dialog mandatory before audio capture | ⃣ |
| AC-13.5.2 | Separate consent for Recording and Voiceprint | ⃣ |
| AC-13.5.3 | Integrated permission handler for Mic and Notifications | ⃣ |
| AC-13.5.4 | Local persistence of consent status | ⃣ |

**File:** `mobile/lib/features/consent/consent_dialog.dart`

---

## EPIC 14: Compliance — Vietnam Decree 356

### US-14.1: Consent Management
**As a** data controller, **I want** granular consent tracked per meeting, **so that** I have audit evidence for Decree 356.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-14.1.1 | Track `consent_recording` and `consent_voiceprint` per meeting | ⃣ |
| AC-14.1.2 | Prevent recording start if `consent_recording` is False | ⃣ |
| AC-14.1.3 | Disable diarization if `consent_voiceprint` is False | ⃣ |
| AC-14.1.4 | Log consent timestamps in the audit log | ⃣ |

**File:** `backend/compliance/consent.py`

### US-14.2: Data Purge (Data Subject Rights)
**As a** meeting participant, **I want** to request complete deletion of my data, **so that** my Decree 356 right to erasure is respected.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-14.2.1 | `DELETE` endpoint for full meeting purge (cascading) | ⃣ |
| AC-14.2.2 | `DELETE` endpoint for independent voiceprint removal | ⃣ |
| AC-14.2.3 | Audit log entry generated for every purge request | ⃣ |
| AC-14.2.4 | Confirmation response listing all deleted entities | ⃣ |

**File:** `backend/compliance/data_purge.py`

### US-14.3: Audit Logging
**As a** compliance officer, **I want** an audit trail of all data processing, **so that** I demonstrate Decree 356 compliance.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-14.3.1 | Log events: creation, capture, transcript, voiceprint, summary, purge | ⃣ |
| AC-14.3.2 | Standardized log fields: action, entity_type/id, details, timestamp | ⃣ |
| AC-14.3.3 | Filterable `GET` endpoint for compliance audit logs | ⃣ |
| AC-14.3.4 | Immutable append-only storage for logs | ⃣ |

**File:** `backend/compliance/audit_log.py`

### US-14.4: Ephemeral Audio Processing
**As a** privacy-conscious user, **I want** raw audio destroyed after transcription, **so that** biometric audio never persists on disk.

**Acceptance Criteria**
| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-14.4.1 | Raw audio held in memory only during LIVE mode | ⃣ |
| AC-14.4.2 | Immediate destruction of audio after segment commitment | ⃣ |
| AC-14.4.3 | Save WAV only if recording consent AND explicit opt-in given | ⃣ |
| AC-14.4.4 | Default state set to `audio_retained=False` | ⃣ |

**File:** `backend/pipeline/orchestrator.py`

---

### EPIC 15: IoT Audio Streaming [P2 — Week 2]

#### US-15.1: Conference Room Audio Streamer

| AC | Criteria | Status |
|----|---------|--------|
| AC-15.1.1 | Python: sounddevice → WebSocket stream | ⃣ |
| AC-15.1.2 | Works on Raspberry Pi 4/5 | ⃣ |
| AC-15.1.3 | Auto-reconnect on network failure | ⃣ |
| AC-15.1.4 | < 50MB RAM footprint | ⃣ |

**File:** `iot/audio_streamer.py`

---


### EPIC 16: AI-First SDLC [P0 — Day 1]

#### US-16.1: Claude Code CI/CD Integration

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-16.1.1 | anthropics/claude-code-action@v1 in GitHub Actions | ⃣ |
| AC-16.1.2 | Automated architectural PR review against CLAUDE.md | ⃣ |
| AC-16.1.3 | Checks: ASR interface, GPU memory, Angular patterns, Decree 356 | ⃣ |

**File:** `.github/workflows/ai-review.yml`

#### US-16.2: Automated Testing Pipeline

| # | Acceptance Criteria | Status |
|---|-------------------|--------|
| AC-16.2.1 | Backend CI: ruff + mypy + pytest | ⃣ |
| AC-16.2.2 | Frontend CI: ng test + ng build | ⃣ |
| AC-16.2.3 | Mobile CI: dart analyze + flutter test | ⃣ |

**Files:** `.github/workflows/backend-ci.yml`, `frontend-ci.yml`, `mobile-ci.yml`

---

## 17. Non-Functional Requirements

| Category | Requirement | | Metric | Target |
|----------|--------------|--------|--------|
| **Latency** | Transcription latency | Speech → screen | < 3 seconds |
| **Latency** | POST processing | 1hr meeting → summary | < 30 seconds |
| **Latency** | Search | FTS5 across 1000 meetings | < 500ms |
| **Latency** | App startup | Cold start to ready | < 5 seconds |
| **Accuracy** | Vietnamese WER | Parakeet / Qwen3-ASR | < 10% |
| **Accuracy** | English WER | faster-whisper / VibeVoice | < 5% |
| **Accuracy** | Speaker diarization accuracy | Speaker attribution | ≥ 90% |
| **Memory** | App memory | Excluding models | < 2 GB |
| **Security** | Data at rest | Encryption | SQLCipher AES-256 |
| **Security** | Data in transit | Encryption | WSS / TLS 1.3 |
| **Security** | Biometric data | Default storage | Ephemeral (RAM only) |
| **Compliance** | Compliance | Vietnam Decree 356 | Full |
| **Platform** | Desktop platforms | Supported | Windows 10+, macOS 13+, Linux |
| **Platform** | Mobile platforms | Supported | iOS 16+, Android 12+ |
| **GPU** | GPU LIVE budget | RTX 3090 | ≤ 5-7 GB |
| **GPU** | GPU POST budget | RTX 3090 | ≤ 12 GB |
| **ASR** | ASR engines | Pluggable count | 10 |
| **LLM** | LLM providers | Pluggable count | 7 |
| **LLM** | Summary templates | Built-in count | 12 (VN + EN) |

---

## 18. Compliance — Vietnam Decree 356

### 18.1 Classification
- **Biometric data (voiceprints)** = Sensitive Personal Data under Decree 356
- MeetScribe processes voiceprints → **no grace period exemption**
- **PDP personnel appointment mandatory** (2+ years legal/IT/security experience)

### 18.2 Architectural Safeguards (Implemented)

| Requirement | Implementation | File |
|-------------|---------------|------|
| Granular consent | Consent dialog (Angular + Electron + Flutter) before mic | consent.py, consent-dialog.component.ts |
| Encryption at rest | SQLCipher AES-256-CBC | database.py |
| Encryption in transit | WSS (TLS 1.3) mandatory in production | main.py |
| Ephemeral audio | RAM-only during LIVE, destroyed after commit | orchestrator.py, recorder.py |
| Data subject rights | CASCADE DELETE purge | data_purge.py |
| Voiceprint isolation | Separate table, independent DELETE | speaker_profiles.py |
| Audit trail | Append-only audit_log table | audit_log.py |
| Edge computing | Flutter on-device = biometric data never leaves device | on_device_transcriber.dart |

---

## 19. AI-First SDLC

### 19.1 Development Pipeline

| Phase | Tool | Automation |
|-------|------|-----------|
| Code generation | Claude Code CLI | 54 steps from CLAUDE.md |
| Code review | claude-code-action@v1 | Every PR auto-reviewed |
| Unit testing | pytest + karma + flutter_test | Per-platform CI |
| E2E testing | QA Wolf (Playwright) | Agentic test generation |
| Visual regression | Applitools | GenUI consistency |
| Linting | ruff + Angular lint + dart analyze | Pre-merge checks |
| Coverage | pytest-cov + karma coverage | Tracked per merge |

### 19.2 Custom Claude Code Commands

| Command | Purpose | File |
|---------|---------|------|
| `/test` | Run full test suite, fix failures, report | `.claude/commands/test.md` |
| `/verify` | Build check + test + smoke test | `.claude/commands/verify.md` |

---

## 20. Multi-Platform Strategy

| Platform | Stack | Features | Priority |
|----------|-------|----------|----------|
| **Web** | Angular 21 (zoneless, Signals+RxJS) | Full features | P0 — Week 1 |
| **Desktop** | Electron 40 (wraps Angular) | + System tray, hotkeys, system audio | P1 — Week 1 |
| **Mobile** | Flutter (fonnx, sherpa-onnx, Riverpod) | On-device ASR + server mode | P2 — Week 2 |
| **IoT** | Python WebSocket client | Audio streamer only | P2 — Week 2 |
| **Docker** | whisper-asr-webservice | REST ASR microservice | P1 — Week 1 |

---

## 21. Risk & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|-----------|
| Parakeet Vietnamese accuracy insufficient | High | Low | Benchmark vs Qwen3-ASR + PhoWhisper; auto-fallback |
| VibeVoice 7B OOM on RTX 3090 bf16 | High | Medium | Use 4-bit NF4 (~7GB); DGX Spark for full precision |
| Electron macOS silent audio stream | High | Medium | CoreAudio Tap flag + IPC audio tap fallback |
| diart + ASR GPU contention | Medium | Low | Parakeet 2GB + diart 2GB = 4GB total, fits easily |
| SimulStreaming latency too high | Medium | Low | Tune AlignAtt; fall back to LocalAgreement |
| Qwen3-ASR not yet widely tested for VN | Medium | Medium | Keep Parakeet as primary; Qwen3-ASR as alternative |
| Flutter fonnx model too large for old phones | Medium | Medium | Use whisper-tiny (39MB); or server mode |
| Decree 356 voiceprint violation | Critical | Low | Consent mandatory; ephemeral audio; edge priority |
| Vietnamese diacritics corruption | Medium | Low | UTF-8 everywhere; tested with tonal edge cases |
| LLM provider API changes | Low | Medium | 7 providers = redundancy; Ollama local always available |

---

## 22. Release Plan & Sprint Execution

### Executed Sprint (5 days, completed via Claude Code in 30 minutes)

| Day | Deliverables | Status |
|-----|-------------|--------|
| **Day 1** | Audio capture, ASR base, Parakeet, faster-whisper, language router, FastAPI, WebSocket | ⃣ Complete |
| **Day 2** | diart diarization, pipeline orchestrator, VibeVoice, SimulStreaming, all LLM providers, storage, compliance | ⃣ Complete |
| **Day 3** | Angular 21 project: 7 feature components, WebSocket→RxJS→Signal, dark theme | ⃣ Complete |
| **Day 4** | Electron shell (tray, hotkeys, macOS fix), export (markdown, clipboard) | ⃣ Complete |
| **Day 5** | Flutter mobile (6 screens, Riverpod, WebSocket), IoT audio streamer | ⃣ Complete |

### Next Steps

| # | Task | Priority |
|---|------|----------|
| 1 | Unit tests for all 54 files | P0 |
| 2 | Integration tests (E2E with real Vietnamese audio) | P0 |
| 3 | Maxine SDK integration (noise removal) | P1 |
| 4 | Flutter on-device ONNX models (fonnx + sherpa-onnx) | P1 |
| 5 | electron-builder production installers | P1 |
| 6 | Performance benchmark on RTX 3090 | P1 |
| 7 | Qwen3-ASR benchmark vs Parakeet for Vietnamese | P1 |
| 8 | WhisperLiveKit integration testing | P2 |
| 9 | GenUI components (Angular Genkit + Flutter GenUI SDK) | P2 |
| 10 | NVIDIA NIM packaging for Parakeet | P2 |

---

## 23. Implementation Status

### Summary

| Metric | Count |
|--------|-------|
| **Development steps completed** | **54 / 54** |
| **ASR engines registered** | **10** |
| **LLM templates created** | **12** (6 types × 2 languages) |
| **LLM providers** | **7** |
| **Angular components** | **7 feature modules** |
| **Flutter screens** | **6** |
| **GitHub Actions workflows** | **4** |
| **Database tables** | **12** (SQLCipher encrypted) |
| **REST API endpoints** | **15+** |
| **WebSocket endpoints** | **2** (/ws/transcript/, /ws/audio/) |
| **Claude Code build time** | **29 minutes 55 seconds** |

### File Inventory (54 files created by Claude Code)

**Backend (34 files):**
```
backend/main.py, config.py, database.py
backend/audio/capture.py, devices.py, recorder.py, file_import.py, maxine_preprocessor.py
backend/asr/base.py, engine_factory.py, parakeet_engine.py, qwen3_asr_engine.py,
  faster_whisper_engine.py, vibevoice_engine.py, simulstreaming_engine.py,
  whisperlivekit_engine.py, phowhisper_engine.py, gasr_engine.py, cloud_engine.py,
  whisper_asr_client.py, language_router.py
backend/diarization/live_diarization.py, offline_diarization.py, speaker_profiles.py
backend/llm/base.py, ollama_provider.py, claude_provider.py, multi_providers.py, summarizer.py
backend/llm/templates/ (12 YAML files)
backend/pipeline/orchestrator.py
backend/storage/models.py, repository.py, search.py, embeddings.py
backend/compliance/consent.py, data_purge.py, audit_log.py
backend/api/websocket.py, recording.py, meetings.py, search.py, settings.py, compliance.py, engines.py
backend/export/markdown.py, clipboard.py
```

**Frontend — Angular 21 (7 feature modules):**
```
frontend/src/app/core/services/transcript-stream.service.ts, recording.service.ts,
  meeting.service.ts, websocket.service.ts
frontend/src/app/features/consent/, recording/, transcript/, summary/, meetings/, search/, settings/
```

**Desktop — Electron 40:**
```
electron/main.ts, tray.ts, package.json
```

**Mobile — Flutter:**
```
mobile/lib/ (6 screens + services + providers)
```

**IoT:**
```
iot/audio_streamer.py
```

**CI/CD:**
```
.github/workflows/ai-review.yml, backend-ci.yml, frontend-ci.yml, mobile-ci.yml
```

**Infrastructure:**
```
CLAUDE.md, README.md, README-DEVELOPER.md, pyproject.toml, docker-compose.yml,
docker/Dockerfile, .env.example, .gitignore, .gitmodules, scripts/download_models.py
```

---

*End of PRD v4.1 FINAL — MeetScribe AI Meeting Intelligence Platform*
*14 EPICs | 50+ User Stories | 150+ Acceptance Criteria | 10 ASR Engines | 7 LLM Providers | 4 Platforms*
*Built in 29m 55s by Claude Code following CLAUDE.md*

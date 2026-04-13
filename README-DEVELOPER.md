# 🛠️ MeetScribe — Developer Bootstrap Guide
## How to Set Up AI-First Development from Scratch with Claude Code

> **This guide is for YOU, the developer.** It walks you through setting up your machine,
> configuring Claude Code, and launching autonomous AI-First development.
> For end-user installation, see `README.md` instead.

Note: Cursor Rules got from - https://github.com/PatrickJS/awesome-cursorrules
---

## Table of Contents

1. [Machine Setup (One-Time)](#1-machine-setup-one-time)
2. [Project Initialization](#2-project-initialization)
3. [Claude Code Setup](#3-claude-code-setup)
4. [GitHub Repository + CI/CD](#4-github-repository--cicd)
5. [Starting AI-First Development](#5-starting-ai-first-development)
6. [Day-by-Day Development Playbook](#6-day-by-day-development-playbook)
7. [Working with Claude Code Effectively](#7-working-with-claude-code-effectively)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Machine Setup (One-Time)

### 1.1 Operating System

**Recommended:** Ubuntu 24.04 LTS or Windows 11 with WSL2
**Also works:** macOS 14+ (Sonoma), Fedora 40+

If on Windows, install WSL2 first:
```powershell
wsl --install -d Ubuntu-24.04
```

### 1.2 NVIDIA GPU Driver + CUDA

```bash
# Check GPU
nvidia-smi

# If no driver installed:
# Ubuntu:
sudo apt update
sudo apt install -y nvidia-driver-560
sudo reboot

# Install CUDA Toolkit 12.6
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt install -y cuda-toolkit-12-6

# Add to PATH (add to ~/.bashrc)
export PATH=/usr/local/cuda-12.6/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-12.6/lib64:$LD_LIBRARY_PATH

# Verify
nvcc --version
# Expected: cuda_12.6.x
```

### 1.3 Python 3.11

```bash
# Ubuntu
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Verify
python3.11 --version
```

### 1.4 Node.js 22 LTS

```bash
# Using nvm (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 22
nvm use 22
nvm alias default 22

# Verify
node --version  # v22.x.x
npm --version   # 10.x.x
```

### 1.5 Angular CLI 21

```bash
npm install -g @angular/cli@21

# Verify
ng version
```

### 1.6 Flutter (Latest Stable)

```bash
# Linux
sudo snap install flutter --classic
# OR follow: https://docs.flutter.dev/get-started/install/linux/desktop

# Verify
flutter doctor -v
# Fix any issues flutter doctor reports
```

### 1.7 FFmpeg

```bash
sudo apt install -y ffmpeg
ffmpeg -version
```

### 1.8 SQLCipher

```bash
# Ubuntu
sudo apt install -y sqlcipher libsqlcipher-dev

# Verify
sqlcipher --version
```

### 1.9 Docker + NVIDIA Container Toolkit

```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# NVIDIA Container Toolkit (for GPU in Docker)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi
```

### 1.10 Ollama (Local LLM)

```bash
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the default model
ollama pull qwen3:8b

# Verify
ollama list
# Should show qwen3:8b
```

### 1.11 HuggingFace CLI

```bash
pip install huggingface-hub
huggingface-cli login
# Paste your token from https://huggingface.co/settings/tokens

# REQUIRED: Accept pyannote model licenses (needed for diart diarization)
# Visit each URL and click "Agree":
#   https://huggingface.co/pyannote/segmentation-3.0
#   https://huggingface.co/pyannote/embedding
```

### 1.12 Git + Git LFS

```bash
sudo apt install -y git git-lfs
git lfs install
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

### 1.13 Claude Code CLI

```bash
# Install
npm install -g @anthropic-ai/claude-code

# Authenticate (requires Anthropic API key or Claude Pro/Max subscription)
claude login

# Verify
claude --version
```

**Important:** Claude Code requires one of:
- An Anthropic API key with sufficient credits
- A Claude Pro or Claude Max subscription

### 1.14 Verification Checklist

Run this to verify everything is installed:

```bash
echo "=== MeetScribe Dev Environment Check ==="
echo -n "Python 3.11: " && python3.12 --version 2>&1 | head -1
echo -n "Node.js:     " && node --version
echo -n "npm:         " && npm --version
echo -n "Angular CLI: " && ng version 2>&1 | grep "Angular CLI" || echo "NOT FOUND"
echo -n "Flutter:     " && flutter --version 2>&1 | head -1
echo -n "CUDA:        " && nvcc --version 2>&1 | grep release || echo "NOT FOUND"
echo -n "Docker:      " && docker --version
echo -n "Ollama:      " && ollama --version 2>&1 | head -1 || echo "NOT FOUND"
echo -n "FFmpeg:      " && ffmpeg -version 2>&1 | head -1
echo -n "SQLCipher:   " && sqlcipher --version 2>&1 | head -1 || echo "NOT FOUND"
echo -n "Git LFS:     " && git lfs version
echo -n "Claude Code: " && claude --version 2>&1 || echo "NOT FOUND"
echo -n "GPU:         " && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>&1 | head -1
echo "========================================="
```

Expected output: all tools show version numbers, GPU shows your RTX 3090 with 24GB.

---

## 2. Project Initialization

### 2.1 Clone or Create the Project

**If you have the bootstrap package:**
```bash
# Copy the scaffold to your projects directory
cp -r /path/to/meetscribe ~/projects/meetscribe
cd ~/projects/meetscribe
```

**If starting from a GitHub repo:**
```bash
git clone --recurse-submodules https://github.com/YOUR_ORG/meetscribe.git
cd meetscribe
```

### 2.2 Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit with your values — AT MINIMUM set these:
nano .env
```

**Minimum .env changes required:**
```env
# REQUIRED: Set a strong passphrase for database encryption
MEETSCRIBE_DB_KEY=your_very_secure_passphrase_at_least_32_characters_long

# REQUIRED: For pyannote/diart diarization models
HUGGINGFACE_TOKEN=hf_your_token_here

# RECOMMENDED: For Claude Code CI/CD and LLM summarization
ANTHROPIC_API_KEY=sk-ant-your_key_here
```

### 2.3 Python Virtual Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate

# Install all dependencies
pip install -e ".[dev]"
```

### 2.4 Download ASR Models (First Time)

This takes 10-60 minutes depending on internet speed. Run in background:

```bash
# Essential (start with these)
python scripts/download_models.py --engine parakeet-vi
python scripts/download_models.py --engine faster-whisper --size large-v3
python scripts/download_models.py --engine diart
python scripts/download_models.py --engine embeddings

# Optional (can download later)
python scripts/download_models.py --engine vibevoice --quantization 4bit
python scripts/download_models.py --engine phowhisper --size large
```

### 2.5 Start Docker Services

```bash
# Start the whisper-asr-webservice microservice
docker compose up -d whisper-asr

# Verify it's running
curl http://localhost:9000/docs
# Should return Swagger UI HTML
```

### 2.6 Verify Backend Starts

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --port 9876
# Expected: Uvicorn running on http://0.0.0.0:9876
# (Will fail if backend/main.py not yet created — that's OK, Claude Code will build it)
```

---

## 3. Claude Code Setup

### 3.1 Configure Claude Code for MeetScribe

Claude Code reads `CLAUDE.md` in the project root automatically. This file contains:
- All architectural rules (15 mandatory rules)
- Every tech stack component with versions
- Full ASR engine interface with code
- Database schema
- API endpoints
- Angular/Flutter/Electron patterns
- 54-step development sequence
- Decree 356 compliance rules

**You don't need to configure anything else.** Just ensure `CLAUDE.md` exists in the project root.

### 3.2 Claude Code Session Workflow

```bash
cd ~/projects/meetscribe

# Start Claude Code
claude

# Claude Code will:
# 1. Read CLAUDE.md automatically
# 2. Understand the full architecture
# 3. Wait for your instructions
```

### 3.3 Recommended First Commands

```
# Phase 1 — Start here
> Read CLAUDE.md completely. Then create backend/asr/base.py with the ASREngine 
  abstract class and TranscriptSegment dataclass exactly as specified in §4.1.

# After base.py is created
> Now create backend/database.py with SQLCipher connection setup and the full 
  schema from CLAUDE.md §6. Use the MEETSCRIBE_DB_KEY from config.

# Continue Phase 1
> Create backend/main.py — FastAPI app with uvloop, ORJSONResponse, CORS, 
  and the WebSocket endpoint /ws/transcript/{meeting_id} as specified in §7.2.
```

### 3.4 Context Management

Claude Code has a context window. For large tasks:

```
# Good: specific, one-file-at-a-time
> Create backend/asr/parakeet_engine.py implementing ASREngine for NVIDIA 
  Parakeet-CTC-0.6B-Vi as specified in CLAUDE.md §4.

# Bad: too vague, too much at once
> Build the entire backend
```

Break work into file-level tasks. Claude Code is most effective when it can focus on one component at a time while understanding how it fits into the architecture via `CLAUDE.md`.

---

## 4. GitHub Repository + CI/CD

### 4.1 Create GitHub Repository

```bash
cd ~/projects/meetscribe
git init
git add -A
git commit -m "Initial scaffold: CLAUDE.md, pyproject.toml, CI/CD workflows, project structure"

# Create repo on GitHub (via CLI or web)
gh repo create meetscribe --private --source=. --push
# OR
git remote add origin https://github.com/YOUR_ORG/meetscribe.git
git push -u origin main
```

### 4.2 Configure GitHub Secrets

Go to GitHub → Settings → Secrets and Variables → Actions → New repository secret:

| Secret Name | Value | Required For |
|-------------|-------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Claude Code AI review |
| `HUGGINGFACE_TOKEN` | Your HuggingFace token | Model downloads in CI |
| `CODECOV_TOKEN` | From codecov.io | Code coverage reports |

### 4.3 Branch Strategy

```
main          ← production-ready code
├── develop   ← integration branch
│   ├── feature/phase-1-backend-core
│   ├── feature/phase-2-pipeline
│   ├── feature/phase-3-angular
│   ├── feature/phase-4-electron
│   └── feature/phase-5-flutter
```

### 4.4 How CI/CD Works

On every Pull Request:
1. **`ai-review.yml`** — Claude Code reads the diff, checks against `CLAUDE.md` rules, posts review comments
2. **`backend-ci.yml`** — Runs `ruff check` + `mypy` + `pytest`
3. **`frontend-ci.yml`** — Runs `ng test` + `ng build`
4. **`mobile-ci.yml`** — Runs `dart analyze` + `flutter test`

All four must pass before merge.

### 4.5 Development Loop

```
1. Create feature branch:  git checkout -b feature/asr-parakeet-engine
2. Open Claude Code:        claude
3. Instruct:               > Create backend/asr/parakeet_engine.py per CLAUDE.md §4
4. Review what Claude Code generates
5. Run tests locally:       pytest tests/backend/ -v
6. Commit + push:           git add -A && git commit -m "feat: Parakeet ASR engine" && git push
7. Create PR on GitHub
8. Claude Code AI review runs automatically
9. Address review comments
10. Merge when CI is green
```

---

## 5. Starting AI-First Development

### 5.1 The CLAUDE.md §15 Development Sequence

Claude Code follows a specific 54-step sequence defined in `CLAUDE.md §15`. Here's how to execute it:

**You give the commands. Claude Code does the coding.**

### Phase 1 — Backend Core (Day 1)

Open Claude Code and issue these commands one by one:

```
> Read CLAUDE.md. Create step 1: pyproject.toml is already done. 
  Create step 2: backend/config.py if not complete, verify against §3.1.

> Create step 3: backend/database.py — SQLCipher connection with full schema from §6.
  Include migration support and the ensure_schema() function.

> Create step 4: backend/asr/base.py — ASREngine ABC and TranscriptSegment exactly as §4.1.

> Create step 5: backend/asr/engine_factory.py — registry and factory per §4.2.

> Create step 6: backend/audio/capture.py — AudioCapture class with sounddevice, 
  WASAPI loopback on Windows, PulseAudio monitor on Linux. 16kHz mono PCM.

> Create step 7: backend/audio/devices.py — enumerate audio devices.

> Create step 8: backend/audio/recorder.py — RecordingSession that saves WAV.

> Create step 9: backend/asr/faster_whisper_engine.py — implements ASREngine 
  with faster-whisper. Include streaming via 30s sliding window.

> Create step 10: backend/asr/parakeet_engine.py — implements ASREngine 
  for nvidia/parakeet-ctc-0.6b-vi via NeMo. Include KenLM boosting. §4.

> Create step 11: backend/asr/language_router.py — per §4.3.

> Create step 12: backend/main.py — FastAPI with uvloop, ORJSONResponse, CORS, 
  mount static files, include all routers. §7.

> Create step 13: backend/api/websocket.py — WebSocket handler per §7.2.

> Create step 14: backend/api/recording.py — start/stop/pause endpoints per §7.1.
```

### Phase 2 — Pipeline + Diarization (Day 2)

```
> Create step 15: backend/diarization/live_diarization.py — diart integration,
  SpeakerDiarization pipeline, 500ms streaming, WebSocket output.

> Create step 16: backend/pipeline/orchestrator.py — MeetingOrchestrator 
  per CLAUDE.md §11. LIVE path + POST path. GPU model lifecycle management.

> Create step 17: backend/asr/vibevoice_engine.py — VibeVoice-ASR 7B 
  with 4-bit quantization, JSON output parsing. POST mode only.

> Create step 18: backend/asr/simulstreaming_engine.py — wraps SimulStreaming 
  AlignAtt as subprocess with TCP interface.

> Create steps 19-20: backend/llm/base.py, ollama_provider.py, claude_provider.py.

> Create step 21: backend/llm/summarizer.py + all templates in templates/ directory.
  Include Vietnamese templates per CLAUDE.md §5.3.

> Create step 22: backend/storage/repository.py — full CRUD for all tables.
  Use aiosqlite. Never raw SQL in API routes.

> Create step 23: backend/api/meetings.py + backend/api/search.py per §7.1.

> Create steps 24-25: backend/compliance/ — consent.py, data_purge.py, audit_log.py.
  Per §12 Decree 356 rules.

> Create step 26: backend/api/compliance.py — consent + purge + audit endpoints.
```

### Phase 3 — Angular Frontend (Day 3-4)

```
> Initialize Angular project: cd frontend && ng new meetscribe-web --standalone 
  --style=css --routing --ssr=false. Then configure Tailwind CSS 4 and proxy to :9876.

> Create core/services/websocket.service.ts — generic WebSocket wrapper using rxjs/webSocket.

> Create core/services/transcript-stream.service.ts — the RxJS → Signal pipeline 
  exactly as shown in CLAUDE.md §8.2. This is the most critical Angular component.

> Create core/services/recording.service.ts — POST to /api/recording/start|stop.

> Create core/services/meeting.service.ts — GET/POST /api/meetings/*.

> Create core/models/ — TypeScript interfaces matching backend TranscriptSegment, 
  Meeting, Summary, ActionItem, Settings.

> Create features/consent/consent-dialog.component.ts — Decree 356 consent modal.
  Two checkboxes: recording consent + voiceprint consent. Blocks until accepted.

> Create features/recording/recording-controls.component.ts — record button, 
  device selectors, engine selector, audio level meters, language indicator.

> Create features/transcript/live-transcript.component.ts — auto-scrolling transcript
  with speaker colors, timestamps, confidence underline. Uses Signals from 
  TranscriptStreamService. @for loop with track by start_time.

> Create features/summary/summary-view.component.ts — rendered markdown, 
  action item checklist, re-generate button, copy to clipboard.

> Create features/meetings/meeting-list.component.ts — sidebar chronological list
  with search, filter by language/date.

> Create features/search/search-bar.component.ts — full-text + semantic search.

> Create features/settings/settings-panel.component.ts — ASR engine picker, 
  LLM provider, audio devices, language, hotwords, GPU info.

> Create app.routes.ts with lazy-loaded routes and app.component.ts with 
  three-panel layout: sidebar | main | detail. Dark/light mode toggle.
```

### Phase 4 — Electron + Polish (Day 4-5)

```
> Create electron/package.json with electron@40 and electron-builder dependencies.

> Create electron/main.ts — Electron entry point. Include:
  - MacLoopbackAudioForScreenShare flag per CLAUDE.md §10
  - System tray (green/red/blue)
  - Global hotkey Ctrl+Shift+R
  - Load Angular production build
  - Spawn Python backend as child process (optional)

> Create electron/preload.ts and electron/tray.ts.

> Create electron-builder.yml for Win/Mac/Linux builds.

> Create backend/export/markdown.py + backend/export/clipboard.py.

> Create backend/asr/gasr_engine.py — GASR/SODA CPU fallback per CLAUDE.md §4.

> Create backend/audio/file_import.py — import audio/video via FFmpeg.

> Create tests/backend/test_asr_base.py — test ASREngine interface contract.

> Create tests/backend/test_database.py — test SQLCipher schema creation.

> Create tests/backend/test_api.py — test REST endpoints with httpx.
```

### Phase 5 — Flutter Mobile (Week 2)

```
> Create Flutter project: cd mobile && flutter create meetscribe_mobile --platforms=android,ios

> Update pubspec.yaml with: riverpod, go_router, fonnx, sherpa_onnx, record, 
  web_socket_channel, dio, permission_handler, hive.

> Create lib/core/services/audio_capture_service.dart — record package, 
  PCM 16-bit 16kHz, background streaming.

> Create lib/core/services/on_device_transcriber.dart — fonnx Whisper ONNX.

> Create lib/core/services/on_device_diarizer.dart — sherpa-onnx PyAnnote.

> Create lib/core/services/server_stream_service.dart — WebSocket to backend.

> Create lib/core/services/background_service.dart — Android Foreground Service 
  + iOS Audio Session for background recording.

> Create lib/features/consent/consent_dialog.dart — Decree 356.

> Create lib/features/recording/recording_screen.dart — record UI.

> Create lib/features/transcript/live_transcript_screen.dart — real-time display.

> Configure Android: AndroidManifest.xml with FOREGROUND_SERVICE_TYPE_MICROPHONE.

> Configure iOS: Info.plist with UIBackgroundModes:audio + NSMicrophoneUsageDescription.

> Create iot/audio_streamer.py — Raspberry Pi WebSocket audio client.
```

---

## 6. Day-by-Day Development Playbook

| Day | Morning (4h) | Afternoon (4h) | Deliverable |
|-----|-------------|----------------|-------------|
| **Mon** | Backend: config, database, ASR base, engine factory, audio capture | ASR engines (Parakeet, faster-whisper), language router, FastAPI skeleton, WebSocket | Backend records audio, transcribes, streams to WebSocket |
| **Tue** | diart diarization, pipeline orchestrator (LIVE path) | VibeVoice POST engine, SimulStreaming, LLM summarizer, storage repo, compliance | Full pipeline: record → transcribe → diarize → summarize |
| **Wed** | Angular project setup, core services (WebSocket, transcript stream, recording) | UI components: consent, recording, live transcript, summary view | Web UI shows live transcript with speaker colors |
| **Thu** | Meeting list, search, settings panel, templates (VN+EN) | Export, action items, Electron shell (tray, hotkeys, macOS audio fix) | Desktop app with system audio capture |
| **Fri** | GASR CPU fallback, file import, tests (pytest + Angular karma) | CI/CD, Docker compose, README, benchmark on RTX 3090, demo | Shippable MVP with documentation |
| **Mon** | Flutter project, on-device inference (fonnx, sherpa-onnx) | Server mode WebSocket, background services, consent | Mobile app (basic) |
| **Tue** | Flutter UI polish, IoT audio streamer, integration tests | End-to-end testing, bug fixes, performance optimization | Complete multi-platform MVP |

---

## 7. Working with Claude Code Effectively

### 7.1 Best Practices

**DO:**
- Give one file/component per command
- Reference CLAUDE.md sections: "per §4.1", "following §8.2 pattern"
- Ask Claude Code to read specific files before editing: "Read backend/asr/base.py then create parakeet_engine.py"
- Test after each component: "Run pytest tests/backend/test_asr_base.py"
- Commit frequently: small, focused commits

**DON'T:**
- Ask "build the whole app" — too broad
- Skip the development sequence (§15) — components have dependencies
- Ignore Claude Code's review comments on PRs
- Put raw SQL in API routes (always use repository)
- Load GPU models in async FastAPI endpoints (use subprocess)

### 7.2 Useful Claude Code Commands

```
# Read a file
> Read CLAUDE.md §4.1 and explain the ASREngine interface

# Create a file
> Create backend/asr/parakeet_engine.py implementing ASREngine for Parakeet

# Edit a file
> In backend/main.py, add the compliance router from backend/api/compliance.py

# Run tests
> Run pytest tests/backend/ -v and fix any failures

# Debug
> The WebSocket connection drops after 30 seconds. Read backend/api/websocket.py 
  and backend/pipeline/orchestrator.py, find and fix the timeout issue.

# Architecture review
> Review backend/asr/ directory. Does every engine implement all ASREngine methods? 
  Are GPU memory budgets respected per CLAUDE.md §4.4?
```

### 7.3 When Claude Code Gets Stuck

```
# Reset context
> Read CLAUDE.md again from the beginning. We are on Phase 2, step 17.
  The current state: backend/asr/base.py and faster_whisper_engine.py exist and work.
  Now create vibevoice_engine.py.

# Be more specific
> The TranscriptSegment needs a 'source' field that defaults to 'live'. 
  Add it to backend/asr/base.py, then update all engines that create TranscriptSegment.
```

---

## 8. Troubleshooting

### Claude Code can't find CLAUDE.md
```bash
# Ensure you're in the project root
pwd  # Should show /path/to/meetscribe
ls CLAUDE.md  # Should exist
claude  # Start Claude Code from this directory
```

### pip install fails on nemo_toolkit
```bash
# NeMo has heavy dependencies. Install PyTorch first:
pip install torch==2.4.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cu126
# Then retry:
pip install -e ".[dev]"
```

### SQLCipher import error
```bash
# Ubuntu
sudo apt install -y libsqlcipher-dev
pip install sqlcipher3-binary --force-reinstall
```

### CUDA out of memory
```bash
# Check what's using GPU
nvidia-smi

# Kill any leftover processes
nvidia-smi --query-compute-apps=pid --format=csv,noheader | xargs -I {} kill -9 {}

# Start with smaller model for development
# In .env: MEETSCRIBE_ASR_LIVE_ENGINE=faster-whisper
# And use model "small" instead of "large-v3"
```

### Angular CLI not found after install
```bash
# Use npx instead
npx ng serve
# Or ensure global bin is in PATH
npm config get prefix  # Check global install path
```

### Docker GPU not working
```bash
# Verify nvidia-container-toolkit
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi
# If fails: sudo systemctl restart docker
```

### Ollama model too slow
```bash
# Check if GPU is being used
ollama ps
# If CPU: ensure NVIDIA driver is installed and Ollama can see it
CUDA_VISIBLE_DEVICES=0 ollama run qwen3:8b "Hello"
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│  MeetScribe Developer Quick Reference                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Start backend:    uvicorn backend.main:app --reload :9876   │
│  Start frontend:   cd frontend && ng serve :4200             │
│  Start Electron:   cd electron && npm run dev                │
│  Start Flutter:    cd mobile && flutter run                  │
│  Start Docker:     docker compose up -d                      │
│  Start Claude:     claude                                    │
│                                                              │
│  Run tests:        pytest tests/ -v                          │
│                    cd frontend && ng test                     │
│                    cd mobile && flutter test                  │
│                                                              │
│  Download models:  python scripts/download_models.py --list  │
│  GPU check:        nvidia-smi                                │
│  Ollama check:     ollama list                               │
│                                                              │
│  Key files:                                                  │
│    CLAUDE.md       ← AI reads this (architecture)            │
│    README.md       ← End-users read this (setup)             │
│    README-DEV.md   ← You read this (dev bootstrap)           │
│    .env            ← Your local config (never commit)        │
│    pyproject.toml  ← Python dependencies                     │
│                                                              │
│  Key URLs:                                                   │
│    Backend API:    http://localhost:9876/docs                 │
│    Angular UI:     http://localhost:4200                      │
│    Whisper ASR:    http://localhost:9000/docs                 │
│    Ollama:         http://localhost:11434                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

**You're ready. Start Claude Code and build MeetScribe. 🚀**

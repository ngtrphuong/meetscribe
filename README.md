# 🎙️ MeetScribe — AI Meeting Intelligence Platform

> Vietnamese-first, local-first, AI-native meeting notes that run on YOUR hardware.

MeetScribe captures, transcribes, identifies speakers, and generates structured meeting summaries — all in real-time, all locally, all private. Built for Vietnamese + English bilingual meetings with code-switching support.

---

## 🚀 What MeetScribe Does

| During Meeting | After Meeting |
|---------------|---------------|
| Real-time Vietnamese/English transcription | High-accuracy reprocessing via VibeVoice-ASR 7B |
| Live speaker identification (who said what) | Structured summary: decisions, action items, follow-ups |
| Audio level monitoring | Searchable meeting library (keyword + semantic) |
| Language auto-detection (VN/EN/mixed) | Export: Markdown, clipboard, DOCX |

**Platforms:** Web (Angular) → Desktop (Electron) → Mobile (Flutter) → IoT (Raspberry Pi)

---

## 📋 Prerequisites

### Hardware Requirements

| Target | Minimum | Recommended |
|--------|---------|-------------|
| **GPU (NVIDIA)** | RTX 3060 12GB | **RTX 3090 24GB** |
| **RAM** | 16 GB | 32 GB |
| **Storage** | 20 GB free | 50 GB (for models) |
| **OS** | Windows 10, Ubuntu 22.04, macOS 13 | Windows 11, Ubuntu 24.04 |

**Optional:** NVIDIA DGX Spark GB10 for heavy batch processing (runs all models simultaneously).

**Mobile:** Any modern smartphone (iOS 16+ / Android 12+) for Flutter app.

### Software Requirements

Install ALL of the following before proceeding:

#### 1. Python 3.11+
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3.11 python3.11-venv python3.11-dev

# macOS (Homebrew)
brew install python@3.11

# Windows: download from python.org
# Ensure "Add to PATH" is checked during installation
```

#### 2. Node.js 22+ (LTS)
```bash
# Using nvm (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
nvm install 22
nvm use 22

# Or via package manager
# Ubuntu: sudo apt install nodejs npm
# macOS: brew install node
```

#### 3. Angular CLI
```bash
npm install -g @angular/cli@21
```

#### 4. Flutter (latest stable)
```bash
# Follow: https://docs.flutter.dev/get-started/install
# Verify:
flutter doctor
```

#### 5. NVIDIA CUDA Toolkit 12.x + cuDNN 9.x
```bash
# Ubuntu
sudo apt install nvidia-cuda-toolkit
# Or follow: https://developer.nvidia.com/cuda-downloads

# Verify:
nvidia-smi
nvcc --version
```

#### 6. FFmpeg
```bash
# Ubuntu
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows: download from ffmpeg.org, add to PATH
```

#### 7. SQLCipher (encrypted SQLite)
```bash
# Ubuntu
sudo apt install sqlcipher libsqlcipher-dev

# macOS
brew install sqlcipher

# Windows: use pre-built wheels
pip install sqlcipher3-binary
```

#### 8. Docker + Docker Compose (for ASR microservice)
```bash
# Follow: https://docs.docker.com/engine/install/
# Verify:
docker --version
docker compose version

# For GPU passthrough:
# Install nvidia-container-toolkit
# Follow: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
```

#### 9. Git LFS (for large model files)
```bash
sudo apt install git-lfs  # or brew install git-lfs
git lfs install
```

#### 10. Claude Code (AI-First development)
```bash
# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Authenticate
claude login

# Verify
claude --version
```

#### 11. HuggingFace CLI (for model downloads)
```bash
pip install huggingface-hub
huggingface-cli login
# Enter your HuggingFace token

# Accept model licenses (required for pyannote):
# Visit: https://huggingface.co/pyannote/segmentation-3.0 → Accept
# Visit: https://huggingface.co/pyannote/embedding → Accept
```

#### 12. Ollama (local LLM)
```bash
# Install: https://ollama.ai/download
curl -fsSL https://ollama.ai/install.sh | sh

# Pull model
ollama pull qwen3:8b

# Verify
ollama list
```

---

## ⚡ Quick Start (5 minutes)

### Step 1: Clone the repository
```bash
git clone --recurse-submodules https://github.com/YOUR_ORG/meetscribe.git
cd meetscribe
```

### Step 2: Set up environment variables
```bash
cp .env.example .env
# Edit .env with your settings:
```

```env
# .env file
MEETSCRIBE_DB_KEY=your_secure_passphrase_here          # SQLCipher encryption key
ANTHROPIC_API_KEY=sk-ant-...                            # Optional: Claude API
HUGGINGFACE_TOKEN=hf_...                                # For pyannote model access
OLLAMA_BASE_URL=http://localhost:11434                  # Ollama server
MEETSCRIBE_HOST=0.0.0.0
MEETSCRIBE_PORT=9876
MEETSCRIBE_DEFAULT_LANGUAGE=vi                          # vi or en or auto
MEETSCRIBE_ASR_LIVE_ENGINE=parakeet-vi                  # See CLAUDE.md §4.2
MEETSCRIBE_ASR_POST_ENGINE=vibevoice                    # VibeVoice for POST
MEETSCRIBE_LLM_PROVIDER=ollama                          # ollama or claude
MEETSCRIBE_LLM_MODEL=qwen3:8b                           # Ollama model name
```

### Step 3: Install and start the backend
```bash
# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"

# Download ASR models (first time only — may take 10-30 minutes)
python scripts/download_models.py --engine parakeet-vi
python scripts/download_models.py --engine faster-whisper --size large-v3
# Optional:
python scripts/download_models.py --engine vibevoice --quantization 4bit
python scripts/download_models.py --engine phowhisper --size large

# Start the backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 9876
```

### Step 4: Start the ASR microservice (optional Docker)
```bash
docker compose up -d whisper-asr
# Runs on port 9000 — used by mobile/IoT clients
```

### Step 5: Start the Angular frontend
```bash
cd frontend
npm install
ng serve --port 4200 --proxy-config proxy.conf.json
# Open http://localhost:4200
```

### Step 6: Open MeetScribe
Navigate to **http://localhost:4200** in your browser. You should see:
1. A consent dialog (Decree 356 compliance) — accept to proceed
2. The main interface with recording controls
3. Click the red record button to start capturing

---

## 🖥️ Electron Desktop App

```bash
cd electron
npm install

# Development mode (uses Angular dev server)
npm run dev

# Build installers
npm run build:win    # Windows .exe
npm run build:mac    # macOS .dmg
npm run build:linux  # Linux .AppImage
```

**macOS users:** System audio capture requires granting Screen Recording permission in System Preferences → Privacy & Security.

---

## 📱 Flutter Mobile App

```bash
cd mobile
flutter pub get

# Run on connected device
flutter run

# Build releases
flutter build apk --release      # Android
flutter build ios --release       # iOS (requires Xcode)
```

**On-device mode:** The Flutter app includes ONNX models (~130MB) for offline Vietnamese transcription. No server needed for basic transcription.

**Server mode:** Connect to the MeetScribe backend via WiFi/LAN for full features (diarization, VibeVoice reprocessing, LLM summarization).

---

## 🤖 IoT / Conference Room Setup

For Raspberry Pi or other Linux SBC with a USB microphone:

```bash
cd iot
pip install -r requirements.txt

# Stream audio to MeetScribe server
python audio_streamer.py \
  --server ws://YOUR_SERVER_IP:9876/ws/audio/MEETING_ID \
  --device 1 \
  --sample-rate 16000
```

---

## 🧠 AI-First Development with Claude Code

MeetScribe is designed to be built using AI-First development practices. The `CLAUDE.md` file in the project root contains all architectural rules, patterns, and constraints that Claude Code follows.

### Starting Development
```bash
# Navigate to project root
cd meetscribe

# Start Claude Code
claude

# Ask Claude to scaffold the project
> Read CLAUDE.md and scaffold Phase 1 — Backend Core

# Or be specific
> Create backend/asr/base.py following the ASREngine interface in CLAUDE.md §4.1
```

### CI/CD with Claude Code
Every Pull Request is automatically reviewed by Claude Code via GitHub Actions:
```yaml
# .github/workflows/ai-review.yml triggers on every PR
# Claude reads CLAUDE.md, reviews the diff, and comments on:
# - ASR interface compliance
# - GPU memory bounds
# - Angular Signal/RxJS patterns
# - Decree 356 consent flows
# - SQLCipher usage
```

---

## 🏗️ Architecture at a Glance

```
LIVE MODE (during meeting):
  Microphone/System Audio
    → NVIDIA Maxine (noise removal)
    → Language Detection (Whisper tiny, CPU)
    → Vietnamese: Parakeet-CTC-0.6B-Vi (~2GB VRAM)
      English: faster-whisper large-v3 (~10GB VRAM)
    → SimulStreaming AlignAtt policy (stable streaming)
    → diart (speaker diarization, 500ms updates)
    → WebSocket → Angular/Electron/Flutter clients

POST MODE (after meeting):
  Full WAV → VibeVoice-ASR 7B (4-bit, ~7GB VRAM)
    → Structured JSON: [{Start, End, Speaker, Content}]
    → LLM Summarization (Ollama Qwen3 or Claude API)
    → Structured notes: summary, decisions, action items
    → Replaces LIVE transcript in database
```

---

## 📊 Supported ASR Engines

| Engine | Language | Mode | VRAM | Use Case |
|--------|----------|------|------|----------|
| NVIDIA Parakeet-CTC-0.6B-Vi | Vietnamese + EN CS | LIVE | ~2 GB | **Primary Vietnamese** |
| faster-whisper large-v3 | 99 languages | LIVE | ~10 GB | Primary English |
| VibeVoice-ASR 7B (4-bit) | 50+ languages | POST | ~7 GB | Best unified accuracy |
| PhoWhisper-large | Vietnamese | LIVE/POST | ~10 GB | Vietnamese fallback |
| GASR/SODA | English | LIVE | CPU only | Offline, no GPU |
| Groq Whisper API | 99 languages | LIVE | Cloud | Cloud fallback |
| whisper-asr-webservice | 99 languages | POST | Docker | REST microservice |

---

## 🔒 Privacy & Compliance (Vietnam Decree 356)

MeetScribe processes biometric voice data, classified as **sensitive personal data** under Vietnam's Personal Data Protection Law (Decree 356/2025). The architecture implements:

- **Consent-first**: Microphone access blocked until explicit consent granted
- **Encryption at rest**: All data encrypted via SQLCipher (AES-256-CBC)
- **Encryption in transit**: WSS (TLS 1.3) for all WebSocket connections
- **Ephemeral audio**: Raw audio in RAM only, destroyed after transcription (unless user opts in)
- **Data purge**: Full cascade delete of meeting + transcript + voiceprints + embeddings
- **Audit logging**: Every data processing operation recorded
- **Edge computing**: Flutter on-device mode keeps biometric data on the phone

---

## 🧪 Testing

```bash
# Backend tests
pytest tests/ -v --cov=backend

# Angular tests
cd frontend && ng test --watch=false --code-coverage

# Angular E2E (Playwright)
cd frontend && npx playwright test

# Flutter tests
cd mobile && flutter test

# Load testing (WebSocket stress)
locust -f tests/load/locustfile.py --host ws://localhost:9876
```

---

## 🐳 Docker Deployment

### Development (local)
```bash
docker compose up -d
# Starts: meetscribe-backend (port 9876) + whisper-asr (port 9000)
```

### DGX Spark / Production
```bash
docker compose -f docker/docker-compose.dgx.yml up -d
# Runs all models simultaneously with 128GB unified memory
```

---

## 📁 Project Structure

```
meetscribe/
├── CLAUDE.md              # AI development instructions (Claude Code reads this)
├── README.md              # This file (human setup guide)
├── pyproject.toml         # Python project config
├── .env.example           # Environment template
├── docker-compose.yml     # Docker services
├── .github/workflows/     # CI/CD with Claude Code AI review
│
├── backend/               # Python FastAPI server
│   ├── main.py            # Entry point
│   ├── asr/               # 7 ASR engines (pluggable)
│   ├── diarization/       # diart (live) + pyannote (offline)
│   ├── llm/               # Ollama + Claude summarization
│   ├── pipeline/          # Meeting orchestrator
│   ├── compliance/        # Decree 356 (consent, purge, audit)
│   ├── storage/           # SQLCipher repository + search
│   └── api/               # REST + WebSocket endpoints
│
├── frontend/              # Angular 21 (zoneless, standalone)
├── electron/              # Electron 40 desktop app
├── mobile/                # Flutter mobile app
├── iot/                   # IoT audio streamer (Raspberry Pi)
├── engines/               # Git submodules (GASR, SimulStreaming)
├── tests/                 # pytest + Playwright + flutter_test
├── scripts/               # Model download + setup helpers
└── docs/                  # Architecture + compliance docs
```

---

## 🤝 Contributing

This project uses AI-First development:

1. Read `CLAUDE.md` before writing any code
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Write code following the patterns in `CLAUDE.md` §8 (Angular) / §9 (Flutter)
4. Push and create a PR — Claude Code will auto-review
5. Address Claude's review comments
6. Merge after CI passes

---

## 📄 License

MIT License — free for personal and commercial use.

**Note:** Some ASR models have their own licenses:
- NVIDIA Parakeet: NVIDIA Open Model License (commercial OK)
- VibeVoice-ASR: MIT (research recommended, check for updates)
- PhoWhisper: MIT
- pyannote: MIT (requires HuggingFace agreement)

---

## 🆘 Troubleshooting

### "CUDA out of memory" during LIVE mode
Reduce model size: set `MEETSCRIBE_ASR_LIVE_ENGINE=faster-whisper` with model `small` instead of `large-v3`.

### Electron shows no system audio on macOS
Ensure Screen Recording permission is granted. If still silent, the CoreAudio Tap regression may be active — the app will automatically fall back to IPC audio tap.

### Flutter on-device transcription is slow
Ensure you're using the quantized model (`whisper-small-q4.onnx`). On older phones, switch to `whisper-tiny` or use server mode.

### Vietnamese diacritics display incorrectly
Ensure all files are UTF-8. Check `MEETSCRIBE_DEFAULT_LANGUAGE=vi` in `.env`.

### SQLCipher "file is not a database" error
The `MEETSCRIBE_DB_KEY` must match the key used when the database was first created. If lost, the database cannot be recovered (by design — encryption).

---

**Built with ❤️ at TMA Solutions — Program 3**

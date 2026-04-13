"""MeetScribe application configuration via Pydantic Settings.

Reads from environment variables and .env file.
See .env.example for all available settings.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MEETSCRIBE_",
        extra="ignore",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 9876
    env: str = "development"
    log_level: str = "INFO"

    # Security (Decree 356)
    db_key: str = "CHANGE_THIS_TO_A_SECURE_PASSPHRASE"

    # ASR
    default_language: str = "vi"
    asr_live_engine: str = "parakeet-vi"
    asr_post_engine: str = "vibevoice"
    vibevoice_quantization: str = "4bit"

    # LLM
    llm_provider: str = "ollama"
    llm_model: str = "qwen3:8b"

    # Data paths
    data_dir: Path = Path("./data")
    models_dir: Path = Path("./data/models")
    recordings_dir: Path = Path("./data/recordings")

    # External services
    ollama_base_url: str = "http://localhost:11434"
    whisper_asr_host: str = "localhost"
    whisper_asr_port: int = 9000

    # API Keys (optional)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    google_gemini_api_key: str = ""
    minimax_api_key: str = ""
    minimax_group_id: str = ""
    alibaba_qwen_api_key: str = ""
    huggingface_token: str = ""

    @property
    def database_path(self) -> Path:
        return self.data_dir / "meetscribe.db"

    @property
    def whisper_asr_url(self) -> str:
        return f"http://{self.whisper_asr_host}:{self.whisper_asr_port}"

    def ensure_dirs(self):
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()

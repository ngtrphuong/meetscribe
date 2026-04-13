"""LLM summarization orchestrator.

Loads YAML templates, formats transcripts, and routes to the appropriate
LLM provider (Ollama, Claude, OpenAI, Gemini, MiniMax, Qwen Cloud).

File: backend/llm/summarizer.py
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

import structlog
import yaml

from backend.asr.base import TranscriptSegment
from backend.llm.base import LLMProvider
from backend.config import settings

logger = structlog.get_logger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


class MeetingSummarizer:
    """Orchestrates LLM summarization for a completed meeting.

    Usage:
        summarizer = MeetingSummarizer()
        summary = await summarizer.summarize(
            segments=segments,
            template_name="general_vi",
            provider_name="ollama",
            meeting_title="Họp nhóm dự án",
            started_at=datetime.datetime.now(),
            duration_seconds=3600,
        )
    """

    async def summarize(
        self,
        segments: list[TranscriptSegment],
        template_name: str = "general_vi",
        provider_name: str = "ollama",
        meeting_title: str = "Cuộc họp",
        started_at: Optional[datetime.datetime] = None,
        duration_seconds: int = 0,
        participants: Optional[list[str]] = None,
    ) -> str:
        """Generate structured meeting notes.

        Args:
            segments: Transcript segments from POST ASR engine
            template_name: Template file name (without .yaml)
            provider_name: LLM provider: "ollama", "claude", "openai", "gemini"
            meeting_title: Meeting title for template substitution
            started_at: Meeting start time
            duration_seconds: Total recording duration
            participants: List of identified speaker names

        Returns:
            Formatted meeting summary as markdown string
        """
        system_prompt = self._load_template(template_name)
        transcript_text = self._format_transcript(segments)

        # Inject meeting metadata into system prompt
        meta = self._build_metadata(
            title=meeting_title,
            started_at=started_at,
            duration_seconds=duration_seconds,
            participants=participants or self._extract_speakers(segments),
        )
        system_prompt = meta + "\n\n" + system_prompt

        provider = self._create_provider(provider_name)

        logger.info(
            "Summarizing meeting",
            template=template_name,
            provider=provider_name,
            segments=len(segments),
            transcript_chars=len(transcript_text),
        )

        summary = await provider.summarize(transcript_text, system_prompt)
        return summary

    def _load_template(self, template_name: str) -> str:
        """Load a YAML template and return the prompt string."""
        yaml_path = TEMPLATES_DIR / f"{template_name}.yaml"

        if not yaml_path.exists():
            logger.warning("Template not found, using general_vi", template=template_name)
            yaml_path = TEMPLATES_DIR / "general_vi.yaml"

        if not yaml_path.exists():
            return _FALLBACK_PROMPT_VI

        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return data.get("prompt", _FALLBACK_PROMPT_VI)

    def list_templates(self) -> list[dict]:
        """Return all available templates with their metadata."""
        templates = []
        for yaml_file in sorted(TEMPLATES_DIR.glob("*.yaml")):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                templates.append({
                    "name": yaml_file.stem,
                    "display_name": data.get("name", yaml_file.stem),
                    "language": data.get("language", "vi"),
                })
            except Exception:
                pass
        return templates

    def _format_transcript(self, segments: list[TranscriptSegment]) -> str:
        """Format segments into a readable transcript string."""
        lines = []
        for seg in segments:
            speaker = seg.speaker or "Unknown"
            start = _format_time(seg.start_time)
            lines.append(f"[{start}] {speaker}: {seg.text}")
        return "\n".join(lines)

    def _extract_speakers(self, segments: list[TranscriptSegment]) -> list[str]:
        """Extract unique speaker labels/names from segments."""
        seen: set[str] = set()
        speakers = []
        for seg in segments:
            label = seg.speaker or "Unknown"
            if label not in seen:
                seen.add(label)
                speakers.append(label)
        return speakers

    def _build_metadata(
        self,
        title: str,
        started_at: Optional[datetime.datetime],
        duration_seconds: int,
        participants: list[str],
    ) -> str:
        """Build meeting metadata header for the system prompt."""
        # Handle both datetime objects and ISO string inputs
        if started_at is None:
            date_str = "N/A"
        elif isinstance(started_at, str):
            try:
                dt = datetime.datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                date_str = dt.strftime("%d/%m/%Y %H:%M")
            except (ValueError, AttributeError):
                date_str = started_at[:16] if len(started_at) >= 16 else "N/A"
        else:
            date_str = started_at.strftime("%d/%m/%Y %H:%M")

        duration_str = _format_duration(duration_seconds)
        participants_str = ", ".join(participants) if participants else "Không xác định"

        return (
            f"THÔNG TIN CUỘC HỌP:\n"
            f"Tiêu đề: {title}\n"
            f"Ngày: {date_str}\n"
            f"Thời lượng: {duration_str}\n"
            f"Người tham gia: {participants_str}\n"
        )

    def _create_provider(self, provider_name: str) -> LLMProvider:
        """Factory: create the appropriate LLM provider."""
        if provider_name == "ollama":
            from backend.llm.ollama_provider import OllamaProvider
            return OllamaProvider(model=settings.llm_model)

        if provider_name == "claude":
            from backend.llm.claude_provider import ClaudeProvider
            return ClaudeProvider()

        if provider_name == "openai":
            from backend.llm.multi_providers import OpenAIProvider
            return OpenAIProvider(api_key=settings.openai_api_key)

        if provider_name == "gemini":
            from backend.llm.multi_providers import GeminiProvider
            return GeminiProvider(api_key=settings.google_gemini_api_key)

        if provider_name == "minimax":
            from backend.llm.multi_providers import MiniMaxProvider
            return MiniMaxProvider(
                api_key=settings.minimax_api_key,
                group_id=settings.minimax_group_id,
            )

        if provider_name == "qwen":
            from backend.llm.multi_providers import QwenCloudProvider
            return QwenCloudProvider(api_key=settings.alibaba_qwen_api_key)

        raise ValueError(f"Unknown LLM provider: {provider_name}")


def _format_time(seconds: float) -> str:
    """Format seconds as MM:SS."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def _format_duration(seconds: int) -> str:
    """Format duration as 'Xh Ym'."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


_FALLBACK_PROMPT_VI = """
Bạn là trợ lý tạo biên bản họp chuyên nghiệp.
Dựa trên bản ghi cuộc họp, hãy tạo bản tóm tắt có cấu trúc:

### Tóm tắt (2-3 câu)
### Các điểm thảo luận chính
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
""".strip()

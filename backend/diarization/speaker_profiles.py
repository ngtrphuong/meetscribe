"""Speaker profile management — name assignment and voiceprint storage.

Maps anonymous SPEAKER_XX labels to human names and optionally stores
voice embeddings (classified as biometric data under Decree 356).

Voiceprints are stored in the speaker_voiceprints table (encrypted via
SQLCipher). DELETE /api/compliance/voiceprints/{id} purges without
affecting transcripts.

File: backend/diarization/speaker_profiles.py
"""

from __future__ import annotations

import uuid
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class SpeakerProfileManager:
    """Maps speaker labels ↔ names and manages voiceprint embeddings."""

    def __init__(self):
        # In-memory map for active session: label → name
        self._label_to_name: dict[str, str] = {}
        self._name_to_label: dict[str, str] = {}

    def assign_name(self, speaker_label: str, name: str) -> None:
        """Manually assign a human name to a SPEAKER_XX label."""
        self._label_to_name[speaker_label] = name
        self._name_to_label[name] = speaker_label
        logger.debug("Speaker name assigned", label=speaker_label, name=name)

    def get_name(self, speaker_label: str) -> Optional[str]:
        """Look up human name for a speaker label."""
        return self._label_to_name.get(speaker_label)

    def get_label(self, name: str) -> Optional[str]:
        """Look up label for a human name."""
        return self._name_to_label.get(name)

    async def save_voiceprint(
        self,
        speaker_name: str,
        embedding: bytes,
        meeting_id: str,
    ) -> str:
        """Save a voice embedding to the database (Decree 356 — requires consent).

        Args:
            speaker_name: Human name of the speaker
            embedding: Serialised numpy float32 array (sentence-transformer output)
            meeting_id: Source meeting (for audit log)

        Returns:
            voiceprint_id (UUID)
        """
        voiceprint_id = str(uuid.uuid4())

        from backend.database import get_db, audit
        async with get_db() as db:
            await db.execute(
                """INSERT INTO speaker_voiceprints (id, speaker_name, voice_embedding)
                   VALUES (?, ?, ?)""",
                (voiceprint_id, speaker_name, embedding),
            )
            await db.commit()

        await audit("CREATE", "voiceprint", voiceprint_id, f"speaker={speaker_name}")
        logger.info("Voiceprint saved", speaker=speaker_name, id=voiceprint_id)
        return voiceprint_id

    async def load_voiceprints(self) -> list[dict]:
        """Load all voiceprints from database for speaker identification."""
        from backend.database import get_db
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id, speaker_name, voice_embedding FROM speaker_voiceprints"
            )
            rows = await cursor.fetchall()
        return [
            {"id": row["id"], "name": row["speaker_name"], "embedding": row["voice_embedding"]}
            for row in rows
        ]

    async def delete_voiceprint(self, voiceprint_id: str) -> bool:
        """Delete a voiceprint (Decree 356 data subject right)."""
        from backend.database import get_db, audit
        async with get_db() as db:
            cursor = await db.execute(
                "DELETE FROM speaker_voiceprints WHERE id = ?", (voiceprint_id,)
            )
            await db.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            await audit("DELETE", "voiceprint", voiceprint_id)
            logger.info("Voiceprint deleted", id=voiceprint_id)
        return deleted

    def identify_speaker(
        self,
        embedding: "np.ndarray",
        known_voiceprints: list[dict],
        threshold: float = 0.75,
    ) -> Optional[str]:
        """Identify a speaker from their embedding against stored voiceprints.

        Returns speaker name if cosine similarity > threshold, else None.
        """
        if not known_voiceprints:
            return None

        try:
            import numpy as np

            query = embedding / (np.linalg.norm(embedding) + 1e-8)
            best_name = None
            best_score = -1.0

            for vp in known_voiceprints:
                stored = np.frombuffer(vp["embedding"], dtype=np.float32)
                stored = stored / (np.linalg.norm(stored) + 1e-8)
                score = float(np.dot(query, stored))
                if score > best_score:
                    best_score = score
                    best_name = vp["name"]

            if best_score >= threshold:
                return best_name
            return None

        except Exception as exc:
            logger.debug("Speaker identification error", error=str(exc))
            return None

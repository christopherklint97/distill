"""Abstract base class for transcription backends."""

from abc import ABC, abstractmethod
from pathlib import Path

from distill.models import TranscriptSegment


class Transcriber(ABC):
    """Base class for audio-to-text transcription backends."""

    @abstractmethod
    def transcribe(
        self, audio_path: Path, language: str = "en"
    ) -> tuple[str, list[TranscriptSegment]]:
        """Transcribe an audio file.

        Args:
            audio_path: Path to the audio file.
            language: Language code or "auto" for auto-detection.

        Returns:
            Tuple of (full_text, segments).
        """
        ...

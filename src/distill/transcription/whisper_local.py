"""Local Whisper model transcription backend."""

import logging
from pathlib import Path

from distill.models import TranscriptSegment
from distill.transcription.base import Transcriber

logger = logging.getLogger(__name__)


class WhisperLocalTranscriber(Transcriber):
    """Transcription using a locally-loaded Whisper model."""

    def __init__(self, model_name: str = "base") -> None:
        self._model_name = model_name
        self._model: object | None = None

    def _load_model(self) -> object:
        """Lazy-load the Whisper model."""
        if self._model is None:
            try:
                import whisper
            except ImportError:
                msg = (
                    "openai-whisper is not installed. "
                    "Install it with: uv add openai-whisper"
                )
                raise ImportError(msg)  # noqa: B904

            logger.info("Loading Whisper model: %s", self._model_name)
            self._model = whisper.load_model(self._model_name)
        return self._model

    def transcribe(
        self, audio_path: Path, language: str = "en"
    ) -> tuple[str, list[TranscriptSegment]]:
        """Transcribe audio using local Whisper model."""
        model = self._load_model()

        options: dict[str, object] = {}
        if language != "auto":
            options["language"] = language

        result: dict[str, object] = model.transcribe(  # type: ignore[attr-defined]
            str(audio_path), **options
        )

        segments: list[TranscriptSegment] = []
        raw_segments: list[dict[str, object]] = result.get(  # type: ignore[assignment]
            "segments", []
        )
        for seg in raw_segments:
            segments.append(
                TranscriptSegment(
                    start=seg["start"],  # type: ignore[arg-type]
                    end=seg["end"],  # type: ignore[arg-type]
                    text=str(seg["text"]).strip(),
                )
            )

        full_text = str(result.get("text", "")).strip()
        logger.info(
            "Transcribed %s: %d segments, %d characters",
            audio_path.name,
            len(segments),
            len(full_text),
        )
        return full_text, segments

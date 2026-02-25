"""OpenAI Whisper API transcription backend."""

import logging
import os
import time
from pathlib import Path

import httpx

from distill.models import TranscriptSegment
from distill.transcription.base import Transcriber

logger = logging.getLogger(__name__)

_API_URL = "https://api.openai.com/v1/audio/transcriptions"
_MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB API limit
_MAX_RETRIES = 3
_RETRY_DELAY = 2.0


class WhisperAPITranscriber(Transcriber):
    """Transcription using the OpenAI Whisper API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self._api_key:
            msg = "OPENAI_API_KEY is required for Whisper API backend"
            raise ValueError(msg)

    def transcribe(
        self, audio_path: Path, language: str = "en"
    ) -> tuple[str, list[TranscriptSegment]]:
        """Transcribe audio using the OpenAI Whisper API.

        Handles files >25MB by chunking.
        """
        file_size = audio_path.stat().st_size
        if file_size > _MAX_FILE_SIZE:
            return self._transcribe_chunked(audio_path, language)
        return self._transcribe_single(audio_path, language)

    def _transcribe_single(
        self, audio_path: Path, language: str
    ) -> tuple[str, list[TranscriptSegment]]:
        """Transcribe a single audio file via the API."""
        headers = {"Authorization": f"Bearer {self._api_key}"}

        data: dict[str, str] = {
            "model": "whisper-1",
            "response_format": "verbose_json",
        }
        if language != "auto":
            data["language"] = language

        for attempt in range(_MAX_RETRIES):
            try:
                with open(audio_path, "rb") as f:
                    files = {"file": (audio_path.name, f, "audio/mpeg")}
                    with httpx.Client(timeout=600) as client:
                        response = client.post(
                            _API_URL,
                            headers=headers,
                            data=data,
                            files=files,
                        )
                        response.raise_for_status()

                result = response.json()
                segments = self._parse_segments(result)
                full_text = result.get("text", "").strip()
                return full_text, segments

            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                if attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_DELAY * (2**attempt)
                    logger.warning(
                        "API request failed (attempt %d/%d): %s. Retrying in %.1fs",
                        attempt + 1,
                        _MAX_RETRIES,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    raise

        msg = "Unexpected: exhausted retries without result or exception"
        raise RuntimeError(msg)

    def _transcribe_chunked(
        self, audio_path: Path, language: str
    ) -> tuple[str, list[TranscriptSegment]]:
        """Transcribe a large file by splitting into chunks.

        Uses ffmpeg to split audio into 24MB segments.
        """
        import subprocess
        import tempfile

        chunk_dir = Path(tempfile.mkdtemp(prefix="distill_chunks_"))

        # Split into ~10-minute chunks
        subprocess.run(  # noqa: S603
            [
                "ffmpeg",
                "-i",
                str(audio_path),
                "-f",
                "segment",
                "-segment_time",
                "600",
                "-c",
                "copy",
                str(chunk_dir / "chunk_%03d.mp3"),
            ],
            check=True,
            capture_output=True,
        )

        all_text: list[str] = []
        all_segments: list[TranscriptSegment] = []
        time_offset = 0.0

        for chunk_path in sorted(chunk_dir.glob("chunk_*.mp3")):
            text, segments = self._transcribe_single(chunk_path, language)
            all_text.append(text)

            for seg in segments:
                all_segments.append(
                    TranscriptSegment(
                        start=seg.start + time_offset,
                        end=seg.end + time_offset,
                        text=seg.text,
                        speaker=seg.speaker,
                    )
                )

            if segments:
                time_offset = all_segments[-1].end

        return " ".join(all_text), all_segments

    @staticmethod
    def _parse_segments(
        result: dict[str, object],
    ) -> list[TranscriptSegment]:
        """Parse segments from the Whisper API verbose JSON response."""
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
        return segments

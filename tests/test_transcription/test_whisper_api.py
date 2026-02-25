"""Tests for Whisper API transcription backend."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distill.transcription.whisper_api import WhisperAPITranscriber


class TestWhisperAPITranscriber:
    def test_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            WhisperAPITranscriber(api_key="")

    def test_init_with_api_key(self) -> None:
        t = WhisperAPITranscriber(api_key="test-key")
        assert t._api_key == "test-key"

    @patch("distill.transcription.whisper_api.httpx.Client")
    def test_transcribe_single(
        self, mock_client_cls: MagicMock, tmp_path: Path
    ) -> None:
        # Create a dummy audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "text": "Hello world. This is a test.",
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "Hello world."},
                {"start": 2.5, "end": 5.0, "text": "This is a test."},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        transcriber = WhisperAPITranscriber(api_key="test-key")
        text, segments = transcriber.transcribe(audio_file)

        assert text == "Hello world. This is a test."
        assert len(segments) == 2
        assert segments[0].text == "Hello world."
        assert segments[1].start == 2.5

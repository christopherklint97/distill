"""Tests for YouTube source extraction."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from distill.sources.youtube import extract_video_id, fetch_transcript


@dataclass
class _FakeSnippet:
    text: str
    start: float
    duration: float


class TestExtractVideoId:
    def test_standard_watch_url(self) -> None:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_watch_url_with_extra_params(self) -> None:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_short_url(self) -> None:
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_embed_url(self) -> None:
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_shorts_url(self) -> None:
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_invalid_url(self) -> None:
        assert extract_video_id("https://example.com") is None

    def test_empty_string(self) -> None:
        assert extract_video_id("") is None

    def test_no_protocol(self) -> None:
        url = "youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"


class TestFetchTranscript:
    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_fetch_transcript_success(self, mock_api_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_api_cls.return_value = mock_instance
        mock_instance.fetch.return_value = [
            _FakeSnippet(start=0.0, duration=3.0, text="Hello world"),
            _FakeSnippet(start=3.0, duration=4.0, text="This is a test"),
        ]
        transcript = fetch_transcript(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        assert transcript.method == "captions"
        assert len(transcript.segments) == 2
        assert "Hello world" in transcript.text
        assert "This is a test" in transcript.text

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not extract video ID"):
            fetch_transcript("https://example.com/not-youtube")

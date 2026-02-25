"""Tests for Pydantic data models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from distill.models import (
    Article,
    ArticleSection,
    ContentSource,
    Transcript,
    TranscriptSegment,
)


class TestContentSource:
    def test_youtube_source(self) -> None:
        source = ContentSource(
            url="https://www.youtube.com/watch?v=abc123",
            title="Test Video",
            source_type="youtube",
            duration_seconds=300,
        )
        assert source.source_type == "youtube"
        assert source.feed_url is None

    def test_podcast_source(self) -> None:
        source = ContentSource(
            url="https://example.com/episode.mp3",
            title="Test Episode",
            source_type="podcast",
            feed_url="https://example.com/feed.xml",
            published_at=datetime(2024, 1, 15),
        )
        assert source.source_type == "podcast"
        assert source.feed_url is not None

    def test_invalid_source_type(self) -> None:
        with pytest.raises(ValidationError):
            ContentSource(
                url="https://example.com",
                title="Test",
                source_type="invalid",  # type: ignore[arg-type]
            )


class TestTranscriptSegment:
    def test_segment_creation(self) -> None:
        seg = TranscriptSegment(
            start=0.0, end=5.0, text="Hello world", speaker="Alice"
        )
        assert seg.start == 0.0
        assert seg.speaker == "Alice"

    def test_segment_no_speaker(self) -> None:
        seg = TranscriptSegment(start=0.0, end=5.0, text="Hello")
        assert seg.speaker is None


class TestTranscript:
    def test_transcript_creation(self) -> None:
        t = Transcript(
            content_id="abc123",
            text="Hello world",
            segments=[
                TranscriptSegment(start=0.0, end=5.0, text="Hello world")
            ],
            language="en",
            method="captions",
        )
        assert t.method == "captions"
        assert len(t.segments) == 1

    def test_invalid_method(self) -> None:
        with pytest.raises(ValidationError):
            Transcript(
                content_id="abc",
                text="test",
                segments=[],
                language="en",
                method="invalid",  # type: ignore[arg-type]
            )


class TestArticle:
    def test_article_creation(self) -> None:
        article = Article(
            content_id="abc123",
            title="Test Article",
            subtitle="A subtitle",
            sections=[ArticleSection(heading="Intro", body="Some text")],
            summary="A summary",
            style="detailed",
            source=ContentSource(
                url="https://example.com",
                title="Source",
                source_type="youtube",
            ),
        )
        assert article.style == "detailed"
        assert len(article.sections) == 1

    def test_article_serialization(self) -> None:
        article = Article(
            content_id="abc123",
            title="Test",
            sections=[ArticleSection(heading="H1", body="Body")],
            summary="Summary",
            style="concise",
            source=ContentSource(
                url="https://example.com",
                title="Source",
                source_type="youtube",
            ),
        )
        json_str = article.model_dump_json()
        restored = Article.model_validate_json(json_str)
        assert restored.title == article.title
        assert restored.sections[0].heading == "H1"

    def test_invalid_style(self) -> None:
        with pytest.raises(ValidationError):
            Article(
                content_id="abc",
                title="Test",
                sections=[],
                summary="Summary",
                style="invalid",  # type: ignore[arg-type]
                source=ContentSource(
                    url="https://example.com",
                    title="Source",
                    source_type="youtube",
                ),
            )

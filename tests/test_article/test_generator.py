"""Tests for article generation."""

import json
from unittest.mock import MagicMock, patch

from distill.article.generator import (
    _parse_article_json,
    _split_into_chunks,
    generate_article,
)
from distill.config import ClaudeConfig
from distill.models import ContentSource


def _make_source() -> ContentSource:
    return ContentSource(
        url="https://www.youtube.com/watch?v=test",
        title="Test Video",
        source_type="youtube",
    )


def _make_article_json() -> str:
    return json.dumps(
        {
            "title": "Generated Title",
            "subtitle": "A subtitle",
            "summary": "This is a summary",
            "sections": [
                {"heading": "Introduction", "body": "Intro text here."},
                {"heading": "Main Points", "body": "Key takeaways."},
            ],
        }
    )


class TestParseArticleJson:
    def test_parse_valid_json(self) -> None:
        raw = _make_article_json()
        article = _parse_article_json(raw, "abc123", "detailed", _make_source())
        assert article.title == "Generated Title"
        assert article.subtitle == "A subtitle"
        assert len(article.sections) == 2
        assert article.summary == "This is a summary"

    def test_parse_json_in_code_block(self) -> None:
        raw = f"```json\n{_make_article_json()}\n```"
        article = _parse_article_json(raw, "abc123", "detailed", _make_source())
        assert article.title == "Generated Title"

    def test_parse_preserves_metadata(self) -> None:
        raw = _make_article_json()
        article = _parse_article_json(raw, "content_abc", "concise", _make_source())
        assert article.content_id == "content_abc"
        assert article.style == "concise"


class TestSplitIntoChunks:
    def test_short_text_single_chunk(self) -> None:
        chunks = _split_into_chunks("Short text")
        assert len(chunks) == 1

    def test_long_text_multiple_chunks(self) -> None:
        text = "A" * 500_000
        chunks = _split_into_chunks(text)
        assert len(chunks) > 1

    def test_chunks_cover_all_text(self) -> None:
        # Each chunk overlaps, so joined set of chars covers full text
        text = "Hello " * 50_000  # ~300k chars
        chunks = _split_into_chunks(text)
        assert len(chunks) >= 2


class TestGenerateArticle:
    @patch("distill.article.generator._call_claude")
    def test_single_pass_generation(self, mock_call: MagicMock) -> None:
        mock_call.return_value = _make_article_json()
        source = _make_source()
        client = MagicMock()
        article = generate_article(
            "Short transcript text",
            "abc123",
            source,
            style="detailed",
            config=ClaudeConfig(),
            client=client,
        )
        assert article.title == "Generated Title"
        assert mock_call.call_count == 1

    @patch("distill.article.generator._call_claude")
    def test_chunked_generation(self, mock_call: MagicMock) -> None:
        # First calls return chunk summaries, last call returns article JSON
        mock_call.side_effect = [
            "Summary of chunk 1",
            "Summary of chunk 2",
            _make_article_json(),
        ]
        source = _make_source()
        client = MagicMock()
        long_text = "A" * 300_000
        article = generate_article(
            long_text,
            "abc123",
            source,
            style="concise",
            config=ClaudeConfig(),
            client=client,
        )
        assert article.title == "Generated Title"
        assert mock_call.call_count >= 3  # at least 2 chunks + 1 synthesis

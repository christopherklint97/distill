"""Tests for prompt templates."""

from datetime import datetime

from distill.article.prompts import (
    build_chunk_prompt,
    build_generation_prompt,
    build_synthesis_prompt,
)
from distill.models import ContentSource


def _make_source() -> ContentSource:
    return ContentSource(
        url="https://www.youtube.com/watch?v=test",
        title="Test Video Title",
        source_type="youtube",
        published_at=datetime(2024, 3, 15),
    )


class TestBuildGenerationPrompt:
    def test_contains_transcript(self) -> None:
        system, user = build_generation_prompt(
            "This is the transcript text", _make_source(), "detailed"
        )
        assert "This is the transcript text" in user

    def test_contains_source_info(self) -> None:
        _, user = build_generation_prompt("text", _make_source(), "detailed")
        assert "Test Video Title" in user
        assert "2024-03-15" in user

    def test_system_prompt_present(self) -> None:
        system, _ = build_generation_prompt("text", _make_source(), "detailed")
        assert "expert writer" in system

    def test_json_format_in_prompt(self) -> None:
        _, user = build_generation_prompt("text", _make_source(), "detailed")
        assert "JSON" in user
        assert "sections" in user

    def test_different_styles(self) -> None:
        for style in ("detailed", "concise", "summary", "bullets"):
            _, user = build_generation_prompt("text", _make_source(), style)
            assert len(user) > 0


class TestBuildChunkPrompt:
    def test_contains_chunk_info(self) -> None:
        prompt = build_chunk_prompt("chunk text here", 2, 5)
        assert "part 2 of 5" in prompt
        assert "chunk text here" in prompt


class TestBuildSynthesisPrompt:
    def test_contains_summaries(self) -> None:
        summaries = ["Summary of part 1", "Summary of part 2"]
        system, user = build_synthesis_prompt(
            summaries, _make_source(), "concise"
        )
        assert "Summary of part 1" in user
        assert "Summary of part 2" in user
        assert "Test Video Title" in user

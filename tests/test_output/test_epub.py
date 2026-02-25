"""Tests for EPUB output rendering."""

from pathlib import Path

from distill.models import Article, ArticleSection, ContentSource
from distill.output.epub import render


def _make_article() -> Article:
    return Article(
        content_id="abc123",
        title="Test Article",
        sections=[
            ArticleSection(heading="Intro", body="Hello world."),
        ],
        summary="A summary.",
        style="detailed",
        source=ContentSource(
            url="https://example.com",
            title="Source",
            source_type="youtube",
        ),
    )


class TestEpubRender:
    def test_creates_epub_file(self, tmp_path: Path) -> None:
        output = tmp_path / "test.epub"
        result = render(_make_article(), str(output))
        assert Path(result).exists()
        assert Path(result).stat().st_size > 0

    def test_returns_output_path(self, tmp_path: Path) -> None:
        output = tmp_path / "test.epub"
        result = render(_make_article(), str(output))
        assert result == str(output)

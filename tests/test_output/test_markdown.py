"""Tests for Markdown output rendering."""

from datetime import datetime

from distill.models import Article, ArticleSection, ContentSource
from distill.output.markdown import render


def _make_article() -> Article:
    return Article(
        content_id="abc123",
        title="Test Article Title",
        subtitle="A Subtitle",
        sections=[
            ArticleSection(heading="Introduction", body="This is the intro."),
            ArticleSection(heading="Key Points", body="Here are the points."),
        ],
        summary="This is the TLDR summary.",
        style="detailed",
        source=ContentSource(
            url="https://www.youtube.com/watch?v=test",
            title="Source Video",
            source_type="youtube",
            published_at=datetime(2024, 3, 15),
        ),
    )


class TestMarkdownRender:
    def test_contains_title(self) -> None:
        result = render(_make_article())
        assert "# Test Article Title" in result

    def test_contains_subtitle(self) -> None:
        result = render(_make_article())
        assert "*A Subtitle*" in result

    def test_contains_summary(self) -> None:
        result = render(_make_article())
        assert "TLDR" in result
        assert "This is the TLDR summary." in result

    def test_contains_sections(self) -> None:
        result = render(_make_article())
        assert "## Introduction" in result
        assert "This is the intro." in result
        assert "## Key Points" in result

    def test_contains_source_link(self) -> None:
        result = render(_make_article())
        assert "[Source Video]" in result
        assert "youtube.com" in result

    def test_no_subtitle(self) -> None:
        article = _make_article()
        article.subtitle = None
        result = render(article)
        assert "# Test Article Title" in result

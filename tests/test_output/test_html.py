"""Tests for HTML output rendering."""

from distill.models import Article, ArticleSection, ContentSource
from distill.output.html import render


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


class TestHtmlRender:
    def test_contains_html_structure(self) -> None:
        result = render(_make_article())
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "</html>" in result

    def test_contains_title_tag(self) -> None:
        result = render(_make_article())
        assert "<title>Test Article</title>" in result

    def test_contains_content(self) -> None:
        result = render(_make_article())
        assert "Hello world." in result

    def test_contains_css(self) -> None:
        result = render(_make_article())
        assert "<style>" in result

"""Tests for the database layer."""

from datetime import datetime

from distill.db import Database, content_id_for_url
from distill.models import (
    Article,
    ArticleSection,
    ContentSource,
    Transcript,
    TranscriptSegment,
)


def _make_source(url: str = "https://youtube.com/watch?v=test") -> ContentSource:
    return ContentSource(
        url=url,
        title="Test Video",
        source_type="youtube",
        duration_seconds=600,
        published_at=datetime(2024, 1, 1),
    )


def _make_transcript(content_id: str) -> Transcript:
    return Transcript(
        content_id=content_id,
        text="Hello world. This is a test transcript.",
        segments=[
            TranscriptSegment(start=0.0, end=3.0, text="Hello world."),
            TranscriptSegment(start=3.0, end=6.0, text="This is a test transcript."),
        ],
        language="en",
        method="captions",
    )


def _make_article(content_id: str, source: ContentSource) -> Article:
    return Article(
        content_id=content_id,
        title="Test Article",
        subtitle="A test subtitle",
        sections=[
            ArticleSection(heading="Introduction", body="Some intro text."),
            ArticleSection(heading="Main Points", body="Key takeaways."),
        ],
        summary="This is a test summary.",
        style="detailed",
        source=source,
    )


class TestContentId:
    def test_deterministic(self) -> None:
        url = "https://youtube.com/watch?v=test"
        assert content_id_for_url(url) == content_id_for_url(url)

    def test_different_urls(self) -> None:
        assert content_id_for_url("url1") != content_id_for_url("url2")


class TestSources:
    def test_save_and_get(self, tmp_db: Database) -> None:
        source = _make_source()
        cid = tmp_db.save_source(source)
        retrieved = tmp_db.get_source(cid)
        assert retrieved is not None
        assert retrieved.title == "Test Video"
        assert retrieved.source_type == "youtube"

    def test_get_nonexistent(self, tmp_db: Database) -> None:
        assert tmp_db.get_source("nonexistent") is None

    def test_upsert(self, tmp_db: Database) -> None:
        source = _make_source()
        cid1 = tmp_db.save_source(source)
        source.title = "Updated Title"
        cid2 = tmp_db.save_source(source)
        assert cid1 == cid2
        retrieved = tmp_db.get_source(cid1)
        assert retrieved is not None
        assert retrieved.title == "Updated Title"


class TestTranscripts:
    def test_save_and_get(self, tmp_db: Database) -> None:
        source = _make_source()
        cid = tmp_db.save_source(source)
        transcript = _make_transcript(cid)
        tmp_db.save_transcript(transcript)
        retrieved = tmp_db.get_transcript(cid)
        assert retrieved is not None
        assert len(retrieved.segments) == 2
        assert retrieved.text == "Hello world. This is a test transcript."
        assert retrieved.method == "captions"

    def test_get_nonexistent(self, tmp_db: Database) -> None:
        assert tmp_db.get_transcript("nonexistent") is None


class TestArticles:
    def test_save_and_get(self, tmp_db: Database) -> None:
        source = _make_source()
        cid = tmp_db.save_source(source)
        article = _make_article(cid, source)
        article_id = tmp_db.save_article(article, output_path="/tmp/test.md")
        retrieved = tmp_db.get_article(article_id)
        assert retrieved is not None
        assert retrieved.title == "Test Article"
        assert len(retrieved.sections) == 2

    def test_list_for_content(self, tmp_db: Database) -> None:
        source = _make_source()
        cid = tmp_db.save_source(source)
        for style in ("detailed", "concise"):
            article = _make_article(cid, source)
            article.style = style  # type: ignore[assignment]
            tmp_db.save_article(article)
        articles = tmp_db.get_articles_for_content(cid)
        assert len(articles) == 2

    def test_history(self, tmp_db: Database) -> None:
        source = _make_source()
        cid = tmp_db.save_source(source)
        article = _make_article(cid, source)
        tmp_db.save_article(article, output_format="markdown")
        history = tmp_db.list_history()
        assert len(history) == 1
        assert history[0]["title"] == "Test Article"


class TestSubscriptions:
    def test_save_and_list(self, tmp_db: Database) -> None:
        tmp_db.save_subscription(
            "https://example.com/feed.xml", title="My Podcast", auto_process=True
        )
        subs = tmp_db.get_subscriptions()
        assert len(subs) == 1
        assert subs[0]["title"] == "My Podcast"
        assert subs[0]["auto_process"] == 1

    def test_update_checked(self, tmp_db: Database) -> None:
        tmp_db.save_subscription("https://example.com/feed.xml")
        tmp_db.update_subscription_checked(
            "https://example.com/feed.xml", "2024-01-15"
        )
        subs = tmp_db.get_subscriptions()
        assert subs[0]["last_checked"] is not None
        assert subs[0]["last_episode_date"] == "2024-01-15"

    def test_delete(self, tmp_db: Database) -> None:
        tmp_db.save_subscription("https://example.com/feed.xml")
        tmp_db.delete_subscription("https://example.com/feed.xml")
        assert len(tmp_db.get_subscriptions()) == 0

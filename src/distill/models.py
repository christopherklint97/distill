"""Data models for Distill."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ContentSource(BaseModel):
    """Metadata about a video or podcast episode."""

    url: str
    title: str
    source_type: Literal["youtube", "podcast"]
    duration_seconds: int | None = None
    published_at: datetime | None = None
    feed_url: str | None = None


class TranscriptSegment(BaseModel):
    """A single segment of a transcript with timing info."""

    start: float
    end: float
    text: str
    speaker: str | None = None


class Transcript(BaseModel):
    """Full transcript of a video or podcast episode."""

    content_id: str
    text: str
    segments: list[TranscriptSegment]
    language: str
    method: Literal["captions", "whisper_local", "whisper_api"]


class ArticleSection(BaseModel):
    """A section within a generated article."""

    heading: str
    body: str


class Article(BaseModel):
    """A generated article derived from a transcript."""

    content_id: str
    title: str
    subtitle: str | None = None
    sections: list[ArticleSection]
    summary: str
    style: Literal["detailed", "concise", "summary", "bullets"]
    source: ContentSource

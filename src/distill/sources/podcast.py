"""Podcast feed parsing and episode extraction."""

import contextlib
import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import feedparser
import httpx

from distill.models import ContentSource

logger = logging.getLogger(__name__)


@dataclass
class PodcastEpisode:
    """A single podcast episode parsed from an RSS feed."""

    title: str
    audio_url: str
    published_at: datetime | None
    duration_seconds: int | None
    description: str


@dataclass
class PodcastFeed:
    """Parsed podcast feed with metadata and episodes."""

    title: str
    feed_url: str
    description: str
    episodes: list[PodcastEpisode]


def parse_feed(feed_url: str) -> PodcastFeed:
    """Parse a podcast RSS/Atom feed and extract episodes."""
    feed = feedparser.parse(feed_url)

    if feed.bozo and not feed.entries:
        msg = f"Failed to parse feed: {feed_url}"
        raise ValueError(msg)

    episodes: list[PodcastEpisode] = []
    for entry in feed.entries:
        audio_url = _extract_audio_url(entry)
        if not audio_url:
            continue

        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            with contextlib.suppress(TypeError, ValueError):
                published = datetime(*entry.published_parsed[:6])

        duration = _parse_duration(entry)

        episodes.append(
            PodcastEpisode(
                title=entry.get("title", "Untitled Episode"),
                audio_url=audio_url,
                published_at=published,
                duration_seconds=duration,
                description=entry.get("summary", ""),
            )
        )

    return PodcastFeed(
        title=feed.feed.get("title", "Unknown Podcast"),
        feed_url=feed_url,
        description=feed.feed.get("description", ""),
        episodes=episodes,
    )


def _extract_audio_url(entry: Any) -> str | None:
    """Extract audio URL from feed entry enclosures or links."""
    for enclosure in entry.get("enclosures", []):
        if enclosure.get("type", "").startswith("audio/"):
            return str(enclosure["href"])

    for link in entry.get("links", []):
        if link.get("type", "").startswith("audio/"):
            return str(link["href"])

    return None


def _parse_duration(entry: Any) -> int | None:
    """Parse episode duration from iTunes or Podcast 2.0 namespace."""
    duration_str = (
        getattr(entry, "itunes_duration", "")
        or entry.get("itunes_duration", "")
    )
    if not duration_str:
        return None

    try:
        if ":" in str(duration_str):
            parts = str(duration_str).split(":")
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + int(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + int(s)
        return int(duration_str)
    except (ValueError, TypeError):
        return None


def episode_to_source(
    episode: PodcastEpisode, feed_url: str
) -> ContentSource:
    """Convert a PodcastEpisode to a ContentSource model."""
    return ContentSource(
        url=episode.audio_url,
        title=episode.title,
        source_type="podcast",
        duration_seconds=episode.duration_seconds,
        published_at=episode.published_at,
        feed_url=feed_url,
    )


def download_episode(audio_url: str, output_dir: Path | None = None) -> Path:
    """Download a podcast episode audio file.

    Returns the path to the downloaded file.
    """
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="distill_"))

    output_dir.mkdir(parents=True, exist_ok=True)

    # Derive filename from URL
    url_path = audio_url.split("?")[0]
    filename = url_path.split("/")[-1] or "episode.mp3"
    output_path = output_dir / filename

    logger.info("Downloading episode from %s", audio_url)
    with (
        httpx.Client(follow_redirects=True, timeout=300) as client,
        client.stream("GET", audio_url) as response,
    ):
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)

    logger.info("Downloaded to %s", output_path)
    return output_path

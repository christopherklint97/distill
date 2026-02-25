"""Tests for podcast feed parsing."""

from unittest.mock import MagicMock, patch

from distill.sources.podcast import (
    PodcastEpisode,
    _parse_duration,
    episode_to_source,
    parse_feed,
)


def _mock_entry(
    title: str = "Test Episode",
    audio_url: str = "https://example.com/ep.mp3",
    duration: str = "01:30:00",
) -> MagicMock:
    """Create a mock feed entry."""
    entry = MagicMock()
    entry.get.side_effect = lambda k, d=None: {
        "title": title,
        "summary": "A test episode",
    }.get(k, d)
    entry.__getitem__ = entry.get
    entry.__contains__ = lambda self, k: k in {"title", "summary"}
    entry.enclosures = [{"type": "audio/mpeg", "href": audio_url}]
    entry.links = []
    entry.published_parsed = (2024, 1, 15, 12, 0, 0, 0, 0, 0)
    entry.itunes_duration = duration
    # Make hasattr work for published_parsed
    type(entry).published_parsed = property(
        lambda self: (2024, 1, 15, 12, 0, 0, 0, 0, 0)
    )
    return entry


class TestParseDuration:
    def _entry_with_duration(self, val: str) -> MagicMock:
        entry = MagicMock(spec=[])
        entry.itunes_duration = val
        entry.get = lambda k, d="": val if k == "itunes_duration" else d
        return entry

    def test_hms_format(self) -> None:
        assert _parse_duration(self._entry_with_duration("01:30:00")) == 5400

    def test_ms_format(self) -> None:
        assert _parse_duration(self._entry_with_duration("45:30")) == 2730

    def test_seconds_only(self) -> None:
        assert _parse_duration(self._entry_with_duration("3600")) == 3600

    def test_no_duration(self) -> None:
        entry = MagicMock(spec=[])
        entry.itunes_duration = ""
        entry.get = lambda k, d="": ""
        assert _parse_duration(entry) is None


class TestParseFeed:
    @patch("distill.sources.podcast.feedparser.parse")
    def test_parse_valid_feed(self, mock_parse: MagicMock) -> None:
        entry_data = {
            "title": "Episode 1",
            "summary": "Description",
            "enclosures": [{"type": "audio/mpeg", "href": "https://example.com/ep1.mp3"}],
            "links": [],
        }
        entry = MagicMock(spec=[])
        entry.get = lambda k, d=None: entry_data.get(k, d)
        entry.enclosures = entry_data["enclosures"]
        entry.links = []
        entry.published_parsed = (2024, 1, 15, 12, 0, 0, 0, 0, 0)
        entry.itunes_duration = "30:00"

        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[entry],
            feed={"title": "Test Podcast", "description": "A test feed"},
        )

        feed = parse_feed("https://example.com/feed.xml")
        assert feed.title == "Test Podcast"
        assert len(feed.episodes) == 1
        assert feed.episodes[0].title == "Episode 1"
        assert feed.episodes[0].duration_seconds == 1800

    @patch("distill.sources.podcast.feedparser.parse")
    def test_empty_feed(self, mock_parse: MagicMock) -> None:
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[],
            feed={"title": "Empty", "description": ""},
        )
        feed = parse_feed("https://example.com/empty.xml")
        assert len(feed.episodes) == 0


class TestEpisodeToSource:
    def test_conversion(self) -> None:
        episode = PodcastEpisode(
            title="My Episode",
            audio_url="https://example.com/ep.mp3",
            published_at=None,
            duration_seconds=1800,
            description="About this episode",
        )
        source = episode_to_source(episode, "https://example.com/feed.xml")
        assert source.source_type == "podcast"
        assert source.title == "My Episode"
        assert source.feed_url == "https://example.com/feed.xml"

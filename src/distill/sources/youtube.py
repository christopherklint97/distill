"""YouTube video extraction: URL parsing, metadata, and transcript fetching."""

import logging
import re
import subprocess
import tempfile
from pathlib import Path

from distill.models import ContentSource, Transcript, TranscriptSegment

logger = logging.getLogger(__name__)

_VIDEO_ID_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?.*v=|youtu\.be/)([a-zA-Z0-9_-]{11})"),
    re.compile(r"youtube\.com/embed/([a-zA-Z0-9_-]{11})"),
    re.compile(r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})"),
]


def extract_video_id(url: str) -> str | None:
    """Extract the video ID from a YouTube URL.

    Supports watch, short, embed, and youtu.be URLs.
    """
    for pattern in _VIDEO_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def fetch_metadata(url: str) -> ContentSource:
    """Fetch video metadata using yt-dlp.

    Returns a ContentSource with title, duration, and publish date.
    """
    import json

    video_id = extract_video_id(url)
    if not video_id:
        msg = f"Could not extract video ID from URL: {url}"
        raise ValueError(msg)

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"

    result = subprocess.run(  # noqa: S603
        [
            "yt-dlp",
            "--dump-json",
            "--no-download",
            canonical_url,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    info = json.loads(result.stdout)
    return ContentSource(
        url=canonical_url,
        title=info.get("title", "Unknown Title"),
        source_type="youtube",
        duration_seconds=info.get("duration"),
        published_at=None,
    )


def fetch_transcript(url: str) -> Transcript:
    """Fetch transcript for a YouTube video.

    Tries captions first via youtube-transcript-api, falls back to
    audio download for whisper transcription.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    video_id = extract_video_id(url)
    if not video_id:
        msg = f"Could not extract video ID from URL: {url}"
        raise ValueError(msg)

    from distill.db import content_id_for_url

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    cid = content_id_for_url(canonical_url)

    try:
        api = YouTubeTranscriptApi()
        transcript_data = api.fetch(video_id)
        segments = [
            TranscriptSegment(
                start=entry.start,
                end=entry.start + entry.duration,
                text=entry.text,
            )
            for entry in transcript_data
        ]
        full_text = " ".join(seg.text for seg in segments)
        return Transcript(
            content_id=cid,
            text=full_text,
            segments=segments,
            language="en",
            method="captions",
        )
    except Exception:
        logger.info(
            "No captions available for %s, will need audio transcription",
            video_id,
        )
        raise


def download_audio(url: str, output_dir: Path | None = None) -> Path:
    """Download audio from a YouTube video using yt-dlp.

    Returns the path to the downloaded audio file.
    """
    video_id = extract_video_id(url)
    if not video_id:
        msg = f"Could not extract video ID from URL: {url}"
        raise ValueError(msg)

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="distill_"))

    output_path = output_dir / f"{video_id}.mp3"
    subprocess.run(  # noqa: S603
        [
            "yt-dlp",
            "-x",
            "--audio-format",
            "mp3",
            "-o",
            str(output_path),
            f"https://www.youtube.com/watch?v={video_id}",
        ],
        check=True,
        capture_output=True,
    )
    return output_path

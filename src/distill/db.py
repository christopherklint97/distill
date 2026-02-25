"""SQLite storage layer for Distill."""

import contextlib
import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from distill.models import (
    Article,
    ContentSource,
    Transcript,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    content_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT,
    source_type TEXT NOT NULL,
    duration_seconds INTEGER,
    published_at TEXT,
    feed_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcripts (
    content_id TEXT PRIMARY KEY REFERENCES sources(content_id),
    text TEXT NOT NULL,
    segments_json TEXT,
    language TEXT,
    method TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id TEXT REFERENCES sources(content_id),
    style TEXT NOT NULL,
    title TEXT,
    body_json TEXT,
    output_path TEXT,
    format TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscriptions (
    feed_url TEXT PRIMARY KEY,
    title TEXT,
    last_checked TEXT,
    last_episode_date TEXT,
    auto_process BOOLEAN DEFAULT FALSE,
    favorite BOOLEAN DEFAULT FALSE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feed_languages (
    feed_url TEXT NOT NULL,
    language TEXT NOT NULL,
    used_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (feed_url, language)
);
"""


def content_id_for_url(url: str) -> str:
    """Generate a content ID (SHA256 hex digest) for a given URL."""
    return hashlib.sha256(url.encode()).hexdigest()


class Database:
    """SQLite database for storing sources, transcripts, articles, and subscriptions."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist and run migrations."""
        self._conn.executescript(_SCHEMA)
        self._migrate_subscriptions_favorite()
        self._conn.commit()

    def _migrate_subscriptions_favorite(self) -> None:
        """Add favorite column to subscriptions if missing."""
        with contextlib.suppress(sqlite3.OperationalError):
            self._conn.execute(
                "ALTER TABLE subscriptions ADD COLUMN favorite BOOLEAN DEFAULT FALSE"
            )

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # --- Sources ---

    def save_source(self, source: ContentSource) -> str:
        """Save a content source, returning its content_id."""
        cid = content_id_for_url(source.url)
        self._conn.execute(
            """INSERT OR REPLACE INTO sources
               (content_id, url, title, source_type, duration_seconds,
                published_at, feed_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                cid,
                source.url,
                source.title,
                source.source_type,
                source.duration_seconds,
                source.published_at.isoformat() if source.published_at else None,
                source.feed_url,
            ),
        )
        self._conn.commit()
        return cid

    def get_source(self, content_id: str) -> ContentSource | None:
        """Retrieve a content source by its content_id."""
        row = self._conn.execute(
            "SELECT * FROM sources WHERE content_id = ?", (content_id,)
        ).fetchone()
        if row is None:
            return None
        return ContentSource(
            url=row["url"],
            title=row["title"],
            source_type=row["source_type"],
            duration_seconds=row["duration_seconds"],
            published_at=(
                datetime.fromisoformat(row["published_at"])
                if row["published_at"]
                else None
            ),
            feed_url=row["feed_url"],
        )

    # --- Transcripts ---

    def save_transcript(self, transcript: Transcript) -> None:
        """Save a transcript."""
        segments_json = json.dumps(
            [seg.model_dump() for seg in transcript.segments]
        )
        self._conn.execute(
            """INSERT OR REPLACE INTO transcripts
               (content_id, text, segments_json, language, method)
               VALUES (?, ?, ?, ?, ?)""",
            (
                transcript.content_id,
                transcript.text,
                segments_json,
                transcript.language,
                transcript.method,
            ),
        )
        self._conn.commit()

    def get_transcript(self, content_id: str) -> Transcript | None:
        """Retrieve a transcript by content_id."""
        row = self._conn.execute(
            "SELECT * FROM transcripts WHERE content_id = ?", (content_id,)
        ).fetchone()
        if row is None:
            return None
        segments = [
            TranscriptSegment(**seg)
            for seg in json.loads(row["segments_json"] or "[]")
        ]
        return Transcript(
            content_id=row["content_id"],
            text=row["text"],
            segments=segments,
            language=row["language"] or "en",
            method=row["method"] or "captions",
        )

    # --- Articles ---

    def save_article(
        self,
        article: Article,
        output_path: str | None = None,
        output_format: str | None = None,
    ) -> int:
        """Save an article, returning its row ID."""
        body_json = article.model_dump_json()
        cursor = self._conn.execute(
            """INSERT INTO articles
               (content_id, style, title, body_json, output_path, format)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                article.content_id,
                article.style,
                article.title,
                body_json,
                output_path,
                output_format,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_article(self, article_id: int) -> Article | None:
        """Retrieve an article by its row ID."""
        row = self._conn.execute(
            "SELECT * FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        if row is None:
            return None
        return Article.model_validate_json(row["body_json"])

    def get_articles_for_content(self, content_id: str) -> list[Article]:
        """Retrieve all articles generated for a given content_id."""
        rows = self._conn.execute(
            "SELECT * FROM articles WHERE content_id = ? ORDER BY created_at DESC",
            (content_id,),
        ).fetchall()
        return [Article.model_validate_json(row["body_json"]) for row in rows]

    def list_history(self, limit: int = 50) -> list[dict[str, object]]:
        """List recent processing history."""
        rows = self._conn.execute(
            """SELECT a.id, a.content_id, a.style, a.title, a.format,
                      a.created_at, s.url, s.source_type
               FROM articles a
               JOIN sources s ON a.content_id = s.content_id
               ORDER BY a.created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    # --- Subscriptions ---

    def save_subscription(
        self,
        feed_url: str,
        title: str | None = None,
        auto_process: bool = False,
        favorite: bool | None = None,
    ) -> None:
        """Add or update a podcast subscription."""
        if favorite is None:
            # Preserve existing favorite value on upsert
            row = self._conn.execute(
                "SELECT favorite FROM subscriptions WHERE feed_url = ?",
                (feed_url,),
            ).fetchone()
            fav = bool(row["favorite"]) if row else False
        else:
            fav = favorite
        self._conn.execute(
            """INSERT OR REPLACE INTO subscriptions
               (feed_url, title, auto_process, favorite)
               VALUES (?, ?, ?, ?)""",
            (feed_url, title, auto_process, fav),
        )
        self._conn.commit()

    def get_subscriptions(self) -> list[dict[str, object]]:
        """List all subscriptions, favorites first."""
        rows = self._conn.execute(
            "SELECT * FROM subscriptions ORDER BY favorite DESC, created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def update_subscription_checked(
        self,
        feed_url: str,
        last_episode_date: str | None = None,
    ) -> None:
        """Update the last-checked timestamp for a subscription."""
        self._conn.execute(
            """UPDATE subscriptions
               SET last_checked = ?, last_episode_date = COALESCE(?, last_episode_date)
               WHERE feed_url = ?""",
            (datetime.now().isoformat(), last_episode_date, feed_url),
        )
        self._conn.commit()

    def set_favorite(self, feed_url: str, favorite: bool) -> None:
        """Set or clear the favorite flag on a subscription."""
        self._conn.execute(
            "UPDATE subscriptions SET favorite = ? WHERE feed_url = ?",
            (favorite, feed_url),
        )
        self._conn.commit()

    def get_recent_feeds(self, limit: int = 10) -> list[dict[str, object]]:
        """Get recent podcast feeds from sources not already in subscriptions."""
        rows = self._conn.execute(
            """SELECT DISTINCT s.feed_url, s.title, MAX(s.created_at) as created_at
               FROM sources s
               LEFT JOIN subscriptions sub ON s.feed_url = sub.feed_url
               WHERE s.source_type = 'podcast'
                 AND s.feed_url IS NOT NULL
                 AND sub.feed_url IS NULL
               GROUP BY s.feed_url
               ORDER BY MAX(s.created_at) DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_subscription(self, feed_url: str) -> None:
        """Remove a subscription."""
        self._conn.execute(
            "DELETE FROM subscriptions WHERE feed_url = ?", (feed_url,)
        )
        self._conn.commit()

    # --- Feed Languages ---

    def save_feed_language(self, feed_url: str, language: str) -> None:
        """Record a language selection for a feed."""
        now = datetime.now().isoformat()
        self._conn.execute(
            """INSERT INTO feed_languages (feed_url, language, used_at)
               VALUES (?, ?, ?)
               ON CONFLICT(feed_url, language)
               DO UPDATE SET used_at = ?""",
            (feed_url, language, now, now),
        )
        self._conn.commit()

    def get_recent_languages(
        self,
        feed_url: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        """Get recently used languages, optionally filtered by feed.

        Returns dicts with 'language', 'feed_url', and 'used_at' keys,
        ordered by most recent use.
        """
        if feed_url:
            rows = self._conn.execute(
                """SELECT language, feed_url, used_at
                   FROM feed_languages
                   WHERE feed_url = ?
                   ORDER BY used_at DESC
                   LIMIT ?""",
                (feed_url, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT language, MAX(feed_url) as feed_url,
                          MAX(used_at) as used_at
                   FROM feed_languages
                   GROUP BY language
                   ORDER BY MAX(used_at) DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

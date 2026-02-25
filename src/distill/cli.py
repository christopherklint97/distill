"""CLI commands for Distill."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from distill.transcription.base import Transcriber

import typer
from rich.console import Console
from rich.table import Table

from distill.config import DistillConfig, load_config, set_config_value
from distill.db import Database, content_id_for_url
from distill.models import ContentSource, Transcript

app = typer.Typer(
    name="distill",
    help="Transform YouTube videos and podcast episodes into readable articles.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Manage configuration.")
app.add_typer(config_app, name="config")

console = Console()
logger = logging.getLogger(__name__)


def _get_config() -> DistillConfig:
    return load_config()


def _get_db(config: DistillConfig) -> Database:
    output_dir = Path(config.general.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    return Database(output_dir / "distill.db")


def _write_output(
    content: str,
    filename: str,
    output_dir: Path,
    output_format: str,
) -> Path:
    """Write content to a file and return the path."""
    ext = {"markdown": ".md", "html": ".html", "epub": ".epub"}
    path = output_dir / f"{filename}{ext.get(output_format, '.md')}"
    path.write_text(content)
    return path


def _generate_and_save(
    transcript: Transcript,
    source: ContentSource,
    style: str,
    output_format: str,
    output_dir: Path,
    config: DistillConfig,
    db: Database,
    language: str = "en",
    send: str | None = None,
) -> Path:
    """Run article generation pipeline and save results."""
    from distill.article.generator import generate_article
    from distill.output import epub as epub_out
    from distill.output import html as html_out
    from distill.output import markdown as md_out

    console.print("[bold]Generating article...[/bold]")
    article = generate_article(
        transcript.text,
        transcript.content_id,
        source,
        style=style,
        config=config.claude,
        language=language,
    )

    # Render output
    safe_title = "".join(
        c if c.isalnum() or c in " -_" else "" for c in article.title
    )[:80].strip()
    if not safe_title:
        safe_title = transcript.content_id[:16]

    output_dir.mkdir(parents=True, exist_ok=True)

    if output_format == "epub":
        path = output_dir / f"{safe_title}.epub"
        epub_out.render(article, str(path))
    elif output_format == "html":
        content = html_out.render(article)
        path = output_dir / f"{safe_title}.html"
        path.write_text(content)
    else:
        content = md_out.render(article)
        path = output_dir / f"{safe_title}.md"
        path.write_text(content)

    db.save_article(article, output_path=str(path), output_format=output_format)
    console.print(f"[green]Article saved to {path}[/green]")

    if send == "email":
        from distill.output.email import send_email

        to = config.email.to
        from_addr = config.email.from_addr
        send_email(article, to=to, from_addr=from_addr)
        console.print(f"[green]Article emailed to {to}[/green]")

    return path


FormatOption = Annotated[
    str,
    typer.Option("--format", "-f", help="Output format: markdown, html, epub"),
]
StyleOption = Annotated[
    str,
    typer.Option(
        "--style", "-s",
        help="Article style: detailed, concise, summary, bullets",
    ),
]
OutputOption = Annotated[
    str | None,
    typer.Option("--output", "-o", help="Output directory"),
]
LanguageOption = Annotated[
    str | None,
    typer.Option(
        "--language", "-l",
        help="Language code for transcription (e.g., en, sv)",
    ),
]
ArticleLanguageOption = Annotated[
    str | None,
    typer.Option(
        "--article-language",
        help="Language for the generated article (e.g., en, sv)",
    ),
]
SendOption = Annotated[
    str | None,
    typer.Option(
        "--send",
        help="Send the article via a delivery method (e.g., email)",
    ),
]


@app.command()
def youtube(
    url: Annotated[str, typer.Argument(help="YouTube video URL")],
    format: FormatOption = "markdown",
    style: StyleOption = "detailed",
    output: OutputOption = None,
    language: LanguageOption = None,
    article_language: ArticleLanguageOption = None,
    send: SendOption = None,
) -> None:
    """Process a YouTube video into an article."""
    from distill.sources.youtube import extract_video_id, fetch_transcript

    config = _get_config()
    db = _get_db(config)

    video_id = extract_video_id(url)
    if not video_id:
        console.print("[red]Invalid YouTube URL.[/red]")
        raise typer.Exit(1)

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    cid = content_id_for_url(canonical_url)

    # Check cache
    existing = db.get_transcript(cid)
    if existing:
        console.print("[dim]Using cached transcript.[/dim]")
        transcript = existing
        source = db.get_source(cid)
        if source is None:
            console.print("[red]Cached source not found.[/red]")
            raise typer.Exit(1)
    else:
        console.print(f"[bold]Fetching transcript for {video_id}...[/bold]")
        try:
            transcript = fetch_transcript(url)
        except Exception as e:
            console.print(f"[red]Failed to fetch transcript: {e}[/red]")
            console.print(
                "[dim]Hint: If no captions are available, audio transcription "
                "is needed (install whisper extra).[/dim]"
            )
            raise typer.Exit(1) from e

        # Fetch metadata
        try:
            from distill.sources.youtube import fetch_metadata

            source = fetch_metadata(url)
        except Exception:
            source = ContentSource(
                url=canonical_url,
                title=f"YouTube Video {video_id}",
                source_type="youtube",
            )

        db.save_source(source)
        db.save_transcript(transcript)

    output_dir = (
        Path(output)
        if output
        else Path(config.general.output_dir).expanduser()
    )
    article_lang = (
        article_language or language or config.whisper.language
    )
    _generate_and_save(
        transcript, source, style, format, output_dir, config, db,
        article_lang, send,
    )
    db.close()


@app.command()
def podcast(
    feed_url: Annotated[str, typer.Argument(help="Podcast RSS feed URL")],
    format: FormatOption = "markdown",
    style: StyleOption = "detailed",
    output: OutputOption = None,
    language: LanguageOption = None,
    article_language: ArticleLanguageOption = None,
    send: SendOption = None,
) -> None:
    """Browse and process episodes from a podcast feed."""
    from distill.sources.podcast import (
        download_episode,
        episode_to_source,
        parse_feed,
    )

    config = _get_config()
    db = _get_db(config)

    console.print(f"[bold]Parsing feed: {feed_url}[/bold]")
    try:
        feed = parse_feed(feed_url)
    except Exception as e:
        console.print(f"[red]Failed to parse feed: {e}[/red]")
        raise typer.Exit(1) from e

    if not feed.episodes:
        console.print("[yellow]No episodes found in feed.[/yellow]")
        raise typer.Exit(0)

    # Interactive episode selection
    console.print(f"\n[bold]{feed.title}[/bold]\n")
    for i, ep in enumerate(feed.episodes[:20]):
        date_str = (
            ep.published_at.strftime("%Y-%m-%d")
            if ep.published_at
            else "Unknown"
        )
        console.print(f"  [{i + 1}] {ep.title} ({date_str})")

    choice = typer.prompt("\nSelect episode number", type=int)
    if choice < 1 or choice > len(feed.episodes):
        console.print("[red]Invalid selection.[/red]")
        raise typer.Exit(1)

    episode = feed.episodes[choice - 1]
    source = episode_to_source(episode, feed_url)
    cid = content_id_for_url(source.url)

    existing = db.get_transcript(cid)
    if existing:
        console.print("[dim]Using cached transcript.[/dim]")
        transcript = existing
    else:
        console.print(f"[bold]Downloading: {episode.title}[/bold]")
        audio_path = download_episode(episode.audio_url)
        transcript = _transcribe_audio(audio_path, cid, config, language)

    db.save_source(source)
    db.save_transcript(transcript)

    output_dir = (
        Path(output)
        if output
        else Path(config.general.output_dir).expanduser()
    )
    article_lang = (
        article_language or language or config.whisper.language
    )
    _generate_and_save(
        transcript, source, style, format, output_dir, config, db,
        article_lang, send,
    )
    db.close()


@app.command(name="podcast-episode")
def podcast_episode(
    audio_url: Annotated[str, typer.Argument(help="Direct audio URL")],
    title: Annotated[str, typer.Option("--title", "-t")] = "Podcast Episode",
    format: FormatOption = "markdown",
    style: StyleOption = "detailed",
    output: OutputOption = None,
    language: LanguageOption = None,
    article_language: ArticleLanguageOption = None,
    send: SendOption = None,
) -> None:
    """Process a podcast episode from a direct audio URL."""
    from distill.sources.podcast import download_episode

    config = _get_config()
    db = _get_db(config)

    cid = content_id_for_url(audio_url)
    source = ContentSource(
        url=audio_url, title=title, source_type="podcast"
    )

    existing = db.get_transcript(cid)
    if existing:
        console.print("[dim]Using cached transcript.[/dim]")
        transcript = existing
    else:
        console.print("[bold]Downloading audio...[/bold]")
        audio_path = download_episode(audio_url)
        transcript = _transcribe_audio(audio_path, cid, config, language)

    db.save_source(source)
    db.save_transcript(transcript)

    output_dir = (
        Path(output)
        if output
        else Path(config.general.output_dir).expanduser()
    )
    article_lang = (
        article_language or language or config.whisper.language
    )
    _generate_and_save(
        transcript, source, style, format, output_dir, config, db,
        article_lang, send,
    )
    db.close()


def _transcribe_audio(
    audio_path: Path,
    content_id: str,
    config: DistillConfig,
    language_override: str | None = None,
) -> Transcript:
    """Transcribe an audio file using the configured backend."""
    backend = config.whisper.backend
    language = language_override or config.whisper.language

    console.print(f"[bold]Transcribing with {backend} backend...[/bold]")

    transcriber: Transcriber
    if backend == "api":
        from distill.transcription.whisper_api import WhisperAPITranscriber

        transcriber = WhisperAPITranscriber()
    else:
        from distill.transcription.whisper_local import (
            WhisperLocalTranscriber,
        )

        transcriber = WhisperLocalTranscriber(
            model_name=config.whisper.model,
        )

    text, segments = transcriber.transcribe(audio_path, language=language)
    method = "whisper_api" if backend == "api" else "whisper_local"

    return Transcript(
        content_id=content_id,
        text=text,
        segments=segments,
        language=language,
        method=method,  # type: ignore[arg-type]
    )


@app.command()
def subscribe(
    feed_url: Annotated[str, typer.Argument(help="Podcast RSS feed URL")],
    auto_process: Annotated[
        bool, typer.Option("--auto-process", help="Automatically process new episodes")
    ] = False,
) -> None:
    """Subscribe to a podcast feed."""
    from distill.sources.podcast import parse_feed

    config = _get_config()
    db = _get_db(config)

    try:
        feed = parse_feed(feed_url)
        title = feed.title
    except Exception:
        title = None

    db.save_subscription(feed_url, title=title, auto_process=auto_process)
    console.print(f"[green]Subscribed to {title or feed_url}[/green]")
    db.close()


@app.command()
def subscriptions() -> None:
    """List all podcast subscriptions."""
    config = _get_config()
    db = _get_db(config)

    subs = db.get_subscriptions()
    if not subs:
        console.print("[dim]No subscriptions yet.[/dim]")
        db.close()
        return

    table = Table(title="Podcast Subscriptions")
    table.add_column("Title", style="bold")
    table.add_column("Feed URL")
    table.add_column("Last Checked")
    table.add_column("Auto")

    for sub in subs:
        table.add_row(
            str(sub.get("title", "")),
            str(sub["feed_url"]),
            str(sub.get("last_checked", "Never")),
            "Yes" if sub.get("auto_process") else "No",
        )

    console.print(table)
    db.close()


@app.command()
def sync() -> None:
    """Check subscribed feeds for new episodes."""
    from distill.sources.podcast import parse_feed

    config = _get_config()
    db = _get_db(config)

    subs = db.get_subscriptions()
    if not subs:
        console.print("[dim]No subscriptions to sync.[/dim]")
        db.close()
        return

    for sub in subs:
        feed_url = str(sub["feed_url"])
        console.print(f"[bold]Checking {sub.get('title', feed_url)}...[/bold]")
        try:
            feed = parse_feed(feed_url)
            if feed.episodes:
                latest = feed.episodes[0]
                date_str = (
                    latest.published_at.isoformat() if latest.published_at else None
                )
                db.update_subscription_checked(feed_url, date_str)
                console.print(f"  Latest: {latest.title}")
            else:
                db.update_subscription_checked(feed_url)
                console.print("  No episodes found.")
        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")

    db.close()


@app.command()
def history(
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
) -> None:
    """Show processing history."""
    config = _get_config()
    db = _get_db(config)

    items = db.list_history(limit=limit)
    if not items:
        console.print("[dim]No history yet.[/dim]")
        db.close()
        return

    table = Table(title="Processing History")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Style")
    table.add_column("Format")
    table.add_column("Type")
    table.add_column("Date")

    for item in items:
        table.add_row(
            str(item.get("content_id", ""))[:12],
            str(item.get("title", "")),
            str(item.get("style", "")),
            str(item.get("format", "")),
            str(item.get("source_type", "")),
            str(item.get("created_at", ""))[:10],
        )

    console.print(table)
    db.close()


@app.command()
def regenerate(
    content_id: Annotated[str, typer.Argument(help="Content ID (from history)")],
    format: FormatOption = "markdown",
    style: StyleOption = "detailed",
    output: OutputOption = None,
    language: LanguageOption = None,
    article_language: ArticleLanguageOption = None,
    send: SendOption = None,
) -> None:
    """Regenerate an article from a cached transcript."""
    config = _get_config()
    db = _get_db(config)

    source = db.get_source(content_id)
    if source is None:
        console.print("[red]Content ID not found.[/red]")
        raise typer.Exit(1)

    transcript = db.get_transcript(content_id)
    if transcript is None:
        console.print("[red]No cached transcript for this content.[/red]")
        raise typer.Exit(1)

    article_lang = (
        article_language or language or transcript.language
    )
    output_dir = (
        Path(output)
        if output
        else Path(config.general.output_dir).expanduser()
    )
    _generate_and_save(
        transcript, source, style, format, output_dir, config, db,
        article_lang, send,
    )
    db.close()


@config_app.command("show")
def config_show() -> None:
    """Show current configuration."""
    config = _get_config()
    console.print("[bold]Current Configuration[/bold]\n")

    sections = {
        "general": config.general,
        "whisper": config.whisper,
        "claude": config.claude,
        "email": config.email,
        "subscriptions": config.subscriptions,
    }

    for name, section in sections.items():
        console.print(f"[bold cyan][{name}][/bold cyan]")
        for key, value in section.__dict__.items():
            console.print(f"  {key} = {value}")
        console.print()


@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="Config key (e.g., whisper.backend)")],
    value: Annotated[str, typer.Argument(help="Value to set")],
) -> None:
    """Set a configuration value."""
    try:
        set_config_value(key, value)
        console.print(f"[green]Set {key} = {value}[/green]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

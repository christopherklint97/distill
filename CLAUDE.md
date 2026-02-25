# Distill — Development Guide

## Project Overview
CLI tool that transforms YouTube videos and podcast episodes into readable articles using LLM-powered summarization.

## Tech Stack
- Python 3.12+, managed with `uv`
- CLI: `typer` + `rich`
- LLM: Anthropic Claude via `anthropic` SDK
- Transcription: `youtube-transcript-api`, `yt-dlp`, `openai-whisper`
- Podcast: `feedparser`, `httpx`
- Storage: SQLite via stdlib `sqlite3`
- Config: TOML via stdlib `tomllib`
- Output: `markdown`, `ebooklib`

## Commands
```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/

# Format
uv run ruff format src/ tests/

# Run the CLI
uv run distill --help
```

## Project Structure
- `src/distill/` — Main package (src layout)
- `src/distill/models.py` — Pydantic data models
- `src/distill/config.py` — TOML config loading
- `src/distill/db.py` — SQLite storage layer
- `src/distill/sources/` — YouTube + podcast extraction
- `src/distill/transcription/` — Whisper backends
- `src/distill/article/` — LLM article generation
- `src/distill/output/` — Markdown, HTML, EPUB rendering
- `src/distill/cli.py` — Typer CLI commands

## Conventions
- Type hints on all functions (`mypy --strict`)
- No function over 50 lines
- Use `logging` stdlib, not print
- All external API calls use retry with exponential backoff
- `content_id` = SHA256 of source URL

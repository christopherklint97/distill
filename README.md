# Distill

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

Transform YouTube videos and podcast episodes into readable articles using LLM-powered summarization.

## Features

- **YouTube processing** — Extract captions or transcribe audio, then generate articles
- **Podcast support** — Parse RSS feeds, browse episodes, download and transcribe audio
- **Multiple article styles** — Detailed, concise, summary, or bullet-point formats
- **Multiple output formats** — Markdown, HTML, or EPUB
- **Subscription management** — Subscribe to podcast feeds and sync for new episodes
- **Local caching** — SQLite database stores transcripts and articles for fast regeneration
- **Configurable** — TOML config file with environment variable overrides

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/christopherklint97/distill.git
cd distill
uv sync
```

For local Whisper transcription (optional, large download):

```bash
uv sync --extra whisper
```

### Environment Variables

```bash
export ANTHROPIC_API_KEY="your-key"    # Required — Claude API
export OPENAI_API_KEY="your-key"       # Optional — Whisper API backend
```

## Usage

### YouTube

```bash
# Process a YouTube video (default: markdown, detailed style)
distill youtube "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Specify format and style
distill youtube "https://youtu.be/dQw4w9WgXcQ" --format html --style concise

# Save to a specific directory
distill youtube "https://youtube.com/watch?v=abc123" --output ./articles/

# Set transcription language
distill youtube "https://youtube.com/watch?v=abc123" --language sv

# Transcribe in Swedish but write the article in English
distill youtube "https://youtube.com/watch?v=abc123" --language sv --article-language en
```

### Podcasts

```bash
# Browse and select an episode from a feed
distill podcast "https://example.com/feed.xml"

# Process a direct audio URL
distill podcast-episode "https://example.com/episode.mp3" --title "Episode Name"
```

### Subscriptions

```bash
# Subscribe to a feed
distill subscribe "https://example.com/feed.xml" --auto-process

# List subscriptions
distill subscriptions

# Check for new episodes
distill sync
```

### History & Regeneration

```bash
# View processing history
distill history

# Regenerate with a different style
distill regenerate <content-id> --style bullets --format epub

# Regenerate in a different language
distill regenerate <content-id> --article-language sv
```

### Configuration

```bash
# Show current config
distill config show

# Change settings
distill config set whisper.backend api
distill config set claude.model claude-sonnet-4-6
```

Config file location: `~/.config/distill/config.toml`

```toml
[general]
output_dir = "~/Documents/distill"
default_format = "markdown"
default_style = "detailed"

[whisper]
backend = "local"    # "local" or "api"
model = "base"       # tiny, base, small, medium, large
language = "en"

[claude]
model = "claude-sonnet-4-6"
max_tokens = 8192

[subscriptions]
check_interval_hours = 24
auto_process = false
```

## Article Styles

| Style | Description |
|-------|-------------|
| `detailed` | Comprehensive article preserving most content |
| `concise` | Key points and highlights (~30% of original) |
| `summary` | Executive summary in 3-5 paragraphs |
| `bullets` | Structured bullet-point notes |

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/

# Format
uv run ruff format src/ tests/
```

## Architecture

```
src/distill/
├── cli.py              # Typer CLI commands
├── config.py           # TOML config loading
├── db.py               # SQLite storage layer
├── models.py           # Pydantic data models
├── sources/
│   ├── youtube.py      # YouTube URL parsing & transcript fetching
│   └── podcast.py      # RSS feed parsing & audio download
├── transcription/
│   ├── base.py         # Abstract transcriber interface
│   ├── whisper_local.py # Local Whisper model
│   └── whisper_api.py  # OpenAI Whisper API
├── article/
│   ├── prompts.py      # LLM prompt templates
│   └── generator.py    # Article generation orchestration
└── output/
    ├── markdown.py     # Markdown renderer
    ├── html.py         # HTML renderer
    └── epub.py         # EPUB renderer
```

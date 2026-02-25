"""Article generation orchestration using Claude API."""

import json
import logging
import time

import anthropic

from distill.article.prompts import (
    build_chunk_prompt,
    build_generation_prompt,
    build_synthesis_prompt,
)
from distill.config import ClaudeConfig
from distill.models import Article, ArticleSection, ContentSource

logger = logging.getLogger(__name__)

# Approximate token limit for single-pass generation
_SINGLE_PASS_CHAR_LIMIT = 200_000  # ~50k tokens
_CHUNK_SIZE_CHARS = 200_000  # ~50k tokens per chunk
_CHUNK_OVERLAP_CHARS = 2_000  # Overlap between chunks
_MAX_RETRIES = 3
_RETRY_DELAY = 2.0


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _call_claude(
    client: anthropic.Anthropic,
    system: str,
    user: str,
    config: ClaudeConfig,
) -> str:
    """Make a Claude API call with retry logic."""
    for attempt in range(_MAX_RETRIES):
        try:
            message = client.messages.create(
                model=config.model,
                max_tokens=config.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return message.content[0].text  # type: ignore[union-attr]
        except anthropic.APIError as e:
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAY * (2**attempt)
                logger.warning(
                    "Claude API error (attempt %d/%d): %s. Retrying in %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    e,
                    delay,
                )
                time.sleep(delay)
            else:
                raise
    msg = "Unexpected: exhausted retries"
    raise RuntimeError(msg)


def _parse_article_json(
    raw: str,
    content_id: str,
    style: str,
    source: ContentSource,
) -> Article:
    """Parse the JSON response from Claude into an Article model."""
    # Extract JSON from markdown code blocks if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (code fences)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    data = json.loads(text)
    sections = [
        ArticleSection(heading=s["heading"], body=s["body"])
        for s in data.get("sections", [])
    ]
    return Article(
        content_id=content_id,
        title=data.get("title", source.title),
        subtitle=data.get("subtitle"),
        sections=sections,
        summary=data.get("summary", ""),
        style=style,  # type: ignore[arg-type]
        source=source,
    )


def generate_article(
    transcript_text: str,
    content_id: str,
    source: ContentSource,
    style: str = "detailed",
    config: ClaudeConfig | None = None,
    client: anthropic.Anthropic | None = None,
    language: str = "en",
) -> Article:
    """Generate an article from a transcript.

    Uses single-pass for short transcripts or chunked summarization
    for long ones.
    """
    if config is None:
        config = ClaudeConfig()
    if client is None:
        client = anthropic.Anthropic()

    if len(transcript_text) <= _SINGLE_PASS_CHAR_LIMIT:
        return _generate_single_pass(
            transcript_text, content_id, source, style, config, client,
            language,
        )
    return _generate_chunked(
        transcript_text, content_id, source, style, config, client,
        language,
    )


def _generate_single_pass(
    transcript_text: str,
    content_id: str,
    source: ContentSource,
    style: str,
    config: ClaudeConfig,
    client: anthropic.Anthropic,
    language: str = "en",
) -> Article:
    """Generate an article in a single API call."""
    logger.info(
        "Generating article (single-pass, ~%d tokens)",
        _estimate_tokens(transcript_text),
    )
    system, user = build_generation_prompt(
        transcript_text, source, style, language,
    )
    raw = _call_claude(client, system, user, config)
    return _parse_article_json(raw, content_id, style, source)


def _generate_chunked(
    transcript_text: str,
    content_id: str,
    source: ContentSource,
    style: str,
    config: ClaudeConfig,
    client: anthropic.Anthropic,
    language: str = "en",
) -> Article:
    """Generate an article using chunked summarization."""
    chunks = _split_into_chunks(transcript_text)
    logger.info(
        "Generating article (chunked, %d chunks, ~%d tokens total)",
        len(chunks),
        _estimate_tokens(transcript_text),
    )

    summaries: list[str] = []
    for i, chunk in enumerate(chunks):
        prompt = build_chunk_prompt(chunk, i + 1, len(chunks))
        summary = _call_claude(client, "", prompt, config)
        summaries.append(summary)
        logger.info("Summarized chunk %d/%d", i + 1, len(chunks))

    system, user = build_synthesis_prompt(
        summaries, source, style, language,
    )
    raw = _call_claude(client, system, user, config)
    return _parse_article_json(raw, content_id, style, source)


def _split_into_chunks(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE_CHARS
        if end >= len(text):
            chunks.append(text[start:])
            break
        # Try to break at a sentence boundary
        boundary = text.rfind(". ", start + _CHUNK_SIZE_CHARS - 1000, end)
        if boundary > start:
            end = boundary + 1
        chunks.append(text[start:end])
        start = end - _CHUNK_OVERLAP_CHARS
    return chunks

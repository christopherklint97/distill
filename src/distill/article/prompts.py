"""Prompt templates for article generation."""

from distill.models import ContentSource

_SYSTEM_PROMPT_TEMPLATE = """You are an expert writer who transforms video \
and podcast transcripts into well-structured, readable articles. You preserve \
the key insights, arguments, and information from the original content while \
making it engaging to read.

Guidelines:
- Preserve direct quotes when they are particularly insightful
- Attribute speakers when speaker information is available
- Generate a descriptive title that captures the essence of the content
- Include a TLDR/summary at the top
- Use clear section headings to organize the content
- Maintain the original tone and voice where appropriate
- Write the article in {language}"""


_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "sv": "Swedish",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "nl": "Dutch",
    "it": "Italian",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
}


def _system_prompt(language: str) -> str:
    """Build the system prompt with the target language."""
    lang_name = _LANGUAGE_NAMES.get(language, language)
    return _SYSTEM_PROMPT_TEMPLATE.format(language=lang_name)

_STYLE_INSTRUCTIONS = {
    "detailed": (
        "Write a comprehensive, detailed article that preserves most of the "
        "original content. Include all key points, examples, and supporting "
        "arguments. The article should be thorough enough that a reader would "
        "not need to watch/listen to the original content."
    ),
    "concise": (
        "Write a concise article highlighting the key points and most important "
        "insights. Aim for approximately 30% of the original content length. "
        "Focus on the main arguments and conclusions, omitting tangential "
        "discussion and repetition."
    ),
    "summary": (
        "Write an executive summary of 3-5 paragraphs capturing the core message "
        "and key takeaways. This should give readers a quick understanding of "
        "what was discussed and the main conclusions."
    ),
    "bullets": (
        "Create structured bullet-point notes organized by topic. Use nested "
        "bullets for sub-points. Include key quotes, statistics, and actionable "
        "insights. This format should be easy to scan and reference later."
    ),
}

_OUTPUT_FORMAT = """Respond with a JSON object matching this exact structure:
{
  "title": "A descriptive article title",
  "subtitle": "An optional subtitle or null",
  "summary": "A 2-3 sentence TLDR summary",
  "sections": [
    {
      "heading": "Section Heading",
      "body": "Section content in markdown format"
    }
  ]
}"""

_CHUNK_SUMMARY_PROMPT = """Summarize this section of a transcript, preserving \
key points, quotes, and insights. This is part {chunk_num} of \
{total_chunks} of a longer transcript.

Transcript section:
{text}

Provide a detailed summary that can later be combined with summaries \
of other sections."""

_SYNTHESIS_PROMPT = """You have summaries of different sections of a \
transcript. Synthesize these into a single coherent article.

Source: {source_title}

Section summaries:
{summaries}

{style_instruction}

{output_format}"""


def build_generation_prompt(
    transcript_text: str,
    source: ContentSource,
    style: str,
    language: str = "en",
) -> tuple[str, str]:
    """Build the system and user prompts for article generation.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    style_instruction = _STYLE_INSTRUCTIONS.get(
        style, _STYLE_INSTRUCTIONS["detailed"]
    )

    source_info = f"Title: {source.title}\nType: {source.source_type}"
    if source.published_at:
        source_info += (
            f"\nPublished: {source.published_at.strftime('%Y-%m-%d')}"
        )

    user_prompt = f"""Transform the following transcript into an article.

Source Information:
{source_info}

Style: {style_instruction}

{_OUTPUT_FORMAT}

Transcript:
{transcript_text}"""

    return _system_prompt(language), user_prompt


def build_chunk_prompt(
    text: str, chunk_num: int, total_chunks: int
) -> str:
    """Build a prompt for summarizing a transcript chunk."""
    return _CHUNK_SUMMARY_PROMPT.format(
        text=text, chunk_num=chunk_num, total_chunks=total_chunks
    )


def build_synthesis_prompt(
    summaries: list[str],
    source: ContentSource,
    style: str,
    language: str = "en",
) -> tuple[str, str]:
    """Build prompts for synthesizing chunk summaries into a final article."""
    style_instruction = _STYLE_INSTRUCTIONS.get(
        style, _STYLE_INSTRUCTIONS["detailed"]
    )
    numbered = "\n\n".join(
        f"--- Section {i + 1} ---\n{s}" for i, s in enumerate(summaries)
    )
    user_prompt = _SYNTHESIS_PROMPT.format(
        source_title=source.title,
        summaries=numbered,
        style_instruction=style_instruction,
        output_format=_OUTPUT_FORMAT,
    )
    return _system_prompt(language), user_prompt

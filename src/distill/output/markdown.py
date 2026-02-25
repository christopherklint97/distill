"""Markdown output renderer."""

from distill.models import Article


def render(article: Article) -> str:
    """Render an Article as Markdown."""
    lines: list[str] = []

    lines.append(f"# {article.title}")
    if article.subtitle:
        lines.append(f"\n*{article.subtitle}*")

    lines.append(f"\n> **TLDR:** {article.summary}")

    source = article.source
    meta_parts = [f"Source: [{source.title}]({source.url})"]
    if source.published_at:
        meta_parts.append(f"Published: {source.published_at.strftime('%Y-%m-%d')}")
    lines.append(f"\n*{' | '.join(meta_parts)}*")

    lines.append("")
    for section in article.sections:
        lines.append(f"## {section.heading}")
        lines.append(f"\n{section.body}")
        lines.append("")

    return "\n".join(lines)

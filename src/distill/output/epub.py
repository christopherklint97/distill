"""EPUB output renderer."""

import logging

from ebooklib import epub

from distill.models import Article
from distill.output.html import render as render_html

logger = logging.getLogger(__name__)


def render(article: Article, output_path: str) -> str:
    """Render an Article as an EPUB file.

    Args:
        article: The article to render.
        output_path: Path to write the EPUB file.

    Returns:
        The output path.
    """
    book = epub.EpubBook()

    book.set_identifier(article.content_id)
    book.set_title(article.title)
    book.set_language("en")
    book.add_author(article.source.title)

    # Create main content chapter
    chapter = epub.EpubHtml(
        title=article.title, file_name="content.xhtml", lang="en"
    )
    chapter.content = render_html(article)
    book.add_item(chapter)

    # Table of contents and spine
    book.toc = [chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    # Add default CSS
    style = epub.EpubItem(
        uid="style",
        file_name="style/default.css",
        media_type="text/css",
        content=b"""
body { font-family: serif; line-height: 1.6; }
h1 { border-bottom: 2px solid #333; padding-bottom: 0.5rem; }
h2 { color: #555; margin-top: 2rem; }
blockquote { border-left: 4px solid #ddd; padding-left: 1rem; color: #666; }
""",
    )
    book.add_item(style)

    epub.write_epub(output_path, book)
    logger.info("EPUB written to %s", output_path)
    return output_path

"""HTML output renderer."""

import markdown as md

from distill.models import Article
from distill.output.markdown import render as render_markdown


def render(article: Article) -> str:
    """Render an Article as HTML."""
    md_text = render_markdown(article)
    body: str = md.markdown(md_text, extensions=["extra", "toc"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article.title}</title>
    <style>
        body {{
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
        h2 {{ color: #555; margin-top: 2rem; }}
        blockquote {{
            border-left: 4px solid #ddd;
            padding-left: 1rem;
            color: #666;
            margin: 1rem 0;
        }}
        a {{ color: #0066cc; }}
    </style>
</head>
<body>
{body}
</body>
</html>"""

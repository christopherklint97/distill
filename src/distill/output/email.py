"""Email delivery via Resend API."""

import logging
import os
import time

import httpx

from distill.models import Article
from distill.output import html as html_out

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"
_MAX_RETRIES = 3
_RETRY_DELAY = 2.0


def send_email(article: Article, to: str, from_addr: str) -> None:
    """Send an article as an HTML email via the Resend API.

    Args:
        article: The article to send.
        to: Recipient email address.
        from_addr: Sender address (e.g. ``Distill <distill@resend.dev>``).

    Raises:
        ValueError: If ``to`` is empty or ``RESEND_API_KEY`` is not set.
        httpx.HTTPStatusError: On non-retryable API errors.
    """
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        msg = "RESEND_API_KEY environment variable is not set"
        raise ValueError(msg)
    if not to:
        msg = "Recipient email address is required"
        raise ValueError(msg)

    html_body = html_out.render(article)
    payload: dict[str, object] = {
        "from": from_addr,
        "to": [to],
        "subject": article.title,
        "html": html_body,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    _post_with_retry(payload, headers)
    logger.info("Email sent to %s: %s", to, article.title)


def _post_with_retry(
    payload: dict[str, object],
    headers: dict[str, str],
) -> None:
    """POST to the Resend API with exponential backoff on 5xx errors."""
    for attempt in range(_MAX_RETRIES):
        response = httpx.post(
            _RESEND_URL, json=payload, headers=headers, timeout=30.0
        )
        if response.status_code < 500:
            response.raise_for_status()
            return
        if attempt < _MAX_RETRIES - 1:
            delay = _RETRY_DELAY * (2**attempt)
            logger.warning(
                "Resend API error %d (attempt %d/%d). Retrying in %.1fs",
                response.status_code,
                attempt + 1,
                _MAX_RETRIES,
                delay,
            )
            time.sleep(delay)
    response.raise_for_status()

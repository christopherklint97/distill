"""Tests for email delivery via Resend API."""

import os
from unittest.mock import patch

import httpx
import pytest
import respx

from distill.models import Article, ArticleSection, ContentSource
from distill.output.email import send_email

_RESEND_URL = "https://api.resend.com/emails"


def _make_article() -> Article:
    return Article(
        content_id="abc123",
        title="Test Article",
        sections=[
            ArticleSection(heading="Intro", body="Hello world."),
        ],
        summary="A summary.",
        style="detailed",
        source=ContentSource(
            url="https://example.com",
            title="Source",
            source_type="youtube",
        ),
    )


class TestSendEmail:
    @respx.mock
    def test_success(self) -> None:
        route = respx.post(_RESEND_URL).mock(
            return_value=httpx.Response(200, json={"id": "email_123"})
        )
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}):
            send_email(
                _make_article(),
                to="user@example.com",
                from_addr="Distill <distill@resend.dev>",
            )
        assert route.called
        request = route.calls[0].request
        assert b'"to":["user@example.com"]' in request.content
        assert b'"subject":"Test Article"' in request.content

    def test_missing_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            # Ensure RESEND_API_KEY is not set
            os.environ.pop("RESEND_API_KEY", None)
            with pytest.raises(ValueError, match="RESEND_API_KEY"):
                send_email(
                    _make_article(),
                    to="user@example.com",
                    from_addr="Distill <distill@resend.dev>",
                )

    def test_missing_recipient(self) -> None:
        with (
            patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}),
            pytest.raises(ValueError, match="Recipient"),
        ):
            send_email(
                _make_article(),
                to="",
                from_addr="Distill <distill@resend.dev>",
            )

    @respx.mock
    def test_retry_on_5xx(self) -> None:
        route = respx.post(_RESEND_URL).mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(502),
                httpx.Response(200, json={"id": "email_123"}),
            ]
        )
        with (
            patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}),
            patch("distill.output.email.time.sleep"),
        ):
            send_email(
                _make_article(),
                to="user@example.com",
                from_addr="Distill <distill@resend.dev>",
            )
        assert route.call_count == 3

    @respx.mock
    def test_raises_on_4xx(self) -> None:
        respx.post(_RESEND_URL).mock(
            return_value=httpx.Response(
                422, json={"message": "Invalid email"}
            )
        )
        with (
            patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}),
            pytest.raises(httpx.HTTPStatusError),
        ):
            send_email(
                _make_article(),
                to="user@example.com",
                from_addr="Distill <distill@resend.dev>",
            )

    @respx.mock
    def test_raises_after_max_retries(self) -> None:
        respx.post(_RESEND_URL).mock(
            return_value=httpx.Response(500)
        )
        with (
            patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}),
            patch("distill.output.email.time.sleep"),
            pytest.raises(httpx.HTTPStatusError),
        ):
            send_email(
                _make_article(),
                to="user@example.com",
                from_addr="Distill <distill@resend.dev>",
            )

"""Phase-3 research runner (slice 4) — the Resend email notification (offline; HTTP POST injected)."""

from health_tech_research_agent.webapp import email


class _Poster:
    """Captures the Resend request instead of sending it; returns a configurable status."""

    def __init__(self, status=200):
        self.status = status
        self.calls = []

    def __call__(self, url, headers, payload):
        self.calls.append({"url": url, "headers": headers, "payload": payload})
        return self.status, "{}"


def test_send_email_posts_and_returns_true_on_2xx():
    poster = _Poster(200)
    ok = email.send_email(api_key="re_x", to="k@example.com", subject="Hi", html="<p>hi</p>", poster=poster)
    assert ok is True
    call = poster.calls[0]
    assert call["url"] == email.RESEND_URL
    assert call["headers"]["Authorization"] == "Bearer re_x"
    assert call["payload"] == {"from": email.DEFAULT_FROM, "to": ["k@example.com"],
                               "subject": "Hi", "html": "<p>hi</p>"}


def test_send_email_false_on_error_status():
    assert email.send_email(api_key="re_x", to="k@x.com", subject="s", html="h", poster=_Poster(422)) is False


def test_send_email_noop_without_key_or_recipient():
    poster = _Poster(200)
    assert email.send_email(api_key="", to="k@x.com", subject="s", html="h", poster=poster) is False
    assert email.send_email(api_key="re_x", to="", subject="s", html="h", poster=poster) is False
    assert poster.calls == []                                         # nothing sent


def test_build_run_email_done_and_failed():
    done_subject, done_html = email.build_run_email(
        {"state": "done", "added": 4, "completed": 5, "reused": 1, "failed": 0}, base_url="https://app.example")
    assert "complete" in done_subject and "4 companies" in done_subject
    assert "https://app.example/research" in done_html

    fail_subject, fail_html = email.build_run_email({"state": "failed", "error": "RateLimitError: <boom>"})
    assert fail_subject == "Research run failed"
    assert "RateLimitError: &lt;boom&gt;" in fail_html                # error HTML-escaped


def test_send_run_notification_only_for_terminal_states():
    poster = _Poster(200)
    assert email.send_run_notification({"state": "running"}, api_key="re_x", to="k@x.com", poster=poster) is False
    assert poster.calls == []
    assert email.send_run_notification({"state": "done", "added": 1}, api_key="re_x", to="k@x.com",
                                       poster=poster) is True
    assert poster.calls[0]["payload"]["subject"].startswith("Research run complete")

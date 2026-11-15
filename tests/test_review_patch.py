"""`review_patch`: review a unified diff passed as text.

The caller hands over the diff; the tool reads no file, resolves no path and
writes no review memory, so it can review a change from any repository without
an allowlist entry. A diff over the size limit is refused rather than cut, so
a review never claims to cover lines it did not see.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import server  # noqa: E402

PATCH = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
 import os
+password = "hunter2"
 print(os.getcwd())
"""

REVIEW = "[RISK] app.py:2\nHard-coded credential.\n"


class _Client:
    def __init__(self, text: str) -> None:
        self.text = text
        self.messages: list[list[dict]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, *, model, messages, max_tokens):
        self.messages.append(messages)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.text))]
        )


def _use(monkeypatch, client: _Client) -> None:
    monkeypatch.setattr(server, "_review_client", lambda _openai: client)
    monkeypatch.setattr(server, "_review_requires_key", lambda: False)
    monkeypatch.setattr(server, "_review_model", lambda: "test-model")


def test_findings_come_back_structured(monkeypatch):
    client = _Client(REVIEW)
    _use(monkeypatch, client)

    result = server.review_patch(PATCH, mode="risk", label="mq-agent#455")

    assert result["ok"] is True
    assert result["mode"] == "risk"
    assert result["label"] == "mq-agent#455"
    assert result["model"] == "test-model"
    assert result["findings"] == [
        {"severity": "RISK", "location": "app.py:2", "body": "Hard-coded credential."}
    ]
    assert result["reviewed_bytes"] == len(PATCH.encode("utf-8"))


def test_the_model_sees_the_contract_and_the_whole_diff(monkeypatch):
    client = _Client(REVIEW)
    _use(monkeypatch, client)

    server.review_patch(PATCH, mode="risk")

    system, user = client.messages[0]
    assert "Review Contract" in system["content"]
    assert PATCH in user["content"]


def test_it_writes_no_review_memory(monkeypatch):
    _use(monkeypatch, _Client(REVIEW))
    saved: list = []
    import review_engine.review_memory as memory

    monkeypatch.setattr(memory.ReviewMemory, "save", lambda *a, **k: saved.append(a))
    server.review_patch(PATCH)

    assert saved == []


def test_an_oversized_patch_is_refused_not_truncated(monkeypatch):
    client = _Client(REVIEW)
    _use(monkeypatch, client)
    big = PATCH + "+" + "x" * server.REVIEW_PATCH_MAX_BYTES + "\n"

    result = server.review_patch(big)

    assert result["ok"] is False
    assert "too large" in result["error"]
    assert client.messages == []


def test_an_empty_patch_or_unknown_mode_is_refused(monkeypatch):
    client = _Client(REVIEW)
    _use(monkeypatch, client)

    assert server.review_patch("   ")["ok"] is False
    assert server.review_patch(PATCH, mode="no-such-mode")["ok"] is False
    assert client.messages == []


def test_no_findings_is_an_empty_list(monkeypatch):
    _use(monkeypatch, _Client("OK — no findings."))

    result = server.review_patch(PATCH)

    assert result["ok"] is True
    assert result["findings"] == []


def test_a_missing_key_is_reported(monkeypatch):
    client = _Client(REVIEW)
    monkeypatch.setattr(server, "_review_client", lambda _openai: client)
    monkeypatch.setattr(server, "_review_requires_key", lambda: True)
    monkeypatch.setattr(server._openai_credential, "openai_api_key", lambda: None)

    result = server.review_patch(PATCH)

    assert result["ok"] is False
    assert "OPENAI_API_KEY" in result["error"]
    assert client.messages == []


def test_a_model_failure_is_an_error_not_an_exception(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("connection refused")

    client = _Client(REVIEW)
    client.chat = SimpleNamespace(completions=SimpleNamespace(create=boom))
    _use(monkeypatch, client)

    result = server.review_patch(PATCH)

    assert result["ok"] is False
    assert "connection refused" in result["error"]

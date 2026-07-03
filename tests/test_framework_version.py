"""Framework-version resolution + drift guard.

The SOT doc is the human source of truth; `structured_evidence.FRAMEWORK_VERSION` is the SHIPPED copy the
pip-installed package stamps with. These tests fail if the two ever drift, and cover the repo-checkout
(read the doc) vs pip-installed (fall back to the constant) paths.
"""

from __future__ import annotations

import re

import pytest

from health_tech_research_agent import ledger
from health_tech_research_agent import structured_evidence as se


def test_shipped_constant_matches_the_sot_header():
    text = ledger._default_sot_path().read_text(encoding="utf-8")
    match = re.search(r"FRAMEWORK_VERSION:\s*(v\d+(?:\.\d+)*)", text)
    assert match, "SOT header carries no FRAMEWORK_VERSION"
    assert se.FRAMEWORK_VERSION == match.group(1), (
        f"FRAMEWORK_VERSION drift: code={se.FRAMEWORK_VERSION!r} SOT={match.group(1)!r} "
        "— bump structured_evidence.FRAMEWORK_VERSION in lockstep with the SOT")


def test_default_read_matches_constant_in_repo():
    assert ledger.read_framework_version() == se.FRAMEWORK_VERSION


def test_falls_back_to_constant_when_sot_not_packaged(tmp_path, monkeypatch):
    # Simulate a pip-installed layout where the SOT doc isn't shipped next to the package.
    monkeypatch.setattr(ledger, "_default_sot_path", lambda: tmp_path / "missing.md")
    assert ledger.read_framework_version() == se.FRAMEWORK_VERSION


def test_explicit_missing_sot_path_still_raises(tmp_path):
    with pytest.raises(ledger.LedgerError):
        ledger.read_framework_version(tmp_path / "nope.md")

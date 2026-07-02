"""Commit 1 — deterministic tests for the §B2 business-model classifier.

Built against SOT SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md §B2 (FRAMEWORK_VERSION v1.13) +
business_model_classifier_fixture.md (v1.3).

This suite proves the DETERMINISTIC half (the mapper + the two human-authoritative override
layers + needs_review + persistence) with NO LLM — the classifier read is an INPUT here, so the
worst-case read is testable directly. The full 6/8/40 fixture-count regression over real LLM
output is the live Colab run (it is a property of the model's reads over real evidence and cannot
be produced offline without fabricating reads).

The load-bearing local proof is the ADVERSARIAL floor test: the human-locked B2B floor exists
precisely because the classifier cannot reliably hold the 6, so it must force B2B EVEN WHEN the
read is consumer/consumer (the worst input). That property must not depend on the live run.
"""

import pytest

from health_tech_research_agent import structured_evidence as se
from health_tech_research_agent import research_runner as rr


# ---------------------------------------------------------------------------
# The §B2 mapper truth table (who_uses / who_pays -> label)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "who_uses, who_pays, expected",
    [
        ("professional", "consumer", "B2B"),      # professional floors to B2B regardless of who_pays
        ("professional", "institution", "B2B"),
        ("professional", "mixed", "B2B"),
        ("consumer", "consumer", "B2C"),
        ("consumer", "institution", "B2B2C"),
        ("consumer", "mixed", "B2B2C"),
        ("Professional", "Mixed", "B2B"),         # normalization (case / spacing) tolerated
        ("consumer", "unknown", ""),              # undeterminable who_pays -> "" (caller flags)
    ],
)
def test_mapper_truth_table(who_uses, who_pays, expected):
    assert se.map_business_model(who_uses, who_pays) == expected


# ---------------------------------------------------------------------------
# ADVERSARIAL floor test — the load-bearing local proof.
# Every floor company must resolve to B2B even when the classifier reads it CONSUMER/CONSUMER
# (the worst-case input the floor exists to catch). Correctness must NOT depend on the live LLM.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("company", sorted(se.LOCKED_B2B_FLOOR))
def test_floor_forces_b2b_under_adversarial_consumer_read(company):
    label, needs_review = se.business_model_for(
        company, who_uses="consumer", who_pays="consumer", who_uses_confidence="high"
    )
    assert label == "B2B", f"{company}: floor must force B2B even on a consumer read"
    assert needs_review is False  # a forced label needs no review


def test_floor_has_exactly_the_six():
    assert se.LOCKED_B2B_FLOOR == frozenset(
        {"openevidence", "cohere health", "zus health", "om1", "medically home", "linus health"}
    )


def test_floor_fires_through_persistence_layer():
    """The override must hold end-to-end: a floor company whose LLM block reads consumer still
    persists business_model == 'B2B', while the RAW read is preserved for audit."""
    parsed = {
        "company": "medically home",
        "business_model_classifier": {
            "who_uses": "consumer", "who_uses_basis": "misread",
            "who_pays": "consumer", "who_pays_basis": "misread",
            "who_uses_confidence": "high",
        },
    }
    cols = se.flatten_business_model_fields(parsed)
    assert cols["business_model"] == "B2B"          # floor wins
    assert cols["who_uses"] == "consumer"           # raw read preserved (auditable)
    assert cols["business_model_needs_review"] is False


# ---------------------------------------------------------------------------
# The 3 documented spike overrides — forced to their locked label from the mapper,
# independent of what a live read would say.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "company, expected",
    [("noom med", "B2C"), ("counsel health", "B2B2C")],  # signos RETIRED — now rides the mapper
)
def test_documented_overrides_force_locked_label(company, expected):
    # feed a read that DISAGREES with the locked label; the override must win.
    label, needs_review = se.business_model_for(
        company, who_uses="professional", who_pays="institution", who_uses_confidence="low"
    )
    assert label == expected
    assert needs_review is False  # forced -> no review


def test_signos_override_retired_rides_the_mapper():
    """signos was retired from the overrides (2026-06-30): the v1.13 prompt reads it correctly, and a
    redundant override would MASK a future prompt regression. signos now rides the mapper — its correct
    read maps to B2C, and (unlike a forced override) a WRONG read would change the label, keeping the
    prompt's correctness visible + testable."""
    assert "signos" not in se.DOCUMENTED_BUSINESS_MODEL_OVERRIDES
    label, _ = se.business_model_for("signos", "consumer", "consumer")  # the correct live read
    assert label == "B2C"  # reached via the mapper, not an override
    # not papered over: a (hypothetical) professional misread would now flip it — proof it rides the prompt
    assert se.business_model_for("signos", "professional", "institution")[0] == "B2B"


# ---------------------------------------------------------------------------
# needs_review — fires on a NON-forced low-confidence or undeterminable read only (flag, don't gate)
# ---------------------------------------------------------------------------

def test_needs_review_on_low_confidence_nonforced():
    _, needs_review = se.business_model_for(
        "some new co", "consumer", "institution", who_uses_confidence="low"
    )
    assert needs_review is True


def test_no_needs_review_on_high_confidence():
    _, needs_review = se.business_model_for(
        "some new co", "consumer", "institution", who_uses_confidence="high"
    )
    assert needs_review is False


def test_needs_review_on_undeterminable_who_pays():
    label, needs_review = se.business_model_for("some new co", "consumer", "unknown")
    assert label == ""
    assert needs_review is True


def test_low_confidence_does_not_flag_a_forced_company():
    # a floor company at low confidence still needs no review — the human already decided.
    _, needs_review = se.business_model_for(
        "openevidence", "consumer", "consumer", who_uses_confidence="low"
    )
    assert needs_review is False


# ---------------------------------------------------------------------------
# The 7 canonical asserts, at the who_uses/who_pays -> label level (fixture v1.3).
# Floor companies assert via the adversarial path (consumer read -> still B2B).
# ---------------------------------------------------------------------------

CANONICAL = [
    # company,           who_uses,       who_pays,        expected_label
    ("openevidence",     "consumer",     "consumer",      "B2B"),    # floor (was mislabeled B2B2C)
    ("medically home",   "consumer",     "consumer",      "B2B"),    # floor
    ("nourish",          "consumer",     "institution",   "B2B2C"),
    ("zoe",              "consumer",     "consumer",      "B2C"),
    ("headway",          "consumer",     "mixed",         "B2B2C"),
    ("rula health",      "consumer",     "institution",   "B2B2C"),
    ("grow therapy",     "consumer",     "institution",   "B2B2C"),
]


@pytest.mark.parametrize("company, who_uses, who_pays, expected", CANONICAL)
def test_canonical_asserts(company, who_uses, who_pays, expected):
    label, _ = se.business_model_for(company, who_uses, who_pays)
    assert label == expected


# ---------------------------------------------------------------------------
# Persistence (flatten_business_model_fields) — Rule-7 columns; raw read carried.
# ---------------------------------------------------------------------------

def test_flatten_persists_raw_read_and_derived_label():
    parsed = {
        "company": "zoe",
        "business_model_classifier": {
            "who_uses": "Consumer", "who_uses_basis": "member uses the ZOE app",
            "who_pays": "Consumer", "who_pays_basis": "consumer subscription",
            "who_uses_confidence": "high",
        },
    }
    cols = se.flatten_business_model_fields(parsed)
    assert cols == {
        "who_uses": "consumer",
        "who_uses_basis": "member uses the ZOE app",
        "who_pays": "consumer",
        "who_pays_basis": "consumer subscription",
        "who_uses_confidence": "high",
        "business_model": "B2C",
        "business_model_needs_review": False,
    }


def test_flatten_tolerates_missing_block():
    cols = se.flatten_business_model_fields({"company": "new co"})
    assert cols["business_model"] == ""            # nothing to map
    assert cols["business_model_needs_review"] is True
    assert cols["who_uses"] == ""


def test_flatten_company_arg_overrides_parsed_company():
    parsed = {"business_model_classifier": {"who_uses": "consumer", "who_pays": "consumer"}}
    cols = se.flatten_business_model_fields(parsed, company="signos")
    assert cols["business_model"] == "B2C"         # signos via the mapper now (override retired)


# ---------------------------------------------------------------------------
# The classifier PROMPT (pure builder) — asserted without an API key.
# ---------------------------------------------------------------------------

def test_prompt_builds_with_substitution_and_no_stray_braces():
    prompt = rr.build_business_model_prompt("ACME Health", "EVIDENCE BLOB")
    assert "Company: ACME Health" in prompt
    assert "EVIDENCE BLOB" in prompt
    # the emitted-JSON example must render single-braced after .format
    assert '{"who_uses"' in prompt
    assert "{{" not in prompt and "}}" not in prompt


def test_prompt_carries_the_signed_off_clauses():
    prompt = rr.build_business_model_prompt("X", "Y")
    for needle in ("FREQUENCY FIREWALL", "MATERIALITY BAR", "EVIDENCE-ONLY", "FREE-TO-CONSUMER"):
        assert needle in prompt
    # the LLM must NOT be asked to emit the label
    assert "You do NOT emit the label" in prompt

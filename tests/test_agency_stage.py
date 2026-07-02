"""Commit 3b/3c — deterministic tests for the §B4 stage discriminator (v1.10) + human-locked stage
override (v1.14) + AGENCY gate + the ipo-prep one-liner (v1.13).

Built against SOT §B4 (v1.10 / v1.13 / v1.14), logic-faithful to the spike. Fully deterministic — no LLM.
The named stage cases use the REAL round data the regen produced (so they assert against reality, not a
toy). The override cases assert the OVERRIDE produces series-b INDEPENDENT of the deterministic read
(the §B2-floor test shape) — proving the lock holds regardless of what the discriminator says.
"""

import pytest

from health_tech_research_agent import structured_evidence as se


# ---------------------------------------------------------------------------
# REAL round data (from v42_full_regen…_FINAL.csv, the data the spike scored)
# ---------------------------------------------------------------------------

SIGNOS = [
    {"type": "seed", "date": "2021-01", "amount": "$4 million", "is_priced_equity": True},
    {"type": "series-a", "date": "2021-11", "amount": "$13 million", "is_priced_equity": True},
    {"type": "extension", "date": "2022-01", "amount": "unknown", "is_priced_equity": False},
    {"type": "series-b", "date": "2023-10", "amount": "$20 million", "is_priced_equity": True},
    {"type": "series-c", "date": "2026-05", "amount": "$20 million", "is_priced_equity": True},
]
BICYCLE = [
    {"type": "seed", "date": "2020-05", "amount": "$5.3M", "is_priced_equity": True},
    {"type": "series-a", "date": "2021-05", "amount": "$27M", "is_priced_equity": True},
    {"type": "series-b", "date": "2022-06", "amount": "unknown", "is_priced_equity": True},
    {"type": "series-c", "date": "2025-01", "amount": "$16.5M", "is_priced_equity": True},
]
NINEAM = [
    {"type": "pre-seed", "date": "2021-03", "amount": "unknown", "is_priced_equity": "false"},
    {"type": "seed", "date": "2021-09", "amount": "$3.7M", "is_priced_equity": "true"},
    {"type": "series-a", "date": "2022-04", "amount": "$16M", "is_priced_equity": "true"},
    {"type": "extension", "date": "2024-02", "amount": "$9.5M", "is_priced_equity": "false"},
    {"type": "series-b", "date": "2026-05", "amount": "$26M", "is_priced_equity": "true"},
]
RULA = [
    {"type": "seed", "date": "unknown", "amount": "unknown", "is_priced_equity": "true"},
    {"type": "series-a", "date": "unknown", "amount": "unknown", "is_priced_equity": "true"},
    {"type": "series-b", "date": "unknown", "amount": "unknown", "is_priced_equity": "true"},
    {"type": "series-c", "date": "2024-07", "amount": "unknown", "is_priced_equity": "true"},
    {"type": "series-c", "date": "2026-02", "amount": "unknown", "is_priced_equity": "true"},
]
NO_IPO = {"occurred": False}


# ---------------------------------------------------------------------------
# 3b — the 4 named stage results (deterministic vs override, asserted individually)
# ---------------------------------------------------------------------------

def test_rula_series_c_deterministic_same_series_does_not_advance():
    # the 2nd same-series series-c round (2026) does NOT advance past series-c — no override needed.
    assert se.funding_stage_from_rounds(RULA, NO_IPO) == "series-c"
    assert se.resolve_funding_stage("rula health", RULA, NO_IPO) == "series-c"


def test_9amhealth_series_b_deterministic_no_override():
    # the discriminator gets 9amhealth right (series-b) — it needs NO override entry.
    assert se.funding_stage_from_rounds(NINEAM, NO_IPO) == "series-b"
    assert "9amhealth" not in se.DOCUMENTED_STAGE_OVERRIDES
    assert se.resolve_funding_stage("9amhealth", NINEAM, NO_IPO) == "series-b"


def test_signos_series_b_via_override_independent_of_read():
    # the deterministic read is series-c (the regen typed it so); the override forces series-b.
    assert se.funding_stage_from_rounds(SIGNOS, NO_IPO) == "series-c"        # what the data says
    assert se.resolve_funding_stage("signos", SIGNOS, NO_IPO) == "series-b"  # the lock wins


def test_bicycle_series_b_via_override_independent_of_read():
    assert se.funding_stage_from_rounds(BICYCLE, NO_IPO) == "series-c"
    assert se.resolve_funding_stage("bicycle health", BICYCLE, NO_IPO) == "series-b"


def test_stage_override_list_is_exactly_the_two():
    assert se.DOCUMENTED_STAGE_OVERRIDES == {"signos": "series-b", "bicycle health": "series-b"}


# ---------------------------------------------------------------------------
# 3b — the discriminator LOGIC itself (synthetic rounds)
# ---------------------------------------------------------------------------

def test_designated_advance_moves_the_series():
    rounds = [{"type": "series-b", "date": "2022", "is_priced_equity": True},
              {"type": "series-c", "date": "2023", "is_priced_equity": True}]
    assert se.funding_stage_from_rounds(rounds, NO_IPO) == "series-c"


def test_same_series_second_round_does_not_advance():
    rounds = [{"type": "series-c", "date": "2024", "is_priced_equity": True},
              {"type": "series-c", "date": "2026", "is_priced_equity": True}]
    assert se.funding_stage_from_rounds(rounds, NO_IPO) == "series-c"


def test_undesignated_later_round_sets_confidence_low():
    # a priced, dated round AFTER the last designated series whose type is NOT a canonical designation
    # -> keep the last confirmed series, but stage_confidence == "low" (Rule 8, flag don't guess).
    rounds = [{"type": "series-c", "date": "2022", "is_priced_equity": True},
              {"type": "venture round", "date": "2024", "is_priced_equity": True}]
    stage, conf = se.funding_stage_with_confidence(rounds, NO_IPO)
    assert stage == "series-c"
    assert conf == "low"


def test_clean_sequence_is_high_confidence():
    rounds = [{"type": "series-b", "date": "2022", "is_priced_equity": True},
              {"type": "series-c", "date": "2024", "is_priced_equity": True}]
    assert se.funding_stage_with_confidence(rounds, NO_IPO) == ("series-c", "high")


def test_explicit_series_designation_overrides_type():
    # the synthesis can emit an explicit designation: a round TYPED series-c but DESIGNATED series-b
    # (a same-series round) does NOT advance — this is the signal that, if present, would correct
    # signos/bicycle deterministically (it isn't in the regen data, hence the human-locked override).
    rounds = [{"type": "series-b", "date": "2022", "is_priced_equity": True},
              {"type": "series-c round", "series_designation": "series-b", "date": "2024", "is_priced_equity": True}]
    assert se.funding_stage_from_rounds(rounds, NO_IPO) == "series-b"


# ---------------------------------------------------------------------------
# 3c — AGENCY maturity buckets
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "stage, reset, expected_pass",
    [
        ("series-a", False, True),
        ("series-b", False, True),
        ("series-c", False, True),          # late-C clean PASS (the open dial)
        ("series-d-plus", False, False),    # late-stage FAILS without reset
        ("series-d-plus", True, True),      # reset rescues D+
        ("public", False, False),           # mature FAILS without reset
        ("public", True, True),             # reset rescues public
        ("seed", False, False),             # too-early FAILS
        ("seed", True, False),              # reset does NOT rescue too-early
        ("pre-seed", True, False),
        ("unknown", False, False),          # undeterminable -> FAIL (never a silent pass)
    ],
)
def test_agency_buckets(stage, reset, expected_pass):
    passed, _reason, _late_c = se.agency_gate(stage, reset)
    assert passed is expected_pass


def test_agency_late_c_flag_exposed():
    assert se.agency_gate("series-c", False)[2] is True
    assert se.agency_gate("series-b", False)[2] is False


def test_agency_ipo_status_public_takes_mature_path():
    # ipo_status == public routes through the mature branch even if stage says otherwise.
    passed, _r, _l = se.agency_gate("series-b", False, ipo_status="public")
    assert passed is False  # mature, no reset


# ---------------------------------------------------------------------------
# ipo-prep one-liner (v1.13 §B4): recognized + never-fire; oura clean exclude.
# ---------------------------------------------------------------------------

def test_ipo_prep_is_recognized_and_never_fires():
    assert "ipo-prep" in se.RESET_EVENT_TYPES        # recognized (won't trigger reset_needs_review)
    assert "ipo-prep" in se.RESET_NEVER_FIRE         # never-fire
    assert "ipo-prep" not in se.RESET_FIREABLE_TYPES  # auto-excluded from firing


def test_emitted_ipo_prep_does_not_fire_and_is_not_flagged():
    obj = {"reset_events": [{"event_type": "ipo-prep", "creates_high_agency_opening": "yes"}]}
    assert se.derive_reset_signal(obj) is False        # does NOT fire (oura S-1)
    assert se.reset_needs_review(obj) is False          # NOT review-flagged (recognized type)


def test_real_firing_type_still_fires_no_regression():
    obj = {"reset_events": [{"event_type": "leadership-change", "creates_high_agency_opening": "yes"}]}
    assert se.derive_reset_signal(obj) is True

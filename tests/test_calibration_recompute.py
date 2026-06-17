"""Regression tests for calibration-flag recompute on dashboard rebuild.

Reason 1 of the dashboard milestone: calibration flags were computed once from
the auto priority at research time and then carried forward verbatim, so a flag
went stale when a human review later changed the priority. The fix recomputes
flags from the FINAL (reviewed) priority during the rebuild, in memory, without
touching the master's stored historical flag.

The clearing test is the load-bearing guard: it fails when flags are computed
from the pre-fix auto priority and passes when computed from the final priority.
"""

import hashlib
from pathlib import Path

import pandas as pd

from health_tech_research_agent.priority import (
    build_calibration_flag,
    recompute_calibration_flags,
)


def _df(rows):
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1. Stale flag is cleared once the final/reviewed priority no longer triggers it.
# ---------------------------------------------------------------------------

def test_stale_flag_cleared_after_priority_change():
    # Auto priority was P2 with low evidence (stored flag), but a human review
    # promoted it to P0. The P2 calibration concern no longer applies.
    df = _df([
        {
            "company": "Promoted Co",
            "priority_level": "P2: Worth deeper diligence",
            "final_priority_level": "P0: Highest-priority target",
            "evidence_confidence_score": 40,
            "business_model_classification": "B2B2C payer-contracted",
            "calibration_flag": "CHECK: P2 with low evidence",
        }
    ])

    out = recompute_calibration_flags(df)

    assert out.iloc[0]["calibration_flag"] == ""


def test_prefix_source_keeps_flag_while_final_source_clears_it():
    # Permanent documentation of the bug: computing from the original auto
    # priority keeps the stale flag; computing from the final priority clears it.
    row = {
        "company": "Promoted Co",
        "priority_level": "P2: Worth deeper diligence",
        "final_priority_level": "P0: Highest-priority target",
        "evidence_confidence_score": 40,
        "business_model_classification": "B2B2C payer-contracted",
    }

    assert "CHECK: P2 with low evidence" in build_calibration_flag(
        row, priority_field="priority_level"
    )
    assert build_calibration_flag(row, priority_field="final_priority_level") == ""


# ---------------------------------------------------------------------------
# 2. A flag whose condition still holds is preserved.
# ---------------------------------------------------------------------------

def test_still_valid_flag_preserved():
    df = _df([
        {
            "company": "Still P2 Co",
            "priority_level": "P2: Worth deeper diligence",
            "final_priority_level": "P2: Worth deeper diligence",
            "evidence_confidence_score": 40,
            "business_model_classification": "B2B2C payer-contracted",
            "calibration_flag": "CHECK: P2 with low evidence",
        }
    ])

    out = recompute_calibration_flags(df)

    assert "CHECK: P2 with low evidence" in out.iloc[0]["calibration_flag"]


# ---------------------------------------------------------------------------
# 3. P-code keying: a near-priority P1 label is recognized as P1 (not under-promoted),
#    while a genuinely low-priority company with elite scores is flagged.
# ---------------------------------------------------------------------------

def test_pcode_keying_recognizes_near_priority_label():
    elite_scores = {
        "thesis_fit_score": 95,
        "pmf_scale_score": 85,
        "evidence_confidence_score": 75,
        "katelynd_role_fit_score": 85,
        "operator_timing_score": 80,
        "business_model_classification": "B2B2C payer-contracted",
    }

    # "P1: Near-priority target" must be treated as P1 -> no under-promotion flag.
    p1 = _df([{
        "company": "Near Priority Co",
        "priority_level": "P1: Near-priority target",
        "final_priority_level": "P1: Near-priority target",
        **elite_scores,
    }])
    assert "under-promotion" not in recompute_calibration_flags(p1).iloc[0]["calibration_flag"]

    # A P3 company with the same elite scores SHOULD be flagged as a possible
    # under-promotion (a previously dead check that now fires under P-code keying).
    p3 = _df([{
        "company": "Underrated Co",
        "priority_level": "P3: Watch list",
        "final_priority_level": "P3: Watch list",
        **elite_scores,
    }])
    assert "CHECK: possible P1 under-promotion" in recompute_calibration_flags(p3).iloc[0]["calibration_flag"]


# ---------------------------------------------------------------------------
# 4. The operator-timing sub-flag (not priority-driven) is preserved.
# ---------------------------------------------------------------------------

def test_operator_timing_subflag_preserved():
    # Priority-driven flags clear at P0, but the operator-timing sub-flag stays.
    cleared = _df([{
        "company": "Late Stage Co",
        "priority_level": "P0: Highest-priority target",
        "final_priority_level": "P0: Highest-priority target",
        "operator_timing_calibration_flag": "TIMING: company appears late-stage",
        "calibration_flag": "CHECK: P2 with low evidence | TIMING: company appears late-stage",
    }])
    assert recompute_calibration_flags(cleared).iloc[0]["calibration_flag"] == (
        "TIMING: company appears late-stage"
    )

    # When a priority-driven flag also applies, both are present.
    both = _df([{
        "company": "Still P2 Late Co",
        "priority_level": "P2: Worth deeper diligence",
        "final_priority_level": "P2: Worth deeper diligence",
        "evidence_confidence_score": 40,
        "operator_timing_calibration_flag": "TIMING: company appears late-stage",
    }])
    result = recompute_calibration_flags(both).iloc[0]["calibration_flag"]
    assert "CHECK: P2 with low evidence" in result
    assert "TIMING: company appears late-stage" in result


# ---------------------------------------------------------------------------
# 5. The recompute leaves the master file and stored flags byte-for-byte intact.
# ---------------------------------------------------------------------------

def test_master_file_and_stored_flags_unchanged_by_recompute(tmp_path):
    master_path = tmp_path / "health_tech_master.csv"
    _df([
        {
            "company": "Promoted Co",
            "priority_level": "P2: Worth deeper diligence",
            "final_priority_level": "P0: Highest-priority target",
            "evidence_confidence_score": 40,
            "business_model_classification": "B2B2C payer-contracted",
            "calibration_flag": "CHECK: P2 with low evidence",
        },
        {
            "company": "Still P2 Co",
            "priority_level": "P2: Worth deeper diligence",
            "final_priority_level": "P2: Worth deeper diligence",
            "evidence_confidence_score": 40,
            "business_model_classification": "B2B2C payer-contracted",
            "calibration_flag": "CHECK: P2 with low evidence",
        },
    ]).to_csv(master_path, index=False)

    digest_before = hashlib.sha256(master_path.read_bytes()).hexdigest()

    loaded = pd.read_csv(master_path)
    stored_flags_before = loaded["calibration_flag"].tolist()

    dashboard = recompute_calibration_flags(loaded)

    digest_after = hashlib.sha256(master_path.read_bytes()).hexdigest()

    # The master file on disk is byte-for-byte unchanged.
    assert digest_before == digest_after
    # The loaded master frame was not mutated; its stored flags are preserved.
    assert loaded["calibration_flag"].tolist() == stored_flags_before
    # The dashboard frame carries freshly recomputed flags.
    assert dashboard.iloc[0]["calibration_flag"] == ""  # promoted to P0 -> cleared
    assert "CHECK: P2 with low evidence" in dashboard.iloc[1]["calibration_flag"]  # still P2 -> kept


# ---------------------------------------------------------------------------
# 6. Empty input is handled safely.
# ---------------------------------------------------------------------------

def test_empty_dataframe_is_safe():
    out = recompute_calibration_flags(pd.DataFrame(columns=["company", "final_priority_level"]))
    assert "calibration_flag" in out.columns
    assert len(out) == 0

"""Tests for the targeted field-landing re-land (src/health_tech_research_agent/reland.py).

Red->green intent of each test (what it would catch on a regression):
1. normal row            -> wrong JSON key / no-transform / case-sensitive match.
2. blank-tag row         -> empty list crashing, or fabricating a value the source lacks.
3. already-populated      -> blank-only violated (engine/human value overwritten).
4. unmatched checkpoint   -> a row silently skipped instead of failing loud.
5. missing JSON key       -> fabricating around an absent key (Step-1 gate at runtime).
6. parse-to-blank         -> the weak "column exists" check; read-back must catch it + roll back.
7. file wrapper happy     -> end-to-end write/validate, non-target safety, idempotent re-run.
"""

import json

import pandas as pd
import pytest

import health_tech_research_agent.reland as reland
from health_tech_research_agent.reland import (
    TARGET_COLS,
    RelandError,
    reland_llm_clusters,
    reland_llm_clusters_df,
)


def _fbj(
    *,
    stage="ideal",
    agency="high",
    why="because the window is open",
    segment="METABOLIC_NUTRITION_HEALTH",
    subseg=("nutrition_care", "food_as_medicine"),
    product=("VIRTUAL_CARE",),
    distribution=("PAYER", "B2B2C"),
    data=("PATIENT_REPORTED",),
    rationale="rationale text",
    drop_rt_key=None,
    drop_block=None,
):
    """Build a fit_brief_json string with the real key shapes (tags as lists)."""
    role_timing = {
        "stage_timing_fit": stage,
        "likely_agency_level": agency,
        "why_now_or_why_not": why,
    }
    if drop_rt_key:
        role_timing.pop(drop_rt_key, None)
    taxonomy = {
        "primary_market_segment": segment,
        "subsegment_tags": list(subseg),
        "product_model_tags": list(product),
        "distribution_model_tags": list(distribution),
        "data_input_tags": list(data),
        "classification_rationale": rationale,
    }
    obj = {}
    if drop_block != "rt":
        obj["role_timing_assessment"] = role_timing
    if drop_block != "tx":
        obj["taxonomy_classification"] = taxonomy
    return json.dumps(obj)


def _blank_master(companies):
    return pd.DataFrame(
        {"company": list(companies), **{col: [""] * len(companies) for col in TARGET_COLS}}
    )


# 1 -------------------------------------------------------------------------
def test_normal_row_lands_all_ten_with_transforms():
    master = _blank_master(["Acme"])
    # case-insensitive match (acme vs Acme) is also exercised here.
    checkpoint = pd.DataFrame({"company": ["acme"], "fit_brief_json": [_fbj(subseg=["x", "y"])]})

    out, result = reland_llm_clusters_df(master, checkpoint)
    row = out.iloc[0]

    assert row["stage_timing_fit"] == "ideal"
    assert row["likely_agency_level"] == "high"
    assert row["why_now_or_why_not"] == "because the window is open"
    assert row["primary_market_segment"] == "METABOLIC_NUTRITION_HEALTH"  # raw code passthrough
    assert row["subsegment_tags"] == "x; y"                               # list joined
    assert row["product_model_tags"] == "VIRTUAL_CARE"
    assert row["distribution_model_tags"] == "PAYER; B2B2C"
    assert row["taxonomy_assignment_method"] == "llm_fit_brief"
    assert row["taxonomy_assignment_basis"] == "rationale text"
    assert result.matched_count == 1
    # _code is deferred to STEP 14, never written here.
    assert "primary_market_segment_code" not in TARGET_COLS
    assert "primary_market_segment_code" not in out.columns


# 2 -------------------------------------------------------------------------
def test_blank_tag_row_stays_blank_no_fabrication():
    master = _blank_master(["Acme"])
    checkpoint = pd.DataFrame({"company": ["Acme"], "fit_brief_json": [_fbj(subseg=[])]})

    out, result = reland_llm_clusters_df(master, checkpoint)

    assert out.iloc[0]["subsegment_tags"] == ""          # empty list -> blank, not fabricated
    assert out.iloc[0]["product_model_tags"] == "VIRTUAL_CARE"  # the others still land
    assert result.targets["subsegment_tags"] == 0        # target excludes the empty-list row
    assert result.fill_counts["subsegment_tags"] == 0    # so read-back==54 wouldn't false-fail


# 3 -------------------------------------------------------------------------
def test_already_populated_is_a_no_op():
    master = _blank_master(["Acme"])
    master.at[0, "stage_timing_fit"] = "too late"        # pre-existing (human/prior) value

    checkpoint = pd.DataFrame({"company": ["Acme"], "fit_brief_json": [_fbj(stage="ideal")]})
    out, result = reland_llm_clusters_df(master, checkpoint)

    assert out.iloc[0]["stage_timing_fit"] == "too late"  # preserved, not overwritten
    assert result.fill_counts["stage_timing_fit"] == 0    # blank-only -> no write
    assert out.iloc[0]["likely_agency_level"] == "high"   # the still-blank column fills


# 4 -------------------------------------------------------------------------
def test_unmatched_checkpoint_row_raises_and_writes_nothing():
    master = _blank_master(["Acme"])
    checkpoint = pd.DataFrame(
        {"company": ["Acme", "Ghost Co"], "fit_brief_json": [_fbj(), _fbj()]}
    )
    with pytest.raises(RelandError, match="no master counterpart"):
        reland_llm_clusters_df(master, checkpoint)


# 5 -------------------------------------------------------------------------
def test_missing_json_key_or_block_raises():
    master = _blank_master(["Acme"])

    missing_key = pd.DataFrame(
        {"company": ["Acme"], "fit_brief_json": [_fbj(drop_rt_key="stage_timing_fit")]}
    )
    with pytest.raises(RelandError, match="missing key 'stage_timing_fit'"):
        reland_llm_clusters_df(master, missing_key)

    missing_block = pd.DataFrame(
        {"company": ["Acme"], "fit_brief_json": [_fbj(drop_block="tx")]}
    )
    with pytest.raises(RelandError, match="taxonomy_classification missing"):
        reland_llm_clusters_df(master, missing_block)


# 6 -------------------------------------------------------------------------
def test_parse_to_blank_readback_raises_and_rolls_back(tmp_path, monkeypatch):
    master_path = tmp_path / "master.csv"
    checkpoint_path = tmp_path / "checkpoint.csv"
    master = _blank_master(["Acme"])
    master["operator_timing_score"] = ["80"]  # a non-target column to prove rollback safety
    master.to_csv(master_path, index=False)
    pd.DataFrame({"company": ["Acme"], "fit_brief_json": [_fbj()]}).to_csv(
        checkpoint_path, index=False
    )
    original_bytes = master_path.read_bytes()

    # Simulate a parse-to-blank bug: the fill drops stage_timing_fit, but the
    # independent target (from the source) still expects it -> read-back shortfall.
    real_landed_values = reland._landed_values

    def buggy_landed_values(role_timing, taxonomy):
        values = real_landed_values(role_timing, taxonomy)
        values["stage_timing_fit"] = ""
        return values

    monkeypatch.setattr(reland, "_landed_values", buggy_landed_values)

    with pytest.raises(RelandError, match="read-back below checkpoint target"):
        reland_llm_clusters(master_path, checkpoint_path, dry_run=False)

    assert master_path.read_bytes() == original_bytes  # rolled back, master untouched


# 7 -------------------------------------------------------------------------
def test_file_wrapper_writes_validates_and_is_idempotent(tmp_path):
    master_path = tmp_path / "master.csv"
    checkpoint_path = tmp_path / "checkpoint.csv"
    master = _blank_master(["Acme", "Bravo"])
    master["operator_timing_score"] = ["80", "60"]  # non-target column, must survive
    master.to_csv(master_path, index=False)
    # one normal row + one empty-subsegment row (the 54-vs-55 case in miniature).
    pd.DataFrame(
        {
            "company": ["acme", "BRAVO"],  # case drift both ways
            "fit_brief_json": [_fbj(subseg=["x"]), _fbj(subseg=[])],
        }
    ).to_csv(checkpoint_path, index=False)

    result = reland_llm_clusters(master_path, checkpoint_path, dry_run=False)
    assert result.readback_counts["stage_timing_fit"] == 2
    assert result.readback_counts["subsegment_tags"] == 1  # the empty-list row stays blank

    after = pd.read_csv(master_path, dtype=str, keep_default_na=False)
    assert list(after["operator_timing_score"]) == ["80", "60"]   # non-target untouched
    assert "primary_market_segment_code" not in after.columns      # _code deferred

    # Re-run is a no-op (idempotent): nothing left blank to fill.
    result2 = reland_llm_clusters(master_path, checkpoint_path, dry_run=False)
    assert sum(result2.fill_counts.values()) == 0

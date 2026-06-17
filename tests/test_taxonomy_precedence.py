"""Regression tests for taxonomy-label precedence in classify_dataframe.

These lock CLAUDE.md architecture rule 6: human taxonomy overrides ALWAYS take
precedence over model-generated values. The required precedence order is:

    1. company override  ->  2. model/LLM value  ->  3. keyword fallback  ->  4. unresolved

The conflict tests (a company that has BOTH a human override AND a conflicting
model value) are the load-bearing guard against reintroducing model-first
ordering. They fail against the old LLM-first classifier and pass against the
merged override-first one.
"""

from pathlib import Path

import pandas as pd
import pytest

from health_tech_research_agent import taxonomy
from health_tech_research_agent.taxonomy import classify_dataframe

REPO_TAXONOMY = Path(__file__).resolve().parents[1] / "taxonomy"


def _classify_one(*, taxonomy_dir=REPO_TAXONOMY, hard_stop=True, **row):
    base = {
        "company": "",
        "primary_market_segment_code": "",
        "primary_market_segment": "",
        "market_segment": "",
        "final_takeaway": "",
    }
    base.update(row)
    out = classify_dataframe(pd.DataFrame([base]), taxonomy_dir=taxonomy_dir, hard_stop=hard_stop)
    return out.iloc[0]


# ---------------------------------------------------------------------------
# 1. Human override beats a conflicting model value (the core guard).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "company, conflicting_model_code, expected_override_code",
    [
        ("Function Health", "DIAGNOSTICS_LIFE_SCIENCES", "CONSUMER_HEALTH_OPTIMIZATION"),
        ("InsideTracker", "DIAGNOSTICS_LIFE_SCIENCES", "CONSUMER_HEALTH_OPTIMIZATION"),
        ("Neko Health", "DIAGNOSTICS_LIFE_SCIENCES", "CONSUMER_HEALTH_OPTIMIZATION"),
        ("Levels Health", "CONSUMER_HEALTH_OPTIMIZATION", "METABOLIC_NUTRITION_HEALTH"),
    ],
)
def test_human_override_beats_conflicting_model_value(
    company, conflicting_model_code, expected_override_code
):
    # The row carries a model-assigned segment that disagrees with the human
    # override. The human override must win.
    result = _classify_one(
        company=company,
        primary_market_segment=conflicting_model_code,
    )

    assert result["primary_market_segment_code"] == expected_override_code
    assert result["taxonomy_assignment_method"] == "company_override"


def test_override_wins_does_not_surface_model_rationale():
    # When the override wins, the displayed basis/rationale must reflect the
    # human override, not the model's justification for a segment we discarded.
    model_rationale = "Model classified as diagnostics because it uses lab panels."
    result = _classify_one(
        company="Function Health",
        primary_market_segment="DIAGNOSTICS_LIFE_SCIENCES",
        taxonomy_rationale=model_rationale,
    )

    assert result["taxonomy_assignment_method"] == "company_override"
    assert taxonomy.safe_text(result["taxonomy_assignment_basis"]) != ""
    assert model_rationale not in taxonomy.safe_text(result["taxonomy_rationale"])


# ---------------------------------------------------------------------------
# 2. Model value is used only when there is no usable override.
# ---------------------------------------------------------------------------

def test_model_value_used_when_no_override():
    result = _classify_one(
        company="Zzz Novel Health Co",  # not in the override table
        primary_market_segment="MENTAL_BEHAVIORAL_HEALTH",
    )

    assert result["primary_market_segment_code"] == "MENTAL_BEHAVIORAL_HEALTH"
    assert result["taxonomy_assignment_method"] == "llm_validated"


def test_override_with_blank_segment_falls_through_to_model(tmp_path):
    # An override row whose segment is blank/invalid must not block or null the
    # model value; classification falls through to the model.
    (tmp_path / "market_segments.csv").write_text(
        "segment_code,segment_label\n"
        "SEG_ALPHA,Alpha Segment\n"
        "SEG_BETA,Beta Segment\n"
        "OTHER_REVIEW,Other / needs review\n"
    )
    (tmp_path / "company_taxonomy_overrides.csv").write_text(
        "company,primary_market_segment,override_reason\n"
        "Blankco,,Intentionally blank override segment\n"
    )

    result = _classify_one(
        taxonomy_dir=tmp_path,
        company="Blankco",
        primary_market_segment="SEG_BETA",
    )

    assert result["primary_market_segment_code"] == "SEG_BETA"
    assert result["taxonomy_assignment_method"] == "llm_validated"


# ---------------------------------------------------------------------------
# 3. Keyword fallback is the last resort.
# ---------------------------------------------------------------------------

def test_keyword_fallback_when_no_override_and_no_model():
    result = _classify_one(
        company="Zzz Keyword Co",  # not in the override table
        final_takeaway="A metabolic and diabetes care company.",
    )

    assert result["primary_market_segment_code"] == "METABOLIC_NUTRITION_HEALTH"
    assert result["taxonomy_assignment_method"].startswith("keyword_fallback")


# ---------------------------------------------------------------------------
# 4. Unresolved -> OTHER_REVIEW, and hard_stop raises.
# ---------------------------------------------------------------------------

def test_unresolved_maps_to_other_review_without_hard_stop():
    result = _classify_one(
        company="Zzqq Holdings",  # not in overrides, no model, no keyword text
        hard_stop=False,
    )

    assert result["primary_market_segment_code"] == "OTHER_REVIEW"
    assert result["taxonomy_assignment_method"] == "unmapped_review"


def test_unresolved_raises_under_hard_stop():
    with pytest.raises(RuntimeError):
        _classify_one(company="Zzqq Holdings", hard_stop=True)


# ---------------------------------------------------------------------------
# 5. The merge kept the newer features and left exactly one definition.
# ---------------------------------------------------------------------------

def test_newer_feature_columns_present_and_object_typed():
    out = classify_dataframe(
        pd.DataFrame([{"company": "Function Health"}]),
        taxonomy_dir=REPO_TAXONOMY,
    )
    for col in [
        "taxonomy_confidence",
        "taxonomy_rationale",
        "taxonomy_needs_review",
        "taxonomy_review_reason",
    ]:
        assert col in out.columns
        assert out[col].dtype == object


def test_exactly_one_classify_dataframe_definition():
    source = Path(taxonomy.__file__).read_text()
    assert source.count("def classify_dataframe(") == 1

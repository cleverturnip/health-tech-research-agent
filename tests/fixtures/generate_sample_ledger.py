"""Generate tests/fixtures/sample_ledger.jsonl — a SYNTHETIC, representative sample of the GATE-2 ledger
(MASTER_REDESIGN_SPEC §3.4) so any reader (e.g. the dashboard build) can see the EXACT entry shape in
practice without the live/private ledger. Built through the real `ledger.build_entry` / `apply_decisions`,
so it is guaranteed to match production. Regenerate: `PYTHONPATH=src python3 tests/fixtures/generate_sample_ledger.py`.

The five entries cover every tricky case:
  1. clean P0 (consumer, fully scored, no override)
  2. low-score floor with a HUMAN OVERRIDE applied (decision block + history + provenance)
  3. B2B floor (bg + FINAL = n/a — the floored-vs-low legibility case)
  4. late-stage company that passed AGENCY via a RESET, then human-overridden DOWN
  5. low-score floor, no override
"""

from __future__ import annotations

import json
from pathlib import Path

from health_tech_research_agent import ledger


def _rec(**over):
    base = dict(business_model="B2C", funding_stage="series-b", background_fit=8, pmf=9, arr_level=10,
                growth=9, strain=2, final_score=19, path_passed=True, agency_passed=True, gate_floored=False,
                floor_ok=True, model_priority="P0", human_override=None, floored_on_bg=False, tier_review=False,
                floor_reason="", data_feedback_loop="yes", background_fit_basis="daily habit loop",
                growth_note="high(+120% YoY, single-source)", growth_evidence="+120% YoY",
                strain_strength="STRONG", strain_rationale="a2=72", path_detail="B2C consumer end-user; engine alive",
                agency_detail="series-b -> PASS", reset_detail="reset events [none]; none fired",
                revenue_or_arr="$80M ARR")
    base.update(over)
    return base


def _row(rounds_date="2024-06", series="series-b", amount="50",
         segment="METABOLIC_NUTRITION_HEALTH", subsegs=("diabetes",), products=("virtual_care",)):
    fb = {"maturity_evidence": {"funding_rounds": [
        {"series_designation": series, "type": series, "date": rounds_date, "is_priced_equity": True,
         "amount_usd_m": amount}], "ipo_event": {}},
        "taxonomy_classification": {"primary_market_segment": segment, "subsegment_tags": list(subsegs),
                                    "product_model_tags": list(products), "distribution_model_tags": ["employer"],
                                    "data_input_tags": ["labs"], "classification_rationale": "sample classification"}}
    return {"fit_brief_json": json.dumps(fb)}


ROSTER = [
    (_rec(company="alpha health"), _row(segment="METABOLIC_NUTRITION_HEALTH")),   # 1. clean P0
    (_rec(company="beta health", background_fit=4, pmf=9, final_score=15,          # 2. low-score floor + override
          floor_ok=False, model_priority="P3", human_override="P1",
          floor_reason="floor-rule — bg_fit=4 / pmf=9", background_fit_basis="2x/yr lab cadence — episodic"),
     _row(rounds_date="2025-11", amount="298", segment="METABOLIC_NUTRITION_HEALTH", subsegs=("diagnostics",))),
    (_rec(company="gamma health", business_model="B2B", funding_stage="series-c",  # 3. B2B floor (n/a)
          background_fit=None, pmf=6, arr_level=7, growth=5, final_score=13, path_passed=False,
          agency_passed=False, gate_floored=True, floor_ok=False, model_priority="P3",
          floor_reason="PATH Test A: B2B floor — human-locked floor list", data_feedback_loop="",
          background_fit_basis="", agency_detail="n/a (floored earlier)"),
     _row(series="series-c", rounds_date="2023-01", amount="90", segment="SPECIALTY_CONDITION_CARE")),
    (_rec(company="delta health", business_model="B2B2C", funding_stage="series-d-plus",  # 4. agency pass via reset + override down
          background_fit=7, pmf=9, final_score=18, model_priority="P0", tier_review=True,
          agency_detail="series-d-plus late-stage +reset",
          reset_detail="reset events [leadership-change]; fired"),
     _row(series="series-d-plus", rounds_date="2026-03", amount="150", segment="MENTAL_BEHAVIORAL_HEALTH")),
    (_rec(company="epsilon health", business_model="B2B2C", background_fit=4, pmf=3, strain=0, final_score=7,
          floor_ok=False, model_priority="P3", floor_reason="floor-rule — bg_fit=4 / pmf=3",
          strain_strength="WEAK", strain_rationale="default-low", data_feedback_loop="no",
          background_fit_basis="episodic navigation, not a habit loop", growth=4, growth_note="unknown(no-signal)"),
     _row(amount="60", segment="WOMENS_FAMILY_HEALTH")),   # 5. low-score floor, no override
]


def main() -> None:
    entries = [ledger.build_entry(rec, row, batch_id="batch_sample_2026-07-03", date_scored="2026-07-03",
                                  framework_version="v1.25") for rec, row in ROSTER]
    # apply two GATE-2 decisions so the sample shows a populated decision block + history + provenance
    entries = ledger.apply_decisions(
        entries,
        [{"company": "beta health", "human_override": "P1", "override_reason": "strong revenue + growth; the low bg is the correct 2x/yr cadence"},
         {"company": "delta health", "human_override": "P3", "override_reason": "too late-stage without a clear high-agency entry"}],
        decided_date="2026-07-03", decided_at_gate="gate2_sample")

    out = Path(__file__).with_name("sample_ledger.jsonl")
    ledger.write_ledger(out, entries)
    print(f"wrote {len(entries)} entries -> {out}")


if __name__ == "__main__":
    main()

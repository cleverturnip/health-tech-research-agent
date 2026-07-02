"""Revenue retry-and-union LIVE validation harness (READ-ONLY, credit-spending).

Runs the revenue ``search_with_recovery`` config on the ground-truth companies and
prints, per company:
  * each of the N RAW pass findings, side by side -- so you can SEE pass
    INDEPENDENCE. If the passes come back near-identical, the inter-pass cadence is
    too tight and the execution variance the mechanism depends on is NOT working
    (even if the union happens to recover a figure that came from pass 1 alone);
  * the unioned finding fed to the synthesis;
  * the synthesis result (revenue_or_arr / q4 / evidence_confidence) vs the known
    ground truth, plus a Mode-B flag (union had a figure but synthesis dropped it).

This is the real proof of the mechanism (recovery + cadence) before the run-once
multi-field regen. It is the test of BOTH that retry-and-union recovers known
figures AND that the chosen ``wait_between_passes`` produces independent passes.

READ-ONLY: no master / checkpoint / Drive writes; output is printed only. NOT a
test and NOT part of the batch (pytest does not collect this module).

Costs API credits -> run ONLY on an explicit go. Check billing FIRST: a sustained
"rate limit" almost always means out of credits, not throttling.

Run manually:
    OPENAI_API_KEY=... python scripts/revenue_live_validation.py
Tune the cadence under test:
    python scripts/revenue_live_validation.py            # uses DEFAULT_WAIT_BETWEEN_PASSES
    # or import and call validate(wait_between_passes=60) to compare intervals
"""
from __future__ import annotations

import json

from health_tech_research_agent.research_runner import (
    DEFAULT_MODEL,
    DEFAULT_WAIT_BETWEEN_PASSES,
    REVENUE_RECOVERY_PASSES,
    _build_latest_status_findings,
    revenue_presence_check,
    revenue_source_directed_prompt,
    run_company_fit_brief,
    search_commercial_scale,
    search_with_recovery,
)
from health_tech_research_agent.review import parse_first_json_object

# Ground truth that PREDATES the June 2026 run (see audits/). For eyeballing recovery;
# the harness does not assert against it -- you read the output.
GROUND_TRUTH = [
    {
        "company": "Midi Health",
        "research_query": (
            "Midi Health (joinmidi.com), virtual menopause / perimenopause care, "
            "founded by Joanna Strober, HQ Menlo Park CA"
        ),
        "expect": (
            "BLINKS (was 2/5 single-pass). $115.9M (Latka) / $150M run-rate (CB Insights). "
            "Expect recovery, and possibly BOTH figures unioned (corroboration)."
        ),
    },
    {
        "company": "Solace Health",
        "research_query": (
            "Solace Health (solace.health), patient-advocacy marketplace, "
            "founded by Jeremy Gurewitz"
        ),
        "expect": "STABLE (was 5/5). ~$10M run-rate (CB Insights). Expect recovered, single-source.",
    },
    {
        "company": "Pelago",
        "research_query": (
            "Pelago (pelago.health, formerly Quit Genius), digital substance-use clinic"
        ),
        "expect": (
            "GENUINE ABSENCE (0/5). No revenue $ exists; growth 287%. "
            "Expect revenue_or_arr EMPTY (correct, not a failure); growth present in the text."
        ),
    },
    {
        "company": "ZOE",
        "research_query": (
            "ZOE (zoe.com), personalized nutrition, founded by Tim Spector and Jonathan Wolf"
        ),
        "expect": (
            "NON-AGGREGATOR path. ~$80M ARR / 88k paying disclosed via Crowdcube (predates run). "
            "Expect recovery via the Gate-2 non-aggregator clause (Crowdcube, not an aggregator)."
        ),
    },
]


def _build_client():
    """Construct the real OpenAI client at runtime (NOT at import), like Colab does."""
    from openai import OpenAI

    return OpenAI()


def _commercial_only_findings(commercial_union: str) -> str:
    """Assemble the 6-section synthesis input with only the commercial union populated.

    The other five searches are intentionally NOT run (this is a REVENUE validation,
    cost-bounded). Their absence may depress evidence_confidence somewhat, so compare
    confidence RELATIVELY across companies (Midi multi-source vs Solace single-source).
    """
    placeholder = "Not researched in this revenue-validation harness."
    return _build_latest_status_findings(
        placeholder, placeholder, placeholder, commercial_union, placeholder, placeholder
    )


def validate(
    *,
    model: str = DEFAULT_MODEL,
    n_passes: int = REVENUE_RECOVERY_PASSES,
    wait_between_passes: float = DEFAULT_WAIT_BETWEEN_PASSES,
    taxonomy_dir=None,
):
    """Run the read-only validation. Prints per-pass + union + synthesis per company."""
    client = _build_client()
    print(
        f"REVENUE LIVE VALIDATION — model={model} n_passes={n_passes} "
        f"wait_between_passes={wait_between_passes}s (READ-ONLY; no writes)"
    )

    for case in GROUND_TRUTH:
        company = case["company"]
        print("\n" + "=" * 90)
        print(f"COMPANY: {company}")
        print(f"EXPECT:  {case['expect']}")
        print("=" * 90)

        union, prov = search_with_recovery(
            search_commercial_scale,
            case["research_query"],
            client=client,
            model=model,
            retry_prompt_builder=revenue_source_directed_prompt,
            presence_check=revenue_presence_check,
            field_name="revenue",
            n_passes=n_passes,
            wait_between_passes=wait_between_passes,
        )

        # PASS-LEVEL: raw findings side by side -> SEE independence (do not infer it).
        for i, raw in enumerate(prov.passes, start=1):
            kind = "general" if i == 1 else "source-directed"
            print(f"\n----- PASS {i} ({kind}) RAW -----\n{raw}")

        print(f"\n----- PROVENANCE ----- n_passes={prov.n_passes} figure_present={prov.figure_present}")
        print(f"\n----- UNION (fed to synthesis) -----\n{union}")

        fit = run_company_fit_brief(
            company,
            _commercial_only_findings(union),
            client=client,
            model=model,
            taxonomy_dir=taxonomy_dir,
        )
        try:
            data = parse_first_json_object(fit)
        except Exception as exc:  # noqa: BLE001 - diagnostic only
            print(f"\n----- SYNTHESIS did not parse: {type(exc).__name__}: {exc} -----")
            continue

        ce = data.get("commercial_evidence", {}) or {}
        revenue = ce.get("revenue_or_arr")
        print("\n----- SYNTHESIS (key fields) -----")
        print(f"revenue_or_arr:      {revenue!r}")
        print(f"q4_evidence_quality: {ce.get('q4_evidence_quality')!r}")
        if prov.figure_present and not str(revenue or "").strip():
            print("** MODE-B: union had a figure but synthesis left revenue_or_arr EMPTY — investigate **")
        print("\n----- FULL SYNTHESIS JSON (incl. evidence_confidence_score) -----")
        print(json.dumps(data, indent=2))


if __name__ == "__main__":  # pragma: no cover - manual, credit-spending
    validate()

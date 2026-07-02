"""Group 1 targeted re-measure (READ-ONLY, credit-spending) — real per-field N for growth-rate +
paying-count, replacing the probe's under-measurement artifacts.

For each field, run its OWN source-directed config via search_with_recovery (N=5), then score EACH of
the 5 passes with the field's presence check -> per-pass hit rate p -> real N (1-(1-p)^N >= 0.9).
Also reports:
  * the PELAGO paying-count check (Tightening 2): raw passes printed so we can SEE that "100+ paying
    employer clients" is kept DISTINCT from "3.4M eligible lives" (non-paying);
  * the AGGREGATOR-REDUNDANCY observation: how often each field's passes cite the same aggregator
    domains -- data for a possible future "one search, several fields" consolidation (NOT a change now).

READ-ONLY: no master/checkpoint/Drive writes; per-(field,company) SCRATCH checkpoint for
disconnect-resume. Credit-spending -> run only on explicit go; check billing (sustained "rate limit"
= out of credits). Not a test; pytest does not collect it; client built at runtime.

Run:  OPENAI_API_KEY=... python scripts/group1_remeasure.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from health_tech_research_agent.research_runner import (
    DEFAULT_MODEL,
    DEFAULT_WAIT_BETWEEN_PASSES,
    REVENUE_RECOVERY_PASSES,
    growth_rate_presence_check,
    growth_rate_source_directed_prompt,
    paying_count_presence_check,
    paying_count_source_directed_prompt,
    search_commercial_scale,
    search_with_recovery,
)

WAIT = DEFAULT_WAIT_BETWEEN_PASSES  # 45s
N = REVENUE_RECOVERY_PASSES  # 5 (kept; the re-measure gives the sample to set permanent per-field N)
SCRATCH = Path("group1_remeasure_scratch.json")
AGG = ["getlatka.com", "growjo.com", "cbinsights.com", "pitchbook.com", "sacra.com"]

QUERIES = {
    "Midi Health": "Midi Health (joinmidi.com), virtual menopause/perimenopause care, founded by Joanna Strober",
    "Solace Health": "Solace Health (solace.health), patient-advocacy marketplace, founded by Jeremy Gurewitz",
    "Pelago": "Pelago (pelago.health, formerly Quit Genius), digital substance-use clinic",
    "ZOE": "ZOE (zoe.com), personalized nutrition, founded by Tim Spector and Jonathan Wolf",
    "Function Health": "Function Health (functionhealth.com), comprehensive lab-testing membership",
    "Omada Health": "Omada Health (omadahealth.com), virtual cardiometabolic care via employers and health plans",
}
# Targeted samples (Solace = growth 20% stress case; Pelago = the paying employer-vs-eligible-lives check).
FIELDS = {
    "growth_rate": {
        "companies": ["Midi Health", "Solace Health", "Pelago", "ZOE"],
        "prompt": growth_rate_source_directed_prompt,
        "presence": growth_rate_presence_check,
    },
    "paying_count": {
        "companies": ["ZOE", "Function Health", "Omada Health", "Pelago"],
        "prompt": paying_count_source_directed_prompt,
        "presence": paying_count_presence_check,
    },
}


def _build_client():
    from openai import OpenAI

    return OpenAI()


def _suggest_n(p, target=0.9):
    if p is None or p <= 0:
        return None
    if p >= 1:
        return 1
    return max(1, math.ceil(math.log(1 - target) / math.log(1 - p)))


def remeasure_one(field, company, cfg, *, client, model):
    _union, prov = search_with_recovery(
        search_commercial_scale, QUERIES[company], client=client, model=model,
        retry_prompt_builder=cfg["prompt"], presence_check=cfg["presence"],
        field_name=field, n_passes=N, wait_between_passes=WAIT,
    )
    # score EACH pass with the field's presence check -> per-pass hit rate
    per_pass = [bool(cfg["presence"](p, client=client, model=model)) for p in prov.passes]
    agg_hits = {a: sum(1 for p in prov.passes if a in str(p).lower()) for a in AGG}
    return {"field": field, "company": company, "per_pass": per_pass,
            "passes": prov.passes, "agg_hits": agg_hits}


def run():
    client = _build_client()
    done = {}
    if SCRATCH.exists():
        done = {(r["field"], r["company"]): r for r in json.loads(SCRATCH.read_text())}
        print(f"Resuming — {len(done)} (field, company) pairs already done.")
    results = list(done.values())
    for field, cfg in FIELDS.items():
        for company in cfg["companies"]:
            if (field, company) in done:
                continue
            print(f"\n>>> {field} / {company} ...")
            results.append(remeasure_one(field, company, cfg, client=client, model=DEFAULT_MODEL))
            SCRATCH.write_text(json.dumps(results, indent=2))
            print(f"    per-pass: {['T' if x else 'F' for x in results[-1]['per_pass']]}")
    report(results)


def report(results):
    by = {}
    for r in results:
        by.setdefault(r["field"], []).append(r)

    print("\n" + "#" * 84 + "\nGROUP 1 RE-MEASURE — real per-field N (replaces the probe artifacts)\n" + "#" * 84)
    for field, rows in by.items():
        print(f"\n=== {field} ===")
        worst = 1.0
        for r in rows:
            hits = sum(1 for x in r["per_pass"] if x)
            rate = hits / len(r["per_pass"]) if r["per_pass"] else 0.0
            worst = min(worst, rate)
            print(f"  {r['company']:<16} {['T' if x else 'F' for x in r['per_pass']]}  ({hits}/{len(r['per_pass'])} = {rate:.0%})")
        print(f"  -> worst-case single-pass p={worst:.0%}; suggested real N≈{_suggest_n(worst)} (for ~90% recovery)")

    print("\n" + "#" * 84 + "\nPELAGO paying-count check — PAYING employer clients vs NON-paying eligible lives (Tightening 2)\n" + "#" * 84)
    found = False
    for r in results:
        if r["field"] == "paying_count" and r["company"] == "Pelago":
            found = True
            for i, p in enumerate(r["passes"], 1):
                print(f"\n--- Pelago paying-count pass {i} ---\n{p}")
    if not found:
        print("  (Pelago paying-count not in results — check the run)")

    print("\n" + "#" * 84 + "\nAGGREGATOR REDUNDANCY — citations per field (sizing a future 'one search, several fields')\n" + "#" * 84)
    for field, rows in by.items():
        tot = {a: sum(r["agg_hits"].get(a, 0) for r in rows) for a in AGG}
        print(f"  {field:<14} " + "  ".join(f"{a.split('.')[0]}:{tot[a]}" for a in AGG))
    print("  (high overlap on the same domains across growth_rate + paying_count [+ revenue] => a "
          "consolidation could de-dupe the fetches; NOT a change now — just sizing the lever.)")


if __name__ == "__main__":  # pragma: no cover - manual, credit-spending
    run()

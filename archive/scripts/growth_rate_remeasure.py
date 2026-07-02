"""Growth-rate re-measure AFTER refine-to-derive (READ-ONLY, credit-spending).

Runs the REFINED growth_rate_source_directed_prompt + growth_rate_presence_check via
search_with_recovery (N=5) on the three companies that blinked pre-derive -- Midi, Solace, ZOE
(Pelago was already 5/5; not re-run here). Scores each of the 5 passes -> per-pass usable-rate hit
rate -> suggested ALWAYS-RUN-N (never stop-on-hit; sized to the post-derive rate, NOT a reflexive
11). PRINTS the raw passes so we can SEE the derive working -- rates COMPUTED from dated endpoints
with the inputs shown -- not just infer it from the hit rate.

Pre-derive baseline (for comparison): Midi 20%, Solace 40%, ZOE 40% -> worst-case N≈11.

READ-ONLY: no master/checkpoint/Drive writes; per-company SCRATCH checkpoint for disconnect-resume.
Credit-spending -> run only on the explicit go (given). Not a test; pytest does not collect it; the
OpenAI client is built at runtime.

Run:  OPENAI_API_KEY=... python scripts/growth_rate_remeasure.py
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
    search_commercial_scale,
    search_with_recovery,
)

WAIT = DEFAULT_WAIT_BETWEEN_PASSES  # 45s
N = REVENUE_RECOVERY_PASSES  # 5 passes measured; permanent N is sized from the measured hit rate
SCRATCH = Path("growth_rate_remeasure_scratch.json")

COMPANIES = [
    {"company": "Midi Health", "research_query": "Midi Health (joinmidi.com), virtual menopause/perimenopause care, founded by Joanna Strober"},
    {"company": "Solace Health", "research_query": "Solace Health (solace.health), patient-advocacy marketplace, founded by Jeremy Gurewitz"},
    {"company": "ZOE", "research_query": "ZOE (zoe.com), personalized nutrition, founded by Tim Spector and Jonathan Wolf"},
]


def _build_client():
    from openai import OpenAI

    return OpenAI()


def _suggest_n(p, target=0.9):
    if p is None or p <= 0:
        return None
    if p >= 1:
        return 1
    return max(1, math.ceil(math.log(1 - target) / math.log(1 - p)))


def remeasure(case, *, client, model):
    _union, prov = search_with_recovery(
        search_commercial_scale, case["research_query"], client=client, model=model,
        retry_prompt_builder=growth_rate_source_directed_prompt,
        presence_check=growth_rate_presence_check,
        field_name="growth_rate", n_passes=N, wait_between_passes=WAIT,
    )
    per_pass = [bool(growth_rate_presence_check(p, client=client, model=model)) for p in prov.passes]
    return {"company": case["company"], "per_pass": per_pass, "passes": prov.passes}


def run():
    client = _build_client()
    done = {}
    if SCRATCH.exists():
        done = {r["company"]: r for r in json.loads(SCRATCH.read_text())}
        print(f"Resuming — {len(done)} already done.")
    results = list(done.values())
    for case in COMPANIES:
        if case["company"] in done:
            continue
        print(f"\n>>> growth_rate / {case['company']} ...")
        results.append(remeasure(case, client=client, model=DEFAULT_MODEL))
        SCRATCH.write_text(json.dumps(results, indent=2))
        print(f"    per-pass: {['T' if x else 'F' for x in results[-1]['per_pass']]}")
    report([r for c in COMPANIES for r in results if r["company"] == c["company"]])


def report(results):
    print("\n" + "#" * 84 + "\nGROWTH-RATE RE-MEASURE (post refine-to-derive) — usable-rate hit per pass\n" + "#" * 84)
    worst = 1.0
    for r in results:
        hits = sum(1 for x in r["per_pass"] if x)
        rate = hits / len(r["per_pass"]) if r["per_pass"] else 0.0
        worst = min(worst, rate)
        print(f"  {r['company']:<16} {['T' if x else 'F' for x in r['per_pass']]}  ({hits}/{len(r['per_pass'])} = {rate:.0%})")
    print(f"\n  -> worst-case single-pass p={worst:.0%}; suggested ALWAYS-RUN N≈{_suggest_n(worst)} (for ~90% recovery)")
    print("     pre-derive baseline was Midi 20% / Solace 40% / ZOE 40% (worst N≈11) -- did derive lift it?")
    print("\n" + "#" * 84 + "\nRAW PASSES — verify derive is COMPUTING rates from dated endpoints (inputs shown)\n" + "#" * 84)
    for r in results:
        for i, p in enumerate(r["passes"], 1):
            print(f"\n----- {r['company']} pass {i} -----\n{p}")


if __name__ == "__main__":  # pragma: no cover - manual, credit-spending
    run()

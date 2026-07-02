"""Funding-stage / IPO-status VARIANCE check (2c) -- READ-ONLY, credit-spending.

*** NOT THE CANONICAL 2c -- REFERENCE LOGIC ONLY (do not run against the regen question as-is). ***
The CANONICAL 2c runs as a NOTEBOOK CELL that calls the PACKAGE path directly
(_research_runner.search_funding -- the same path run_research_batch / the regen uses), so it cannot
drift from the live path. This standalone harness duplicates that logic for offline reference only;
reconcile it to the package before trusting it. (Kept, not deleted, to keep the logic legible.)

The AGENCY gate (SOT B4, FRAMEWORK_VERSION v1.2) rests on funding_stage + ipo_status, whose run-to-run
VARIANCE was never measured -- and the SAME search (search_funding) also yields valuation, which the
all-fields probe showed blinks 0-100%. A static regen doc is ONE sample, so variance can only be
measured by repeating the search N times. This isolates the high-value cell: is the GATE input
(stage/ipo) STABLE across N even though the CONTEXT field (valuation) is noisy on the same search?

Sampling -- variance only matters where a blink could FLIP the AGENCY gate (A/B/C pass; D+/public fail):
  - Hinge Health, Omada Health -- IPO'd 2025: public-vs-late-private boundary (a stage/ipo blink flips
    the gate). Also shared-search valuation cases.
  - Sword Health -- late Series D, IPO-rumored: Series-C-vs-D boundary + shared-search valuation.
  - Transcarent -- Series C/D + the 2025 Accolade merger: stage/status ambiguity boundary.
  - Allara Health -- clear Series B: CONTROL (confirms stability on an easy case).

Per pass: run search_funding, then a NO-WEB extraction pulls (funding_stage, ipo_status, valuation).
Report per company: do stage/ipo stay STABLE across the N passes or BLINK -- side by side with valuation
stability. The no-web extraction is a tight enum parse over identical text, so its own variance is
minimal; the variance it reflects is the SEARCH's.

CHECK BILLING FIRST: a sustained "Rate limit hit ... Max retries reached" here almost always means
OUT OF CREDITS (insufficient_quota), NOT throttling -- check platform.openai.com billing + the monthly
auto-recharge cap before assuming rate limits.

READ-ONLY: no master/checkpoint/Drive writes; per-company SCRATCH checkpoint for disconnect-resume.
Credit-spending (~25 search_funding web calls + ~25 cheap no-web parses) -> run on the explicit go.
Not a test; pytest does not collect it; the OpenAI client is built at runtime.

Run:  OPENAI_API_KEY=... python scripts/funding_variance_check.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from health_tech_research_agent.research_runner import (
    DEFAULT_MODEL,
    call_openai,
    search_funding,
)

N = 5
SCRATCH = Path("funding_variance_scratch.json")

COMPANIES = [
    {"company": "Hinge Health",
     "research_query": "Hinge Health (hingehealth.com), digital MSK / physical-therapy care; IPO 2025",
     "boundary": "public vs late-private (IPO 2025) -- gate-flip + shared-search valuation"},
    {"company": "Omada Health",
     "research_query": "Omada Health (omadahealth.com), virtual chronic-condition care; IPO 2025",
     "boundary": "public vs late-private (IPO 2025) -- gate-flip"},
    {"company": "Sword Health",
     "research_query": "Sword Health (swordhealth.com), digital MSK care; late-stage, IPO-rumored",
     "boundary": "Series C vs D -- gate-flip + shared-search valuation"},
    {"company": "Transcarent",
     "research_query": "Transcarent (transcarent.com), health navigation platform; 2025 Accolade merger",
     "boundary": "Series C/D + 2025 Accolade merger -- stage/status ambiguity"},
    {"company": "Allara Health",
     "research_query": "Allara Health (allarahealth.com), virtual PCOS / women's hormonal-health care",
     "boundary": "clear Series B -- CONTROL"},
]

EXTRACT_PROMPT = """From the funding fact-list below, output ONE JSON object and nothing else:
{{"funding_stage": one of "pre-seed","seed","series-a","series-b","series-c","series-d-plus","public","unknown";
  "ipo_status": one of "private","public","filed-s1","unknown";
  "valuation": the latest STATED valuation as a short string (e.g. "$6.2B"), or "none"}}
Use ONLY what the fact-list states; do not guess or use outside knowledge.

Fact-list:
{finding}
"""


def _build_client():
    from openai import OpenAI

    return OpenAI()


def _extract(finding, *, client, model):
    out = call_openai(
        EXTRACT_PROMPT.format(finding=finding), client=client, model=model,
        use_web_search=False, max_output_tokens=120,
    )
    try:
        s = out[out.find("{"):]
        d = json.loads(s[: s.rfind("}") + 1])
        return {k: str(d.get(k, "?")) for k in ("funding_stage", "ipo_status", "valuation")}
    except Exception:
        return {"funding_stage": "PARSE_FAIL", "ipo_status": "PARSE_FAIL", "valuation": "PARSE_FAIL"}


def measure(case, *, client, model):
    passes = []
    for _ in range(N):
        finding = search_funding(case["research_query"], client=client, model=model)
        passes.append({"finding": finding, **_extract(finding, client=client, model=model)})
    return {"company": case["company"], "boundary": case["boundary"], "passes": passes}


def run():
    client = _build_client()
    done = {}
    if SCRATCH.exists():
        done = {r["company"]: r for r in json.loads(SCRATCH.read_text())}
        print(f"Resuming -- {len(done)} already done.")
    results = list(done.values())
    for case in COMPANIES:
        if case["company"] in done:
            continue
        print(f"\n>>> funding variance / {case['company']} ...")
        results.append(measure(case, client=client, model=DEFAULT_MODEL))
        SCRATCH.write_text(json.dumps(results, indent=2))
    report([r for c in COMPANIES for r in results if r["company"] == c["company"]])


def _stab(vals):
    c = Counter(vals)
    return ("STABLE" if len(c) == 1 else f"BLINK({len(c)})"), dict(c)


def report(results):
    print("\n" + "#" * 92)
    print("FUNDING-STAGE / IPO VARIANCE (2c) -- gate input (stage/ipo) stability vs valuation blink")
    print("#" * 92)
    for r in results:
        s_v, s_c = _stab([p["funding_stage"] for p in r["passes"]])
        i_v, i_c = _stab([p["ipo_status"] for p in r["passes"]])
        v_v, v_c = _stab([p["valuation"] for p in r["passes"]])
        print(f"\n  {r['company']}  [{r['boundary']}]")
        print(f"    funding_stage: {s_v:<9} {s_c}")
        print(f"    ipo_status:    {i_v:<9} {i_c}")
        print(f"    valuation:     {v_v:<9} {v_c}   <- GATE input vs noisy context field, same search")
    print("\n" + "#" * 92 + "\nRAW funding fact-lists (verify the extraction)\n" + "#" * 92)
    for r in results:
        for i, p in enumerate(r["passes"], 1):
            print(f"\n----- {r['company']} pass {i}: stage={p['funding_stage']} ipo={p['ipo_status']} val={p['valuation']} -----")
            print(p["finding"][:400])


if __name__ == "__main__":  # pragma: no cover - manual, credit-spending
    run()

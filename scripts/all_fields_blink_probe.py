"""All-fields blink probe (READ-ONLY, credit-spending) — per-field blink-rate map + B1/B2 live-validation.

Measures single-pass presence variance per field across N=5 samples, to scope which fields
(beyond revenue) need retry-and-union, and folds in B1 (Pelago per-pass hit rate, via the real
source-directed mechanism) and B2 (ZOE entity_review_needed carried, not dropped).

Rule-8 corrections baked into the verdicts (the probe's own method is not exempt):
- CORRECTION 1: a field that is LOW/blinky under measurement that is NOT its own source-directed
  retry is "RECOVERABILITY UNRESOLVED -- needs source-directed re-measure", NOT "leave single-pass".
  Only a ROBUST (always-found) result yields a final "no retry needed". Only REVENUE is measured
  with its own source-directed prompt here, so only revenue can be called genuinely-absent. (Pelago's
  blind 0/5 was wrong; do not repeat that mistake on any other field.)
- CORRECTION 2: every measured field is sampled the SAME N_REPEATS (5). No reduced sampling on the
  diffuse fields -- that would bake in the robustness the probe exists to test. The only cost lever
  is company count.

READ-ONLY: NO master/checkpoint/Drive writes. Per-company SCRATCH checkpoint (a plain JSON, NOT the
master) so a Colab disconnect doesn't lose hours of spend; resumes by skipping done companies. Costs
credits -> run only on an explicit go; check billing first (a sustained "rate limit" = out of
credits). Not a test; pytest does not collect it; the OpenAI client is built at runtime.

Run:  OPENAI_API_KEY=... python scripts/all_fields_blink_probe.py
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from health_tech_research_agent.research_runner import (
    DEFAULT_MODEL,
    DEFAULT_WAIT_BETWEEN_PASSES,
    REVENUE_RECOVERY_PASSES,
    _build_latest_status_findings,
    call_openai,
    is_search_failure,
    revenue_presence_check,
    revenue_source_directed_prompt,
    run_company_fit_brief,
    search_commercial_scale,
    search_funding,
    search_operating_characteristics,
    search_org_events,
    search_outcomes,
    search_payer_signal,
    search_with_recovery,
)
from health_tech_research_agent.review import parse_first_json_object

N_REPEATS = 5
WAIT = DEFAULT_WAIT_BETWEEN_PASSES  # 45s — independence spacing (same as the revenue validation)
SCRATCH_PATH = Path("all_fields_blink_probe_scratch.json")  # scratch only — NOT the master

# Approved 6-company sample (ZOE doubles as the soft strain case this round).
SAMPLE = [
    {"company": "Midi Health", "ground_truth": True,
     "research_query": "Midi Health (joinmidi.com), virtual menopause/perimenopause care, founded by Joanna Strober, HQ Menlo Park CA"},
    {"company": "Solace Health", "ground_truth": True,
     "research_query": "Solace Health (solace.health), patient-advocacy marketplace, founded by Jeremy Gurewitz"},
    {"company": "Pelago", "ground_truth": True,
     "research_query": "Pelago (pelago.health, formerly Quit Genius), digital substance-use clinic"},
    {"company": "ZOE", "ground_truth": True,
     "research_query": "ZOE (zoe.com), personalized nutrition, founded by Tim Spector and Jonathan Wolf"},
    {"company": "Function Health", "ground_truth": False,
     "research_query": "Function Health (functionhealth.com), comprehensive lab-testing membership, co-founded by Jonathan Swerdlin"},
    {"company": "Omada Health", "ground_truth": False,
     "research_query": "Omada Health (omadahealth.com), virtual cardiometabolic / chronic-condition care via employers and health plans"},
]

# Fields gathered by search_commercial_scale -> measured via the REAL source-directed mechanism.
COMMERCIAL_FIELDS = {
    "revenue": "a revenue / ARR / run-rate / GMV / sales figure -- NOT a funding round, valuation, or list price alone",
    "growth_signal": "ANY growth direction (growing / flat / declining), qualitative OR quantified",
    "growth_rate_quantified": "a QUANTIFIED growth RATE (a number, e.g. '287%', '+53% YoY', '10x') -- NOT just the word 'growing'",
    "paying_customer_count": "a count of PAYING customers / subscribers / members (exclude free, trial, pilot, covered-lives)",
    "revenue_per_user": "a per-paying-user revenue figure or the pricing needed to derive it",
}
# Other fields -> measured BLIND (no source-directed prompt yet); Correction 1 applies to their verdicts.
FUNDING_FIELDS = {"valuation": "a company valuation figure (e.g. '$1B valuation')"}
DIFFUSE_SEARCHES = [
    (search_payer_signal, {"payer_institutional": "evidence of payer / employer / provider / health-system institutional distribution (named contracts, partners, or covered lives)"}),
    (search_outcomes, {"outcomes": "clinical, real-world, or engagement/retention outcomes evidence"}),
    (search_org_events, {"org_events": "a recent (last ~12-18 months) leadership change, restructuring, layoffs, pivot, or transformation event"}),
    (search_operating_characteristics, {
        "operational_strain": "evidence of operational strain -- layoffs, backlog, service breakage, attrition, or scaling pain",
        "capability_fit": "evidence of the product-engagement structure / operating model (how the product is built and run)",
    }),
]
# Only revenue is measured with its own source-directed prompt -> only revenue can be called absent.
SOURCE_DIRECTED_FIELDS = {"revenue"}


def _build_client():
    from openai import OpenAI  # runtime import so the module stays importable offline

    return OpenAI()


def _score_presence(text, field_questions, *, client, model):
    """One cheap LLM call (no web search) scoring each field present/absent in `text`, by MEANING
    not keywords. Returns {field: True/False/None} (None on parse failure)."""
    if not str(text or "").strip() or is_search_failure(text):
        return {k: False for k in field_questions}  # failed/blank search -> nothing present
    items = "\n".join(f"- {k}: {q}" for k, q in field_questions.items())
    prompt = f"""Read the research text below. For EACH item, decide whether that SPECIFIC value is
PRESENT (a source actually states or credibly implies it) or ABSENT. Judge MEANING, not keywords --
e.g. "no revenue found" is ABSENT for revenue; a funding round is ABSENT for revenue.

Items:
{items}

Answer with ONLY a JSON object mapping each item key to "present" or "absent".

Research text:
{text}
"""
    out = call_openai(prompt, client=client, model=model, use_web_search=False, max_output_tokens=200)
    try:
        parsed = parse_first_json_object(out)
    except Exception:
        return {k: None for k in field_questions}
    return {
        k: (str(parsed[k]).strip().lower().startswith("present") if k in parsed else None)
        for k in field_questions
    }


def _repeat_search(search_fn, query, field_questions, *, client, model):
    """Run a search N_REPEATS times (blind), 45s apart, scoring its fields each repeat.
    Returns ({field: [present per repeat]}, first_finding) -- the first finding feeds the synthesis."""
    per_field = {k: [] for k in field_questions}
    first_finding = ""
    for r in range(N_REPEATS):
        if r:
            time.sleep(WAIT)
        finding = search_fn(query, client=client, model=model)
        if r == 0:
            first_finding = finding
        for k, v in _score_presence(finding, field_questions, client=client, model=model).items():
            per_field[k].append(v)
    return per_field, first_finding


def probe_company(case, *, client, model):
    query = case["research_query"]
    result = {"company": case["company"], "ground_truth": case["ground_truth"], "fields": {}}

    # --- COMMERCIAL fields via the REAL source-directed mechanism (5 passes) -> also B1 ---
    union, prov = search_with_recovery(
        search_commercial_scale, query, client=client, model=model,
        retry_prompt_builder=revenue_source_directed_prompt,
        presence_check=revenue_presence_check, field_name="revenue",
        n_passes=REVENUE_RECOVERY_PASSES, wait_between_passes=WAIT,
    )
    commercial = {k: [] for k in COMMERCIAL_FIELDS}
    for raw in prov.passes:  # the 5 per-pass findings -> blink rate per commercial field
        for k, v in _score_presence(raw, COMMERCIAL_FIELDS, client=client, model=model).items():
            commercial[k].append(v)
    result["fields"].update(commercial)
    result["b1_revenue_per_pass"] = commercial["revenue"]  # T/F across the 5 passes (Pelago focus)

    # --- FUNDING (valuation) + DIFFUSE searches, BLIND 5x ---
    funding_pf, funding_first = _repeat_search(search_funding, query, FUNDING_FIELDS, client=client, model=model)
    result["fields"].update(funding_pf)
    diffuse_first = {}
    for search_fn, fields in DIFFUSE_SEARCHES:
        pf, first = _repeat_search(search_fn, query, fields, client=client, model=model)
        result["fields"].update(pf)
        diffuse_first[search_fn.__name__] = first

    # --- B2 (ground-truth only): synthesis on the commercial UNION -> entity_review_needed + recovery ---
    if case["ground_truth"]:
        findings_block = _build_latest_status_findings(
            funding_first,
            diffuse_first.get("search_payer_signal", ""),
            diffuse_first.get("search_outcomes", ""),
            union,  # commercial union -- where any entity-doubt figure (ZOE "Join ZOE") lives
            diffuse_first.get("search_org_events", ""),
            diffuse_first.get("search_operating_characteristics", ""),
        )
        try:
            data = parse_first_json_object(
                run_company_fit_brief(case["company"], findings_block, client=client, model=model)
            )
            ce = data.get("commercial_evidence", {}) or {}
            result["b2"] = {
                "entity_review_needed": data.get("entity_review_needed", ""),
                "revenue_or_arr": ce.get("revenue_or_arr", ""),
            }
        except Exception as exc:  # noqa: BLE001 - diagnostic only
            result["b2"] = {"error": f"{type(exc).__name__}: {exc}"}

    return result


# --------------------------------------------------------------------------- reporting


def _blink_rate(flags):
    vals = [f for f in flags if f is not None]
    return (sum(1 for f in vals if f) / len(vals)) if vals else None


def _suggest_n(p, target=0.9):
    if p is None or p <= 0:
        return None
    if p >= 1:
        return 1
    return max(1, math.ceil(math.log(1 - target) / math.log(1 - p)))


def _verdict(field, rate):
    """Per-field decision, honoring Correction 1: only revenue is source-directed-measured here, so
    only revenue can be called genuinely-absent; any other field that is low/blinky is UNRESOLVED."""
    if rate is None:
        return "NO DATA (presence scoring failed)"
    if rate >= 0.9:
        return "ROBUST -> leave single-pass (no retry needed)"
    if rate <= 0.1:
        if field in SOURCE_DIRECTED_FIELDS:
            return "stable-absent under SOURCE-DIRECTED -> likely genuinely absent"
        return ("RECOVERABILITY UNRESOLVED -- low under non-source-directed measurement; "
                "needs a field-specific source-directed re-measure before any leave-single-pass call (Correction 1)")
    return ("HIGH BLINK -> ENABLE retry-and-union (data surfaced on some passes => recoverable); "
            f"suggested N≈{_suggest_n(rate)} (confirm/tune with a source-directed re-measure)")


def report(results):
    print("\n" + "#" * 90 + "\nALL-FIELDS BLINK-RATE MAP (per company; 1.0 = always found, 0.0 = never)\n" + "#" * 90)
    all_fields = list(COMMERCIAL_FIELDS) + list(FUNDING_FIELDS) + [
        k for _, fields in DIFFUSE_SEARCHES for k in fields
    ]
    companies = [r["company"] for r in results]
    print(f"\n{'field':<24} " + " ".join(f"{c[:10]:>10}" for c in companies) + "   measured-as")
    for field in all_fields:
        cells = []
        for r in results:
            rate = _blink_rate(r["fields"].get(field, []))
            cells.append("  n/a" if rate is None else f"{rate:>5.0%}")
        measured = "source-directed" if field in SOURCE_DIRECTED_FIELDS else "BLIND"
        print(f"{field:<24} " + " ".join(f"{c:>10}" for c in cells) + f"   {measured}")

    print("\n" + "#" * 90 + "\nPER-FIELD VERDICTS (worst-case across the sample; Correction 1 applied)\n" + "#" * 90)
    for field in all_fields:
        rates = [_blink_rate(r["fields"].get(field, [])) for r in results]
        present = [x for x in rates if x is not None]
        worst = min(present) if present else None  # the company where it surfaced least
        print(f"- {field:<24} {_verdict(field, worst)}")

    print("\n" + "#" * 90 + "\nGROWTH-RATE: variance vs the separate COVERAGE gap\n" + "#" * 90)
    for r in results:
        sig = _blink_rate(r["fields"].get("growth_signal", []))
        rate_q = _blink_rate(r["fields"].get("growth_rate_quantified", []))
        print(f"- {r['company']:<16} growth_signal={('n/a' if sig is None else f'{sig:.0%}')}  "
              f"quantified_rate={('n/a' if rate_q is None else f'{rate_q:.0%}')}  "
              f"(signal present but rate absent => the qualitative-'growing' coverage gap, a wording fix not a retry fix)")

    print("\n" + "#" * 90 + "\nB1 — Pelago per-pass revenue hit rate (vs the prior ~2/4)\n" + "#" * 90)
    for r in results:
        pp = r.get("b1_revenue_per_pass")
        if pp is not None:
            hits = sum(1 for x in pp if x)
            print(f"- {r['company']:<16} revenue per-pass: {['T' if x else 'F' for x in pp]}  ({hits}/{len(pp)})")

    print("\n" + "#" * 90 + "\nB2 — entity carry-and-flag (ground-truth; ZOE = the $82.3M 'Join ZOE' case)\n" + "#" * 90)
    for r in results:
        if "b2" in r:
            b2 = r["b2"]
            if "error" in b2:
                print(f"- {r['company']:<16} synthesis error: {b2['error']}")
            else:
                print(f"- {r['company']:<16} entity_review_needed={b2['entity_review_needed']!r}")
                print(f"    revenue_or_arr: {b2['revenue_or_arr']}")


def run_probe(*, model=DEFAULT_MODEL):
    client = _build_client()
    done = {}
    if SCRATCH_PATH.exists():  # resume: skip companies already scored
        done = {r["company"]: r for r in json.loads(SCRATCH_PATH.read_text())}
        print(f"Resuming — {len(done)} companies already scored in {SCRATCH_PATH}.")
    results = list(done.values())
    for case in SAMPLE:
        if case["company"] in done:
            continue
        print(f"\n>>> probing {case['company']} ...")
        results.append(probe_company(case, client=client, model=model))
        SCRATCH_PATH.write_text(json.dumps(results, indent=2))  # checkpoint after each company
        print(f"    checkpointed ({len(results)}/{len(SAMPLE)}).")
    # report in sample order
    by_company = {r["company"]: r for r in results}
    report([by_company[c["company"]] for c in SAMPLE if c["company"] in by_company])


if __name__ == "__main__":  # pragma: no cover - manual, credit-spending
    run_probe()

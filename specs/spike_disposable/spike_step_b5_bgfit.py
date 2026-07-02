# =====================================================================================
# DISPOSABLE PHASE-2 SPIKE — STEP B5: BACKGROUND-FIT GRADIENT (1-10). Throwaway/scratch,
# clean-room from SOT §B5. The wording is STAGED -> joint-review BEFORE scores are final.
# Scores the 37 GATE-PASSED companies ONLY (the 17 floored are out by design). ~37 no-web calls.
# Prereqs already run in THIS Colab: Step 2 (client) + Step 3 (call_openai); Drive mounted.
# Nourish "periodic" mislabel is the §B5 named regression — printed explicitly.
# =====================================================================================
import json
import pandas as pd

CSV_PATH = "/content/drive/MyDrive/Job Search/Health Tech Research/research_batches/v42_full_regen_clean_slate_20260622_full56_checkpoint.csv"
df = pd.read_csv(CSV_PATH).fillna("")

# the 37 that PASSED both gates in the spike deterministic core (17 floored excluded by design)
PASSED = {
    "function health", "grow therapy", "zoe", "angle health", "rula health", "oula", "familywell health",
    "cylinder health", "levels health", "season health", "pelago", "bicycle health", "counsel health",
    "equip health", "nourish", "outcomes4me", "fay", "pomelo care", "affect therapeutics", "culina health",
    "solace health", "summer health", "oshi health", "allara health", "jasper health", "foodsmart", "wellist",
    "9amhealth", "waymark", "diana health", "visana health", "insidetracker", "vivante health", "berry street",
    "oova", "tia", "signos",
}
assert len(PASSED) == 37, f"expected 37 passed, got {len(PASSED)}"

# ---- STAGED §B5 wording (review THIS before trusting the scores) ----
BG_PROMPT = """You score BACKGROUND FIT for a CONSUMER-facing health company: HOW CLOSE its consumer-engagement model is to the "mobile-games loop" -- habitual, high-frequency, retention-driven engagement the consumer keeps returning to on their own. This is a GRADIENT (1-10), not a pass/fail. (Precondition already met upstream: the consumer is the end-user of the company's OWN product/service.)

Output ONE JSON object and nothing else:
{{"background_fit": <integer 1-10>,
  "data_feedback_loop": "yes" or "no",
  "basis": "<one line describing the consumer's ACTUAL ongoing engagement>"}}

SCALE:
- 9-10 = a tight DATA-FEEDBACK LOOP: the consumer sees their OWN body/health data -> acts on it -> sees the result reflected back -> repeats. The habitual self-tracking loop (metabolic / CGM / wearable / biomarker / continuous activity or glucose tracking). This loop is the top-of-scale AMPLIFIER -> set data_feedback_loop = "yes".
- 6-8 = a STRONG consumer-habit model WITHOUT that tight data-loop: frequent, retention-driven engagement the consumer actively sustains (recurring coaching / therapy / care they personally show up for, a consumer app with real habitual use, an ongoing condition-management relationship). A strong consumer-health company that simply LACKS the data-feedback loop STILL SCORES SOLIDLY HERE -- do NOT floor it merely for lacking the loop.
- 3-5 = a genuinely EPISODIC / intermittent consumer relationship: the consumer engages around a discrete need or event and then largely leaves, with little sustained habit.
- 1-2 = almost no recurring consumer-engagement surface.

DO NOT under-score (the "periodic" trap): judge the consumer's ACTUAL ongoing engagement with the company's OWN product/service. Care delivered through the company's employed clinicians/coaches, or paid for by an employer/health-plan, is STILL the consumer's own habit -- do not label it "periodic" for that reason. A serious or medically-driven condition is NOT automatically low-frequency: a daily nutrition program, an ongoing therapy relationship, or continuous condition management is HABITUAL even when the underlying need is medical. Score 3-5 ONLY when the engagement is genuinely one-off / intermittent.

Company: {company}
Evidence:
{evidence}"""


def bg_fit(row):
    ev = "\n\n".join(filter(None, [
        str(row.get("operating_characteristics_finding", "")),
        str(row.get("commercial_scale_finding", "")),
        str(row.get("outcomes_finding", "")),
    ]))[:9000]
    out = call_openai(BG_PROMPT.format(company=row["company"], evidence=ev),  # noqa: F821 (Step 3)
                      use_web_search=False, max_output_tokens=220)
    try:
        d = json.loads(out[out.find("{"): out.rfind("}") + 1])
        return int(d["background_fit"]), str(d.get("data_feedback_loop", "")).strip().lower(), str(d.get("basis", ""))
    except Exception:
        return None, "?", "PARSE_FAIL: " + out[:120]


scores = {}
for _, row in df.iterrows():
    co = str(row["company"]).strip().lower()
    if co in PASSED:
        scores[co] = bg_fit(row)

# ---- read-back / coverage validation (catch a wrong or partial CSV BEFORE trusting scores) ----
missing = sorted(PASSED - set(scores))
parse_fails = sorted(co for co, v in scores.items() if v[0] is None)
print(f"COVERAGE: scored {len(scores)}/37 of the gate-passed set"
      + (f"  | MISSING from CSV: {missing}" if missing else "  | none missing OK")
      + (f"  | PARSE-FAILS: {parse_fails}" if parse_fails else "  | no parse-fails OK"))
if missing:
    print("  ** STOP: a gate-passed company is absent from this CSV -> wrong/partial file."
          " Confirm CSV_PATH matches the file your classifier round ran against. **")

print("=" * 104)
print("B5 BACKGROUND-FIT (1-10) — 37 gate-passed companies | STAGED wording (scores NOT final until wording locked)")
print("=" * 104)
for co in sorted(scores, key=lambda c: (-(scores[c][0] if scores[c][0] is not None else -1), c)):
    bf, loop, basis = scores[co]
    amp = "LOOP" if loop in ("yes", "true") else " .  "
    print(f"   {co:20} bg_fit={str(bf):>4}  [{amp}]  {basis[:92]}")

print("\n" + "-" * 104)
nb, nloop, nbasis = scores.get("nourish", (None, "?", "(nourish missing from passed set?)"))
print(f"NOURISH REGRESSION CHECK -> bg_fit={nb}   data_feedback_loop={nloop}")
print(f"   basis: {nbasis}")
print("   EXPECT >=6 (daily nutrition-coaching = strong consumer habit). If LOW on a 'periodic/episodic'")
print("   read -> that is the STAGED-WORDING regression: fix doc-first, do NOT accept as a calibration dial.")

print("\n" + "=" * 104)
print("PASTE THIS WHOLE BLOCK BACK to Claude Code (offline full-table assembly):")
print("=" * 104)
print("BG_FIT = {")
for co in sorted(scores):
    bf, loop, basis = scores[co]
    safe = basis.replace('"', "'").replace("\n", " ")[:120]
    print(f'    "{co}": [{bf}, "{loop}", "{safe}"],')
print("}")

# OFFLINE FULL-TABLE ASSEMBLY (Task 2). Execs the spine, ingests the pasted BG_FIT (§B5 scores
# from Colab), computes FINAL = bg_fit + pmf + strain, ranks desc, prints the full component table
# with floor_rule_ok (bf>4 AND pmf>4) + known flags + FINAL distribution. THRESHOLDS NOT APPLIED.
# Run: python3 spike_assemble_full_table.py   (after pasting real BG_FIT below).
import os, runpy, pandas as pd  # noqa
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(os.path.join(HERE, "spike_scoring_spine.py"), run_name="_spine_lib")
run = ns["run"]
CSV = "/Users/katelyndlavallee/Downloads/v42_full_regen_clean_slate_20260622_full56_checkpoint_FINAL.csv"
df = pd.read_csv(CSV).fillna("")

# ---- PASTE the real BG_FIT dict from the Colab b5 cell here (placeholder = render smoke-test) ----
try:
    from bg_fit_scores import BG_FIT  # next turn: drop the pasted dict into bg_fit_scores.py
except Exception:
    BG_FIT = None  # placeholder -> uniform dummy 7 just to verify the table renders

PASSED_HINT = None
def bg_fit_fn(r, fb, bm):
    co = str(r["company"]).strip().lower()
    if BG_FIT is None:
        return 7  # DUMMY render-check only (NOT real scores)
    v = BG_FIT.get(co)
    return (v[0] if v else None)

def loop_of(co):
    if BG_FIT is None: return "?"
    v = BG_FIT.get(co); return (v[1] if v else "?")

# known spike-grade flags carried into the table so Pass-2 reads with asterisks visible
FLAGS = {
    "outcomes4me": "FENCE-LEAK 485% patient-count -> grw inflated",
    "pomelo care": "FENCE-LEAK 50% covered-lives -> grw inflated",
    "season health": "UNDER-EXTRACT ~53.7% missed -> grw low",
    "jasper health": "DATA-GAP no rev figure",
}

rows, floored, cap7, zb, residual = run(df, bg_fit_fn)
zb_set = {co for co, *_ in zb}

# ---- PASS-2 Step A: the two SETTLED framework calls (overlays — NOT scoring-logic changes) ----
OVERRIDE_CANDIDATE = {"function health"}  # keep bg_fit=4; tag for review-time human override (Rule 6)
LEAK_DISCOUNTED = {"outcomes4me"}         # floor=PASS rides the 485% fence-leak -> floor-FAIL for calibration
def eff_floor_ok(x):
    return False if x["company"] in LEAK_DISCOUNTED else x["floor_ok"]

print("=" * 140)
print("FULL RANKED TABLE — POST Step A  (FINAL = background_fit + pmf + strain)   |   THRESHOLDS NOT APPLIED")
if BG_FIT is None:
    print("*** RENDER SMOKE-TEST: BG_FIT placeholder (uniform dummy 7). NOT real scores. ***")
print("=" * 140)
hdr = f"{'company':20}{'model':6}{'stage':14}{'bgfit':6}{'lp':3}{'arr':4}{'grw':4}{'ac':3}{'pmf':4}{'str':4}{'FINAL':6}{'floor_ok':10}flags"
print(hdr); print("-" * 140)
for x in rows:
    co = x["company"]
    bf = x["bf"]; lp = "Y" if loop_of(co) in ("yes", "true") else "."
    fr = "PASS" if eff_floor_ok(x) else "fail"
    if co in LEAK_DISCOUNTED: fr = "fail†"     # discounted from PASS
    fl = FLAGS.get(co, "")
    if co in OVERRIDE_CANDIDATE: fl = (fl + " | " if fl else "") + "HUMAN-OVERRIDE-CANDIDATE (revenue+complexity unicorn; bf kept=4)"
    if co in LEAK_DISCOUNTED:    fl = (fl + " | " if fl else "") + "LEAK-DISCOUNTED -> floor=FAIL for calibration"
    if co in zb_set: fl = (fl + " | " if fl else "") + "zero-baseline"
    print(f"{co:20}{x['bm']:6}{x['stage']:14}{str(bf):6}{lp:3}{str(x['al']):4}{str(x['gr']):4}{str(x['accel']):3}"
          f"{str(x['pmf']):4}{str(x['strain']):4}{str(x['final']):6}{fr:10}{fl}")

from collections import Counter
fin_hist = Counter(x["final"] for x in rows)
fr_pass = sum(1 for x in rows if eff_floor_ok(x))
print("\nFINAL distribution:", " ".join(f"{k}:{fin_hist[k]}" for k in sorted(fin_hist)))
print(f"floor_rule_ok (bf>4 AND pmf>4, POST Step A): PASS {fr_pass}/{len(rows)}  (flag only — NOT a P-tier assignment)")
print("  Step A applied: function health = override-candidate (bf kept 4); outcomes4me = leak-discounted (PASS->FAIL†).")
print(f"gate-floored (P3, out of the 37): {len(floored)}  | zero-baseline tagged: {len(zb)}")
print("\nbg_fit LOCKED v1.7 · thresholds NOT applied · zero-baseline + other dials NOT calibrated (Step B next) · HOLD for Katelynd")

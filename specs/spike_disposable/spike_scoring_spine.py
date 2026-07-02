# =====================================================================================
# DISPOSABLE PHASE-2 SCORING SPIKE — gated-then-ranked spine, clean-room from SOT v1.4 §B3-B7.
# THROWAWAY / SCRATCH. NOT package code, NOT wired into the flow. Phase-3 hardening is separate.
# Dials at SOT defaults; THRESHOLDS NOT APPLIED (raw scores + components only). HOLD after output.
#
# business_model = the TRUSTED-for-spike classifier result = fixture truth + locked floor + 3 overrides
# (documented). PATH + AGENCY + PMF + STRAIN are deterministic from the persisted evidence + the SOT-B4
# funding mapper. BACKGROUND-FIT (§B5) is the ONE LLM gradient (STAGED) -- pluggable: real LLM in Colab,
# stub offline. PMF per-stage cutoffs are SPIKE-PROVISIONAL (anchored to the SOT's stated anchors; §C
# PLACEHOLDER -> calibrated in Pass 2, not invented arbitrarily).
# =====================================================================================
import json, re, math
from collections import Counter
import pandas as pd
from health_tech_research_agent.structured_evidence import funding_stage_from_rounds  # SOT B4 mapper (not old scoring code)

# ---- business_model: fixture truth (firefly deferred). floor-6 + 3 overrides are baked in here. ----
FX_B2B   = {"openevidence","cohere health","zus health","om1","medically home","linus health"}  # human-locked floor (§B2 v1.4)
FX_B2C   = {"oura","insidetracker","function health","noom med","oova","levels health","zoe","signos"}
FX_B2B2C = {"nourish","equip health","grow therapy","maven clinic","omada health","oshi health","visana health","sword health","solace health","midi health","transcarent","familywell health","headway","affect therapeutics","9amhealth","culina health","jasper health","fay","season health","pomelo care","thyme care","hinge health","waymark","oula","mae health","cylinder health","foodsmart","rula health","pelago","bicycle health","vivante health","diana health","summer health","berry street","counsel health","wellist","angle health","outcomes4me","allara health","tia"}
BUSINESS_MODEL = {**{c:"B2B" for c in FX_B2B}, **{c:"B2C" for c in FX_B2C}, **{c:"B2B2C" for c in FX_B2B2C}}
LOCKED_FLOOR = FX_B2B  # §B2 v1.4: forced B2B regardless of classifier; covers medically home
# STAGE_OVERRIDE: Katelynd-approved stage corrections (SOT §B4 v1.10 designated-series rule), the disposable
# analogue of the §B2 human-locked floor. signos/bicycle: a later same-series venture round does NOT advance
# the series. 9amhealth: no-op (already series-b; the STEP-0 audit misread its clean Series B, May 2026).
STAGE_OVERRIDE = {"signos": "series-b", "bicycle health": "series-b", "9amhealth": "series-b"}

ABSENT = ("", "none", "n/a", "na", "unknown", "none found", "not found", "no ", "no strong", "did not find")
def _has(v):
    t = re.sub(r"\s+"," ",str(v)).strip().lower()
    return bool(t) and not any(t.startswith(a) for a in ABSENT)
def _ce(fb):  return fb.get("commercial_evidence", {}) if isinstance(fb, dict) else {}
def _me(fb):  return fb.get("maturity_evidence", {}) if isinstance(fb, dict) else {}

# ---- PATH gate (§B3) ----
# ROBUST presence checks — detect a figure / named channel ANYWHERE in the finding (the findings lead with
# hedges like "No company-reported ARR, but Sacra estimates $100M" — a prefix check false-floors them).
def _figure(text):
    t = str(text).lower()
    return bool(re.search(r'\$\s*[\d.]+\s*(k|m|b|million|billion)', t)) or bool(re.search(r'\b\d[\d,]*\s*(k|m|million|billion)\b', t))
def has_any_revenue(ce):       return _figure(ce.get("revenue_or_arr",""))
def has_meaningful_scale(ce):  return _figure(ce.get("sponsored_user_scale","")) or _figure(ce.get("paying_customer_count",""))
def has_positive_growth(ce):
    g = str(ce.get("growth_signal","")).lower()
    return ("grow" in g or bool(re.search(r'\d+\s*%', g)) or "x over" in g or "tripl" in g or "doubl" in g) and "declin" not in g
def has_real_institutional_channel(row, ce):
    blob = (str(row.get("payer_institutional_finding","")) + " " + str(ce.get("business_model_type",""))).lower()
    named = bool(re.search(r'aetna|blue cross|bcbs|anthem|unitedhealth|\buhc\b|cigna|oscar|humana|medicaid|medicare|\bcms\b|commonspirit|essence|baptist', blob))
    structural = (bool(re.search(r'covered lives|in-?network|\d[\d,]*\s*(?:members|covered|lives)\b', blob))
                  or ("employer" in blob and any(k in blob for k in ["partner","client","benefit","self-insured","for work","sponsored","funds"]))
                  or ("health plan" in blob and any(k in blob for k in ["partner","contract","client","relationship"]))
                  or "value-based" in blob or "outcomes-based contract" in blob)
    return named or structural
def path_gate(row, fb, bm):
    if bm == "B2B":  return "FAIL", "Test A: B2B (no consumer end-user)"
    ce = _ce(fb)
    if bm == "B2C":
        alive = has_any_revenue(ce) or has_meaningful_scale(ce) or has_positive_growth(ce)   # no-revenue fallback ^c10
        return ("PASS","Test B B2C: engine-alive (rev|user-scale|growth)") if alive else ("FAIL","Test B B2C: DEAD (no rev/scale/growth)")
    if bm == "B2B2C":
        ok = has_real_institutional_channel(row, ce)
        return ("PASS","Test B B2B2C: real institutional channel") if ok else ("FAIL","Test B B2B2C: no real institutional channel")
    return "FAIL","UNMAPPED"

# ---- AGENCY gate (§B4) ----
RESET_FIRES = {"leadership-change","founder-transition","post-failure-rebuild","restructuring-layoffs","declared-transformation"}
def _norm(s): return re.sub(r"[\s_]+","-",str(s).strip().lower())
# SOT §B4 v1.5 sharpenings applied to the EMITTED events (the regen's emitter pre-dates v1.5):
_PIVOT_SUBSTANCE = re.compile(r"pricing|business[- ]model|outcome pricing|pivotal evolution|evolution into|moving beyond|into a more|expansion into|product strategy|integrated[- ]care platform", re.I)
_IPO_PREP        = re.compile(r"\bipo\b|s-1|registration statement|public[- ]market|go(?:ing)? public", re.I)
_GROWTH_SUPPORT  = re.compile(r"to support .{0,40}expansion|to accelerate growth|accelerate growth and expand|support .{0,30}expansion", re.I)
def _event_qualifies(e):
    if not isinstance(e, dict): return False
    if str(e.get("creates_high_agency_opening","")).strip().lower() not in ("yes","true"): return False  # CONFIDENCE bar: unclear/no never fires
    if _norm(e.get("event_type")) not in RESET_FIRES: return False                                       # strategic-pivot / ma-integration excluded by type
    basis = str(e.get("basis",""))
    if _PIVOT_SUBSTANCE.search(basis): return False   # SUBSTANCE-over-label: business-model/pricing/product-strategy = pivot
    if _IPO_PREP.search(basis):        return False   # IPO-prep NON-QUALIFYING
    if _GROWTH_SUPPORT.search(basis):  return False   # growth-support exec add is not a reopening
    return True
def reset_fired(fb):
    evs = fb.get("reset_evidence", {}).get("reset_events", []) if isinstance(fb, dict) else []
    return any(_event_qualifies(e) for e in evs) if isinstance(evs, list) else False
def agency_gate(fb):
    me = _me(fb)
    stage = funding_stage_from_rounds(me.get("funding_rounds"), me.get("ipo_event")) or "unknown"
    ipo = str(me.get("ipo_status","")).strip().lower()
    rf = reset_fired(fb)
    late_c_flag = (stage == "series-c")  # OPEN-DIAL exposed (clean PASS this run)
    if ipo == "public" or stage == "public":
        return (("PASS" if rf else "FAIL"), f"public/{stage} mature" + (" +reset" if rf else " (no reset)"), stage, late_c_flag)
    if stage == "series-d-plus":
        return (("PASS" if rf else "FAIL"), f"{stage} late-stage" + (" +reset" if rf else " (no reset)"), stage, late_c_flag)
    if stage in ("seed","pre-seed"):
        return ("FAIL", f"{stage} too-early (no reset rescue)", stage, late_c_flag)
    if stage in ("series-a","series-b","series-c"):
        return ("PASS", f"{stage} -> PASS" + (" [late-C clean-pass, dial]" if late_c_flag else ""), stage, late_c_flag)
    return ("FAIL", f"{stage} undeterminable", stage, late_c_flag)

# ---- PMF (§B6) — COMMITTED Scale A (ARR) + Scale B (growth) + geometric interp (SOT v1.8, LOCKED) ----
# Clean-room to the committed rule: replaces the spike's improvised sqrt-ARR curve + stage-blind % bands.
# Acceleration REMOVED + PARKED (does not fire). Zero-baseline -> Scale A on the magnitude (arr=growth collapse).
ARR_SCALE = {   # representative ARR in $M at score 1..10 (Scale A)
    "seed":          [0.10, 0.178, 0.316, 0.562, 1.0, 1.4, 1.9, 2.6, 3.6, 5.0],
    "series-a":      [5, 6.6, 8.7, 11.4, 15, 19.1, 24.3, 30.9, 39.3, 50],
    "series-b":      [15, 20.3, 27.4, 37, 50, 54.9, 60.3, 66.3, 72.8, 80],
    "series-c":      [30, 38.3, 49, 62.6, 80, 104, 136, 177, 230, 300],
    "series-d-plus": [50, 65.8, 86.6, 114, 150, 191, 243, 309, 393, 500],
    "public":        [100, 126, 158, 199, 250, 330, 435, 574, 758, 1000],
}
GROWTH_SCALE = {   # % YoY growth at score 1..10 (Scale B, engine-agnostic)
    "seed":     [25, 30, 45, 65, 90, 120, 160, 210, 280, 350],
    "series-a": [30, 45, 60, 80, 100, 125, 155, 200, 280, 400],
    "series-b": [25, 35, 45, 60, 75, 90, 110, 135, 170, 200],
    "series-c": [15, 22, 30, 38, 48, 58, 70, 90, 120, 150],
    "public":   [10, 15, 20, 27, 35, 42, 50, 62, 80, 100],
}
def _arr_stage(stage):     # Scale A normalization (no scored co is pre-seed/unknown; mapped for safety)
    return stage if stage in ARR_SCALE else ("seed" if stage == "pre-seed" else "series-b")
def _growth_stage(stage):  # Scale B stage map: series-d-plus reads the PUBLIC row; seed/a/b/c 1:1
    if stage in ("series-d-plus", "public"): return "public"
    return stage if stage in GROWTH_SCALE else ("seed" if stage == "pre-seed" else "series-b")
def scale_interp(v, pts):  # geometric, round-half-up; pts ascending @ score 1..10
    if v <= pts[0]:  return 1
    if v >= pts[-1]: return 10
    for s in range(1, 10):                     # s = lower score: lo=pts[s-1]@s, hi=pts[s]@s+1
        lo, hi = pts[s-1], pts[s]
        if lo <= v <= hi:
            return max(1, min(10, int(math.floor(s + math.log(v/lo)/math.log(hi/lo) + 0.5))))
    return 10
def _money(s):
    out=[]
    for m in re.finditer(r'\$?\s*([\d.]+)\s*(b|m)\b', str(s).lower()):
        out.append(float(m.group(1))*(1e9 if m.group(2)=="b" else 1e6))
    return max(out) if out else None
def arr_level_score(ce, stage):
    arr = _money(ce.get("revenue_or_arr",""))
    if arr is None: return None
    return scale_interp(arr/1e6, ARR_SCALE[_arr_stage(stage)])     # Scale A ($M) + geometric interp
# §B6.1 FENCE — these growth contexts must NOT feed growth_score (route to strain/sponsored_user_scale).
# (covered-lives/paid-member growth is NOT fenced — it is paid growth, not non-paying user-scale.)
_FENCE = re.compile(r"headcount|employee|staff|download|install|\bmau\b|\busers?\b|user-scale|registered|active users|app(?:\s|-)?(?:download|install)|partner|client-count|funding round|valuation|utilization|covered lives|covered-lives|\bpatients?\b|member reach", re.I)
def growth_score(ce, stage, raw_growth=""):
    rev = str(ce.get("revenue_or_arr",""))
    g = str(ce.get("growth_signal","")) + " || " + rev + " || " + str(raw_growth)[:3000]
    gl = g.lower()
    src = "derived" if re.search(r'derived|sacra|latka|growjo|cb insights|third-party|estimate', gl) else "company-reported"
    # ZERO-BASELINE: launch-from-zero REVENUE -> score the magnitude reached via Scale A (arr=growth collapse).
    # Magnitude taken from revenue_or_arr (revenue context) to avoid grabbing covered-lives/member counts.
    if re.search(r'\$\s*0\b.{0,40}?(?:->|→|to)\s*\$?\s*[\d.]+\s*[mb]|from zero|zero revenue|launch(?:ed)?\b.{0,40}?\$\s*[\d.]+\s*[mb]', gl):
        mag = _money(rev)
        if mag:
            sc = scale_interp(mag/1e6, ARR_SCALE[_arr_stage(stage)])
            return sc, sc, 0, f"zero-baseline ->${mag/1e6:.0f}M=>{sc}(ScaleA)", "zero-baseline"
    # explicit % / multiple, FENCED to revenue/paid context (skip a figure adjacent to a fenced term, ±40)
    pct = mult = None
    for m in re.finditer(r'(\d{1,4}(?:\.\d+)?)\s*%', gl):
        if not _FENCE.search(gl[max(0,m.start()-40):m.end()+40]): pct = float(m.group(1)); break
    for m in re.finditer(r'([\d.]+)\s*x\b', gl):
        if not _FENCE.search(gl[max(0,m.start()-40):m.end()+40]): mult = float(m.group(1)); break
    if "tripl" in gl: mult = max(mult or 0, 3.0)
    if "doubl" in gl: mult = max(mult or 0, 2.0)
    if pct is None and mult is not None: pct = (mult - 1.0) * 100.0    # multiple -> % YoY (3x=+200%, 2x=+100%)
    if pct is not None:
        base = scale_interp(pct, GROWTH_SCALE[_growth_stage(stage)])   # Scale B (stage-relative); NO acceleration
        return base, base, 0, f"{pct:g}%@{_growth_stage(stage)}", src
    # qualitative fallbacks — NO quantified rate (the Step-C no-quantified-rate dial; UNCHANGED this turn)
    if "declin" in gl:                  return 1, 1, 0, "declining(no-rate)", src
    if re.search(r'\bflat\b', gl[:40]): return 3, 3, 0, "flat(no-rate;StepC)", src
    if "grow" in gl:                    return 5, 5, 0, "growing(no-rate;StepC)", src
    return None, None, 0, "no revenue-growth figure", src
def pmf(ce, stage, raw_growth=""):
    al = arr_level_score(ce, stage)
    g_base, g_final, accel, gnote, gsrc = growth_score(ce, stage, raw_growth)
    # CAP only on GENUINE revenue-growth absence (Pass-1 fix: derived/estimate + zero-baseline SCORE, are NOT
    # the missing-data cap; the prior `"estimate" in q4 -> cap` over-capped ~30 credible-estimate companies).
    cap = (g_final is None)
    al_e, g_e = (al if al is not None else 4), (g_final if g_final is not None else 4)
    raw = 0.4*al_e + 0.6*g_e
    val = round(raw)
    if cap: val = min(val, 7)
    return val, (al if al is not None else "—"), (g_final if g_final is not None else "—"), accel, cap, gnote, gsrc

# ---- STRAIN (§B7) — structured a2_score + speed-of-scale text; strict B2 bar; default LOW ----
def strain(row, fb):
    a2 = fb.get("capability_evidence",{}).get("a2_score") if isinstance(fb,dict) else None
    try: a2 = int(a2)
    except: a2 = None
    op = str(row.get("operating_characteristics_finding","")).lower()
    speed = bool(re.search(r'\d0{1,3}\s*(?:->|→|to)\s*\d', op)) or "in ~6" in op or "doubled" in op
    if a2 is not None and a2 >= 70: return 2, "STRONG", f"a2={a2}"
    if (a2 is not None and a2 >= 55) or speed: return 1, "MODERATE", (f"a2={a2}" if a2 else "speed-of-scale")
    return 0, "WEAK", "default-low"

def run(df, bg_fit_fn):
    rows, floored, zero_baseline, residual_cap = [], [], [], []
    cov_cap7 = 0
    for _, r in df.iterrows():
        co = str(r["company"]).strip().lower()
        try: fb = json.loads(r["fit_brief_json"])
        except Exception: fb = {}
        bm = "B2B" if co in LOCKED_FLOOR else BUSINESS_MODEL.get(co, "UNMAPPED")
        ag, agwhy, stage, lateC = agency_gate(fb)
        stage = STAGE_OVERRIDE.get(co, stage)   # §B4 v1.10 designated-series corrections (Katelynd-approved)
        pa, pawhy = path_gate(r, fb, bm)
        if pa == "FAIL" or ag == "FAIL":
            floored.append((co, bm, ("PATH:"+pawhy) if pa=="FAIL" else ("AGENCY:"+agwhy))); continue
        ce = _ce(fb)
        pm, al_s, gr_s, accel, cap, gnote, gsrc = pmf(ce, stage, r.get("growth_finding",""))
        if gsrc == "zero-baseline": zero_baseline.append((co, stage, gr_s, gnote))
        if cap: cov_cap7 += 1; residual_cap.append((co, gnote))
        st, sttag, stwhy = strain(r, fb)
        bf = bg_fit_fn(r, fb, bm)          # §B5 LLM (STAGED); None offline
        final = (bf if bf is not None else 0) + (pm if pm is not None else 0) + st
        floor_ok = (bf is not None and bf > 4 and pm is not None and pm > 4)
        rows.append(dict(company=co, bm=bm, stage=stage, bf=bf, al=al_s, gr=gr_s, accel=accel, pmf=pm,
                         cap=cap, strain=st, sttag=sttag, final=final, floor_ok=floor_ok,
                         bf_pending=(bf is None), gnote=gnote, gsrc=gsrc))
    rows.sort(key=lambda x: (x["final"], x["pmf"] if isinstance(x["pmf"],int) else -1), reverse=True)
    return rows, floored, cov_cap7, zero_baseline, residual_cap

def print_report(df, bg_fit_fn, llm=False):
    rows, floored, cap7, zb, residual = run(df, bg_fit_fn)
    print(f"Parsed rows: {len(df)} | passed both gates: {len(rows)} | gate-floored (P3): {len(floored)}")
    print(f"\n{'company':20}{'model':6}{'stage':13}{'bgfit':6}{'arr':4}{'grw':4}{'ac':3}{'pmf':4}{'cap':4}{'str':4}{'gsrc':10}{'FINAL':7}")
    for x in rows:
        bf = (x['bf'] if not x['bf_pending'] else 'PEND')
        fin = (x['final'] if not x['bf_pending'] else f"{x['final']}+bf")
        print(f"{x['company']:20}{x['bm']:6}{x['stage']:13}{str(bf):6}{str(x['al']):4}{str(x['gr']):4}{str(x['accel']):3}{str(x['pmf']):4}{('Y' if x['cap'] else '-'):4}{str(x['strain']):4}{str(x['gsrc']):10}{str(fin):7}")
    print(f"\nGATE-FLOORED (P3) — {len(floored)}:")
    for co, bm, why in floored: print(f"   {co:20}{bm:6} {why}")
    print(f"\nZERO-BASELINE companies (growth via magnitude+stage DIAL — SURFACED for Pass-2, not calibrated) — {len(zb)}:")
    for co, stage, sc, note in zb: print(f"   {co:20}{stage:13} growth_score={sc}  [{note}]")
    print(f"\nGENUINELY-ABSENT residual (still cap@7) — {len(residual)}:")
    for co, note in residual: print(f"   {co:20} {note}")
    from collections import Counter as _C
    pmf_hist = _C(x["pmf"] for x in rows if isinstance(x["pmf"],int))
    base_hist = _C((x["pmf"] or 0)+x["strain"] for x in rows)
    print(f"\nPMF distribution: " + " ".join(f"{k}:{pmf_hist[k]}" for k in sorted(pmf_hist)))
    print(f"(pmf+strain) base spread: " + " ".join(f"{k}:{base_hist[k]}" for k in sorted(base_hist)))
    print(f"\nDATA-COVERAGE: scored-on-real-growth = {len(rows)-cap7}/{len(rows)} | cap@7 = {cap7}/{len(rows)} (was 34/40) | zero-baseline-scored = {len(zb)}")
    if not llm:
        print("\n[OFFLINE] background_fit=PEND (§B5 LLM in Colab; HELD). PMF cutoffs SPIKE-PROVISIONAL (§C). THRESHOLDS NOT APPLIED.")

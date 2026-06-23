# Run-once V4.2 clean-slate regeneration — Colab execution runsheet

**Status:** ready to execute (gate clear; merge to `main` done). Run-once.
**Created:** 2026-06-22. Keep this file in sync with any change to the regen flow.
**Companion docs:** `phase2_refresh_runbook.md` (the pre-regen gate + reminders),
`COLLABORATION_CONTEXT.md` (handoff/state).

This is the cell-by-cell script for the single clean-slate regeneration: the master is discarded
(archived first), rebuilt fresh so every company is an INSERT, researched anew through the
item-8 budgets + guard, landed via the notebook's STEP 12, and read back. Decisions locked:
(1) insert-path dry-run is a HARD GATE; (2) re-research everything via Step 7 (no STEP 26
rescore-from-archive); (3) clear ALL research checkpoints so nothing pre-item-8 is reused.

---

## Corrected flow at a glance (the irreversible ordering)

```
clear checkpoints → batch config → ARCHIVE master → FRESH-INIT (empty master)
   → research (Step 7) → Step 10 → 10A → Step 10 (re-run) → 10B → 10C
   → STEP 12 dry-run → ◾HARD STOP #1 (verify) → flip DRY_RUN→False
   → re-run STEP 12 (real) → read-back → (dashboard = separate milestone)
```

The master is emptied **only after it is archived**, and stays empty until the single real write.
The notebook's dry-run always **reads the real master**, so emptying it first is what makes every
company an INSERT in both the dry-run and the real write — the only difference between them is the
`DRY_RUN` flag.

## Quick references

- **DRY_RUN toggle:** the `## Dry Run Setup` cell — `DRY_RUN = True` (defaults True ✅). Isolation
  lives inside the `## 12` cell; it diverts **writes** to `/content/DRYRUN_*` and always **reads**
  the real Drive master. Flip is the `## Real Write` cell (`DRY_RUN = False`).
- **Rate-limit wait:** confirm `WAIT_BETWEEN_WEB_SEARCHES = 120` in the `## Step 2` cell (not 5).
- **STEP 12 cell ends before the verify scaffolding.** Everything after the master-write +
  `files.download` block in the `## 12` cell, plus the `## Gate 2` and `## Final Read Back` cells,
  is ZOE/Function verify-batch scaffolding — it crashes on a different company set (IndexError /
  `REAL_MASTER_PATH` NameError) and reads stale throwaway paths. **Delete it; use the verification
  cell below.**

---

## ⚠️ Required code fix before the run — Step 10A drops the two Slice 3.7 findings

Step 10A's schema list was never updated for Slice 3.7. Near the top of the `## 10A` cell it defines
a **7-column** `required_current_schema_cols` (no `org_events_finding`, no
`operating_characteristics_finding`), and later does `df = df[required_current_schema_cols]` — which
**drops those two columns from `df` and overwrites both the local and Drive checkpoints with the
7-column version.**

Two consequences for the run-once:
1. **Every company lands BLANK `org_events_finding` + `operating_characteristics_finding` on the
   master** (10C reads them from `df`, which no longer has them). Scoring is unaffected —
   capability/reset/maturity all derive from `fit_brief_json`, which 10A preserves — but the master
   loses the Slice 3.7 operator-evidence text the master-completeness work deliberately carried.
2. **The checkpoint is silently truncated to 7 columns** → any disconnect after 10A makes
   `run_research_batch` treat every row as "incomplete" and **re-research the whole set.**

**Fix** — in the `## 10A` cell, replace its `required_current_schema_cols = [...]` with the
9-column list (matching Step 7):

```python
required_current_schema_cols = [
    "company",
    "date_researched",
    "funding_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "commercial_scale_finding",
    "org_events_finding",                  # add (Slice 3.7)
    "operating_characteristics_finding",   # add (Slice 3.7)
    "fit_brief_json",
]
```

The verification cell below also hard-stops on a blank `org_events_finding`, so the dry-run gate is
a backstop — but fix 10A so the hole never opens.

**Confirm the fix actually took — run this RIGHT AFTER the 10A cell.** A Colab edit that's typed but
not re-run, or made in the wrong cell, leaves the old 7-column list active in globals; the only
symptom is `df` coming back `(N, 7)` at 10B (observed twice during the verify pass). This gate catches
it at 10A instead of three cells later:

```python
# Run RIGHT AFTER the 10A cell.
assert {"org_events_finding","operating_characteristics_finding"} <= set(required_current_schema_cols), \
    "STOP: 10A still has the 7-column list — edit the 10A cell and re-run it."
print("✅ 10A fix active:", len(required_current_schema_cols), "cols | df shape:", df.shape, "(want (N, 9))")
```

The byte-exact corrected cell is also saved at `snippets/step_10A_fixed.py` (generated from the
notebook; only the two schema lines differ) if hand-editing keeps slipping. **This fix is
notebook-only** — `colab_workflow.py`'s mirror still has the stale 7-column 10A (post-regen
mirror-port tracked in `phase2_refresh_runbook.md`); don't trust or port the mirror's 10A until then.

---

## Cell-by-cell runsheet (by Colab title)

| Cell title (as shown in Colab) | Action | Expected output before moving on |
|---|---|---|
| **Step A - Get the branch into Colab** | **RUN** (the `main` version) | `git log` tip shows the slice4 merge on `main` |
| **Step B - Restart the runtime** | **RUN** | Runtime restarts; continue at Step 1 |
| **Step 1** | **RUN** | Quiet pip install, no errors |
| **Step 2 - Setup and Package Bootstrap** | **RUN** — confirm `WAIT_BETWEEN_WEB_SEARCHES = 120` | Prints the SEARCH_FAILED marker string + `False` |
| **Cel V1 - Checklist #1: import resolves** | **RUN** | `DEFAULT_MODEL: gpt-5.4-mini`, `run_research_batch importable: True` |
| **Step 3 / Step 4 / Step 5** | **RUN** | No output (define the shims) |
| **Cell V2 - Checklist 2: shims bind + smoke test** | **RUN** | `callable: True True True`, smoke `call_openai -> OK`, `fit brief parsed keys: [...]` |
| **[NEW] Clear ALL checkpoints** *(insert after V2)* | **RUN ONCE** — set `CONFIRM_CLEAR_ALL=True`, then back to `False` | `✅ Cleared N file(s). Both research_batches/ folders are empty.` |
| **Step 6 - Batch Config** | **DON'T RUN** (superseded by next cell) | — |
| **Cell V3 Setup** → replace contents with **[NEW] Batch config** | **RUN** | `Regen batch: <name> | companies: N` + per-company roster list — eyeball every query |
| **[NEW] Archive master** *(insert after V3)* | **RUN ONCE** | `✅ Archived <rows> rows × <cols> cols -> ...pre_v42_regen_<date>.csv` |
| **[NEW] Fresh empty master** *(insert after Archive)* | **RUN ONCE** | `✅ Fresh empty master: 0 rows × <cols> cols (schema preserved)` |
| **Step 7** | **RUN** (long; resumable) | `Researched this run: [all N]` · **`Failed: []`** · `df shape: (N, 9)` |
| **Cell V6** | **RUN** (tail forced-fail probe is harmless — one wasted call, no conflict) | All 6 findings `POPULATED` per company · **`✅ No SEARCH_FAILED markers`** |
| **Cell S3.5-A** | **RUN** | Per company: reset events + per-event opening + `reset_or_restructure_signal` |
| **Cell S3.5-B** | **DON'T RUN** (moot vs empty master; writes only a throwaway) | — |
| **Cell V4** | **RUN** | Per company: A1/A2/A3 + `katelynd_capability_fit_score` |
| **Cell V5** | **RUN** | Per company: funding stage / maturity + q1–q4 commercial |
| **Cell V7** | **RUN** | `CANDIDATE_FRAMEWORK_VERSION: V4.2` · suppressed demo → `P3 / True` |
| **10 - Validation summary** | **RUN** | `summary_df` built · no `WARNING: Some rows could not be parsed`, no `STOP` |
| **10A - Deterministic priority adjudication** | **EDIT (9-col fix), RUN, then the gate cell** | `PASS: …` + gate prints `✅ 10A fix active … df shape (N, 9)` — **(N, 7) here means the fix didn't take** |
| **10 - Validation summary** *(re-run — required by 10A)* | **RUN AGAIN** | `summary_df` rebuilt with adjudicated priorities, no `STOP` |
| **10B - Batch QA checks** | **RUN** | `QA passed. No issues flagged.` (if flags appear → review before continuing) |
| **10C - Slice 2/3.5/4 + engine-signal derivation** | **RUN** | `All slice columns present: True` · per-company maturity/commercial/reset/capability table populated |
| **Dry Run Setup** | **RUN** | `DRY_RUN = True …` |
| **12 - Add current batch to master** *(dry-run)* | **RUN** | `Master shape before: (0, …)` · `New companies added: [all N]` · **`Existing companies updated: None`** · `Step 12 master update complete` · no error |
| **[NEW] Verification cell** *(insert after the `## 12` cell)* | **RUN** → ◾ **HARD STOP #1** | **`✅ PASS — N rows, every company present, slice columns landed, no dups, read-back stable`** |
| **Gate 2** | **DON'T RUN — delete** (ZOE/Function hardcoded → IndexError) | — |
| **Real Write** | **RUN** → ◾ **HARD STOP #2** (flip once) | `DRY_RUN = False …` |
| **12 - Add current batch to master** *(scroll up, re-run once)* | **RUN ONCE** | Same prints; `Active master saved to: <real Drive master path>` |
| **[NEW] Verification cell** *(scroll down, re-run)* | **RUN** | **`✅ PASS`** — now reading the real master |
| **Final Read Back** | **DON'T RUN — delete** (`REAL_MASTER_PATH` NameError; stale paths) | — |
| **Old flow** (everything below) | **DON'T RUN** | Dashboard is a separate milestone |

**The 10 → 10A → 10 → 10B loop is real** — Step 10 runs twice on purpose. 10A rewrites the
adjudicated priority into `fit_brief_json`; the second Step 10 re-parses it into `summary_df`.

---

## The NEW / replacement cells

### Clear ALL research checkpoints (run once)
```python
# PRE-FLIGHT: clear ALL research checkpoints (decision 3 — every company researches fresh through
# item-8 budgets + guard). Wipes BOTH the local folder AND the Drive mirror, ALL files (not
# prefix-limited). ⚠️ Run ONCE at the start. Do NOT re-run after Step 7 begins — it destroys
# in-progress research. After the initial clear, set CONFIRM_CLEAR_ALL = False again.
CONFIRM_CLEAR_ALL = False    # <-- set True to arm the one-time clear; leave False = no-op
import glob, os
from pathlib import Path
from google.colab import drive; drive.mount("/content/drive")
local_dir = Path("research_batches")
drive_dir = Path("/content/drive/MyDrive/Job Search/Health Tech Research/research_batches")
if not CONFIRM_CLEAR_ALL:
    print("CONFIRM_CLEAR_ALL is False — nothing cleared. Set True to arm the one-time clear.")
else:
    removed = 0
    for d in (local_dir, drive_dir):
        if d.exists():
            for fp in glob.glob(str(d / "*")):
                if os.path.isfile(fp):
                    os.remove(fp); removed += 1; print("removed", fp)
    left = [p for d in (local_dir, drive_dir) if d.exists()
              for p in glob.glob(str(d / "*")) if os.path.isfile(p)]
    assert not left, f"STOP: files still present after clear: {left}"
    print(f"\n✅ Cleared {removed} file(s). Both research_batches/ folders are empty. Now set CONFIRM_CLEAR_ALL=False.")
```

### Batch config (replaces Cell V3; full set, no unlink)

`roster` accepts MIXED entries: `("Name", "short descriptor")` → query `"Name: descriptor"`; a bare
`"Name"`; or a full `{"company": ..., "research_query": ...}` dict for disambiguation / a known angle.
Each of the 6 searches injects `research_query` as company context and adds its own dimension focus,
so a short descriptor is enough — reserve full dicts for companies that need it. The closing loop
prints every company + truncated query so you can eyeball the roster before the run-once.

```python
# Batch config for the run-once regen. Supersedes Step 6 and the old Cell V3 (no checkpoint unlink).
# `roster` accepts MIXED entries — use whichever fits each company:
#   ("Name", "short descriptor")               -> query becomes "Name: descriptor"
#   "Name"                                     -> bare name (query = the name)
#   {"company": "Name", "research_query": "…"} -> full hand-tuned query (disambiguation / known angle)
BATCH_NAME = "v42_full_regen_clean_slate_20260622"     # <-- your regen batch name

roster = [
    ("ZOE", "personalized nutrition; ZOE 2.0 freemium / mass-market pivot"),
    {"company": "Function Health",
     "research_query": "Function Health: membership diagnostics / lab testing; funding stage, "
                       "valuation, total funding, founding year; paying members, pricing, retention; "
                       "recent leadership / restructuring; operational scaling strain"},
    # "Oura",
    # ("Company Name", "short descriptor"),
    # ... your full regen set, mixing forms freely ...
]

def _to_entry(item):
    if isinstance(item, dict):
        name = str(item["company"]).strip()
        query = (str(item.get("research_query") or "").strip()) or name
    elif isinstance(item, (tuple, list)):
        name = str(item[0]).strip()
        desc = str(item[1]).strip() if len(item) > 1 else ""
        query = f"{name}: {desc}".strip().rstrip(":").strip()
    else:                                   # bare string
        name = str(item).strip()
        query = name
    assert name, f"STOP: empty company name in roster entry: {item!r}"
    return {"company": name, "research_query": query}

companies = [_to_entry(x) for x in roster]

from pathlib import Path
research_batches_folder = Path("research_batches"); research_batches_folder.mkdir(parents=True, exist_ok=True)
batch_checkpoint_path     = research_batches_folder / f"{BATCH_NAME}_checkpoint.csv"
batch_raw_export_path     = research_batches_folder / f"{BATCH_NAME}_raw.csv"
batch_summary_export_path = research_batches_folder / f"{BATCH_NAME}_summary.csv"
assert companies, "STOP: add companies to the roster before running."
assert len({c['company'].strip().lower() for c in companies}) == len(companies), "STOP: duplicate company in roster."
print("Regen batch:", BATCH_NAME, "| companies:", len(companies))
for c in companies:
    q = c["research_query"]
    print(f" - {c['company']}: {q[:80]}{'…' if len(q) > 80 else ''}")
```

### Archive the master (insurance, run once)
```python
# PRE-FLIGHT: archive the live master BEFORE any clear. This is your rollback. Refuses to clobber a
# same-day archive, and refuses to archive an already-empty master (guards a reconnect re-run).
import shutil, pandas as pd
from datetime import date
from pathlib import Path
from google.colab import drive; drive.mount("/content/drive")
drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
real_master  = drive_folder / "health_tech_market_research_summary_MASTER.csv"
archive_path = drive_folder / f"health_tech_market_research_summary_MASTER_pre_v42_regen_{date.today():%Y%m%d}.csv"
assert real_master.exists(), f"STOP: no master at {real_master}"
assert not archive_path.exists(), f"STOP: archive exists, refusing to clobber: {archive_path}"
src = pd.read_csv(real_master)
assert len(src) > 0, "STOP: master already empty — did fresh-init already run? Do NOT archive empty over real data."
shutil.copy2(real_master, archive_path)
arc = pd.read_csv(archive_path)                              # read-back (Rule 5)
assert arc.shape == src.shape, f"STOP: archive {arc.shape} != source {src.shape}"
print(f"✅ Archived {arc.shape[0]} rows × {arc.shape[1]} cols\n   -> {archive_path}\n   This is your rollback. Keep it.")
```

### Fresh empty master (run once, after archive)
```python
# PRE-FLIGHT: header-only fresh master from archive.iloc[0:0] (same columns + order, ZERO rows).
# Real master is EMPTY from here until the real STEP 12 write; the archive is the rollback.
import pandas as pd
from datetime import date
from pathlib import Path
from google.colab import drive; drive.mount("/content/drive")
drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
real_master  = drive_folder / "health_tech_market_research_summary_MASTER.csv"
local_master = Path("health_tech_market_research_summary_MASTER.csv")
archive_path = drive_folder / f"health_tech_market_research_summary_MASTER_pre_v42_regen_{date.today():%Y%m%d}.csv"
assert archive_path.exists(), "STOP: run the ARCHIVE cell first."
fresh = pd.read_csv(archive_path).iloc[0:0]
fresh.to_csv(local_master, index=False); fresh.to_csv(real_master, index=False)
chk = pd.read_csv(real_master)                              # read-back (Rule 5)
assert len(chk) == 0 and "company" in chk.columns and list(chk.columns) == list(pd.read_csv(archive_path).columns)
print(f"✅ Fresh empty master: 0 rows × {chk.shape[1]} cols (schema preserved). Empty until the real STEP 12 write.")
```

### Verification (run after STEP 12, both dry-run and real)
```python
# === VERIFICATION — run right after STEP 12, on BOTH the dry-run and the real write. ===
# Reads the throwaway when DRY_RUN, the real master when not (no wrong-file risk). Hard-stops on
# real problems; WARNS (does not stop) on valid capability suppression / SEARCH_FAILED markers.
import pandas as pd, re
from pathlib import Path
from collections import Counter
from health_tech_research_agent.research_runner import is_search_failure
if DRY_RUN:
    target = Path("/content/DRYRUN_drive_master.csv"); label = "DRY-RUN — insert-path HARD GATE"
else:
    target = Path("/content/drive/MyDrive/Job Search/Health Tech Research/health_tech_market_research_summary_MASTER.csv")
    label  = "REAL WRITE — post-write read-back"
def _nk(v): t=("" if pd.isna(v) else str(v)).strip().lower(); return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9]+"," ",t)).strip()
m = pd.read_csv(target)
expected = [c["company"] for c in companies]; exp = {_nk(c) for c in expected}; got = {_nk(c) for c in m["company"]}
findings = ["funding_finding","payer_institutional_finding","outcomes_finding",
            "commercial_scale_finding","org_events_finding","operating_characteristics_finding"]
deterministic = ["company_maturity_read","reset_or_restructure_signal","capability_needs_review"]
stop, warn = [], []
if len(m) != len(expected): stop.append(f"row count {len(m)} != expected {len(expected)}")
if exp - got: stop.append(f"missing companies: {sorted(exp-got)}")
dups = [c for c,n in Counter(m['company'].apply(_nk)).items() if n>1]; stop += [f"dup rows: {dups}"] if dups else []
dcol = [c for c,n in Counter(m.columns).items() if n>1];              stop += [f"dup cols: {dcol}"] if dcol else []
for _, r in m.iterrows():
    co = r["company"]
    for c in deterministic:
        if c not in m.columns or str(r.get(c,"")).strip()=="": stop.append(f"{co}: blank {c}")
    for c in findings:
        v = str(r.get(c,"")).strip()
        if v=="": stop.append(f"{co}: blank {c}")
        elif is_search_failure(v): warn.append(f"{co}: SEARCH_FAILED in {c} — rider (a): inspect synthesis")
    cap = str(r.get("katelynd_capability_fit_score","")).strip()
    rev = str(r.get("capability_needs_review","")).strip().lower()
    if cap=="" and rev not in ("true","1","yes"): stop.append(f"{co}: blank capability score WITHOUT needs_review")
    elif cap=="": warn.append(f"{co}: capability suppressed (blank score + needs_review) — valid, confirm intended")
if not m.fillna("").astype(str).equals(pd.read_csv(target).fillna("").astype(str)): stop.append("read-back unstable")
print(f"[{label}] target={target.name} expected={len(expected)} rows={len(m)}"); print("="*72)
for w in warn: print("⚠️ ", w)
print(("\n❌ STOP:\n   " + "\n   ".join(stop)) if stop else
      f"\n✅ PASS — {len(m)} rows, every company present, slice columns landed, no dups, read-back stable.")
```

### Pause and resume — save research across a disconnect

Step 7 auto-mirrors the checkpoint to Drive after each company, but that copy lives in
`research_batches/` (which the clear-all cell wipes). The SAVE cell writes a separate, verified,
clear-proof backup OUTSIDE that folder; RESTORE reinstates it.

**To pause:** let Step 7 finish (`Failed: []`) → run SAVE → confirm `✅ Save verified complete` →
disconnect.
**To resume:** Step A → B → 1–5 → roster cell → RESTORE → re-run Step 7 (reuses everything, fast) →
continue to Cell V6 / Step 10. **Do NOT run Clear / Archive / Fresh-init on return** — the master is
already archived + emptied on Drive, and Clear would wipe the auto-mirror.

**SAVE (after Step 7, before disconnecting):**
```python
import shutil, pandas as pd
from pathlib import Path
from google.colab import drive; drive.mount("/content/drive")
from health_tech_research_agent.research_runner import is_search_failure
drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
local_ckpt = Path("research_batches") / f"{BATCH_NAME}_checkpoint.csv"
saved_path = drive_folder / f"{BATCH_NAME}_checkpoint_SAVED.csv"   # distinct name, NOT in research_batches/
assert local_ckpt.exists(), f"STOP: no local checkpoint at {local_ckpt} — has Step 7 finished?"
shutil.copy(local_ckpt, saved_path)
d = pd.read_csv(saved_path)
findings = ["funding_finding","payer_institutional_finding","outcomes_finding",
            "commercial_scale_finding","org_events_finding","operating_characteristics_finding"]
need = ["company","date_researched"] + findings + ["fit_brief_json"]
missing_cols = [c for c in need if c not in d.columns]
blanks  = [(r.get("company"), c) for _, r in d.iterrows() for c in findings+["fit_brief_json"] if str(r.get(c,"")).strip()==""]
markers = [(r.get("company"), c) for _, r in d.iterrows() for c in findings if is_search_failure(str(r.get(c,"")))]
print(f"Saved -> {saved_path}")
print(f"rows: {len(d)} | companies: {d['company'].nunique() if 'company' in d.columns else '?'}")
print("missing cols:", missing_cols or "none", "| blank findings:", blanks or "none", "| markers:", markers or "none")
print("\n✅ Save verified complete — safe to disconnect." if not (missing_cols or blanks or markers)
      else "\n⚠️ Gaps present — re-run Step 7 to fill before relying on this save.")
```

**RESTORE (on return, after the roster cell):**
```python
import shutil, pandas as pd
from pathlib import Path
from google.colab import drive; drive.mount("/content/drive")
drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
saved_path  = drive_folder / f"{BATCH_NAME}_checkpoint_SAVED.csv"
mirror_path = drive_folder / "research_batches" / f"{BATCH_NAME}_checkpoint.csv"
src = saved_path if saved_path.exists() else mirror_path          # prefer SAVED; fall back to the auto-mirror
assert src.exists(), f"STOP: no saved checkpoint (looked at {saved_path.name} and the auto-mirror)."
local_dir = Path("research_batches"); local_dir.mkdir(parents=True, exist_ok=True)
(drive_folder / "research_batches").mkdir(parents=True, exist_ok=True)
batch_checkpoint_path = local_dir / f"{BATCH_NAME}_checkpoint.csv"
drive_checkpoint_path = drive_folder / "research_batches" / f"{BATCH_NAME}_checkpoint.csv"
shutil.copy(src, batch_checkpoint_path); shutil.copy(src, drive_checkpoint_path)
df = pd.read_csv(batch_checkpoint_path)
print(f"✅ Restored from {src.name}: {len(df)} rows, {df['company'].nunique()} companies → local + mirror.")
print("Next: re-run Step 7 (reuses everything), then continue to Step 10.")
```

---

## ◾ HARD STOP #1 — insert-path dry-run gate (verification cell after the dry-run STEP 12)

**PASS (proceed to the flip) only if ALL:**
- STEP 12 finished **without raising** (its own all-or-nothing commercial-scale + review-field
  batch validations passed for every company);
- its printout shows **`New companies added` = the full set** and **`Existing companies updated: None`**;
- the verification cell prints **`✅ PASS`**. `⚠️` warnings (valid suppression / markers) are for
  your eyes, not a stop — but on a `SEARCH_FAILED` warning, do rider (a): open that company's
  `fit_brief_json` and confirm the synthesis didn't read the marker as evidence absence.

**STOP — do NOT flip — if:** STEP 12 raised, any company in `Existing companies updated`, or the
cell prints `❌`. Fix the cause (a `❌ blank` almost always means re-research that company), re-run
from the dry-run STEP 12. The real master is still empty; nothing is lost.

## ◾ HARD STOP #2 — the `DRY_RUN True→False` flip (one-way, run-once)

- **NEVER flip on the verify batch (ZOE/Function).** The real write is for the FULL company set only —
  thin verify-batch scores must not land in the trusted master. A verify pass STOPS at HARD STOP #1
  (`✅ PASS` on the dry-run); the dry-run already proves the insert path end-to-end. **If you did flip
  on the verify batch** (the master then holds those rows), re-empty it from the archive before the
  real regen — glob the `…pre_v42_regen_*.csv` archive, write `iloc[0:0]` to the master, confirm 0
  rows. The archive makes this a non-event; do NOT re-run Archive (it would clobber the original).
- Flip **only after** archive ✅ + fresh-init ✅ + HARD STOP #1 `✅ PASS` + **the full roster (not the verify set)**.
- Run `## Real Write` → `DRY_RUN=False` → **scroll up and re-run STEP 12 exactly once** → run the
  verification cell again (post-write read-back, now reads the real master).
- **⚠️ Do not run STEP 12 a third time.** The master is now populated; a further run converts clean
  INSERTs into UPDATEs.
- If the real write fails partway: **STOP, restore the master from the archive, investigate** — don't
  re-run blind.
- Optional: re-run `## Dry Run Setup` afterward to set `DRY_RUN=True` again (re-isolates any
  accidental future run).

## Tail click-order (the notebook layout isn't linear here)

1. `## Dry Run Setup` → confirm `DRY_RUN=True`.
2. **STEP 12** → writes throwaway.
3. **Verification cell** → ◾ HARD STOP #1. If `❌`, fix and repeat from 2.
4. If `✅`: `## Real Write` → `DRY_RUN=False`.
5. **Scroll UP, re-run STEP 12** once → real write.
6. **Scroll down, re-run the verification cell** → post-write read-back. Confirm `✅`.
7. Done — do not re-run STEP 12.

## Reconnect protocol (the run-once will likely span a disconnect)

- **First, is the session actually gone?** A disconnect sometimes reconnects to the same runtime
  (state intact) — check before rebuilding:
  ```python
  try: print("ALIVE — BATCH_NAME:", BATCH_NAME, "| df:", df.shape)
  except NameError: print("GONE — fresh runtime, full rebuild needed.")
  ```
- **Kernel restart** (Step B) keeps `/content` → checkpoint survives → re-run cells to rebuild
  globals; Step 7 resumes.
- **Full runtime recycle** wipes `/content` → rebuild in this order: **Step A → B → 1–5 → roster cell
  → RESTORE → Step 7** → then Step 10 → 10C → STEP 12. ⚠️ **Step B restarts the kernel and clears
  `BATCH_NAME`**, so the roster cell must come *after* B — and keep its `BATCH_NAME` unchanged so the
  SAVED/mirror files match.
- **The 10A fix survives a reconnect — it's a NOTEBOOK edit, not the repo.** Step A re-clones the repo
  (the stale `colab_workflow.py` mirror still has the 7-column 10A), but the regen path NEVER executes
  that mirror — you run the notebook's own cells, which Colab reopens with your 9-column fix intact.
  (Only old-flow STEP 20–27 read the mirror; you don't run them.) Do NOT re-derive 10A from
  `colab_workflow.py`. **Backstop:** after any reconnect, run the **10A gate cell** right after 10A —
  if Colab hadn't autosaved your edit before the disconnect (rare), the gate catches it before 10B.
- **Before Step 7, confirm the package/client loaded** (the roster cell + diagnostics don't load them):
  ```python
  try: print("Env ready — MODEL:", MODEL, "| run_research_batch:", callable(run_research_batch))
  except NameError: print("Env NOT ready — run Step A → B → 1-5, then the roster cell again.")
  ```
- **Restore vs. re-research** — check which Drive copies survived at full width (the bad-10A run
  truncates the auto-mirror; the SAVED copy survives because it's outside `research_batches/`):
  ```python
  import pandas as pd
  from pathlib import Path
  from google.colab import drive; drive.mount("/content/drive")
  drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
  want = {"org_events_finding", "operating_characteristics_finding"}
  for label, p in [("SAVED restore file", drive_folder / f"{BATCH_NAME}_checkpoint_SAVED.csv"),
                   ("Drive mirror checkpoint", drive_folder / "research_batches" / f"{BATCH_NAME}_checkpoint.csv")]:
      if p.exists():
          d = pd.read_csv(p); miss = want - set(d.columns)
          print(f"{'✅' if not miss else '❌'} {label}: {len(d.columns)} cols, {len(d)} rows" + ("" if not miss else f"  MISSING {sorted(miss)}"))
      else: print(f"• {label}: NOT FOUND")
  ```
  SAVED ✅ 9-col → RESTORE → Step 7 (reuses, fast). SAVED ❌ 7-col → skip RESTORE → Step 7 (re-researches).
- **One-time cells — NEVER re-run on a reconnect:** Clear, Archive, Fresh-init. Clearing would wipe
  restored research; the others are guarded but skip them. Keep `CONFIRM_CLEAR_ALL=False` after the
  initial clear. (With the 10A fix, the checkpoint stays 9-column, so a post-10A disconnect resumes
  instead of re-researching.)

## Dashboard

Stop after the post-write read-back (`✅`). Every dashboard cell lives in the post-`Old flow`
region; per `CLAUDE.md` the dashboard rebuild is its **own active milestone** (package-level rebuild
+ structural/field validation + completion read-back). Once the trusted master is verified, sequence
the dashboard as a separate step with its own gate.

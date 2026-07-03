# Dashboard Design — Katelynd's working tracker (career search)

**Status: DESIGN — LOCKED & reconciled; all design open items resolved (2026-07-03). Ready for Katelynd's
end-to-end read-through, then build scoping. No code yet.** This is the design contract for the dashboard
milestone (the second autonomous segment, after GATE 2). The only remaining §9 item (`dashboard.py` retire/
re-point) is a build-time task, not a design decision. It is being designed *with Katelynd* before any
build, per the "scope it with her before building" note in `COLLABORATION_CONTEXT.md` and the open dashboard
item in `MASTER_REDESIGN_SPEC.md` §6/§7. When this doc is locked, the build re-points/retires the old
`dashboard.py` against it.

> **What this dashboard is FOR (reframed 2026-07-03):** this is Katelynd's **career-search** working tool —
> finding a *role* at these health-tech companies. Not an investment tracker. That drives the vocabulary:
> statuses, warm intros, key contacts, "what makes this company desirable *for me*."

> **Visual reference (the wireframe we built together):** [`specs/dashboard_wireframe.html`](dashboard_wireframe.html)
> — open in a browser. Two views: the grid tabs (all companies · pursuit · contacts · segment radar) and the
> locked per-company detail view (§5a). Illustrative sample data; it is the render contract this doc describes.

---

## 1. Purpose & the jobs it does

When Katelynd opens the dashboard she is doing one of these:
- **Deciding who to pursue next** — scan companies by priority and pick targets.
- **Working her active pursuits** — update next steps, status, and her own notes on companies she's chosen.
- **Housing her manual deep-dive research** — HQ, what makes a company more/less desirable, and key contacts
  for a warm intro.
- **Seeing where she's thin by segment** — market coverage read across segments.

## 2. Architecture — two layers, split by write-authority

The dashboard is split by *who is allowed to write to it* — the same "authority flows one direction"
discipline the ledger already uses (scores write-once; only the decision block is human). See the concept
diagram shared in design chat (2026-07-03).

- **Automated, read-only (from the ledger).** Everything derived from `ledger.jsonl` is *fully regenerated*
  each run. Because it is never hand-edited, it cannot drift from the scoring ledger. This is the all-companies
  list and the segment radar.
- **Yours, persistent (your layer).** The `pursue` flag, the pursuit workspace notes, and the contacts are
  *your* write-region. The automation never overwrites them. Keyed by company name.

New companies from a later batch simply appear in the read-only all-companies list and stay there until *you*
promote them — so a new company never arrives pre-filled with (or clobbering) your manual info.

## 3. The living layer — how your notes survive a regeneration

Your inputs live in a **separate durable store keyed by company name**. On every regeneration the merge rule is:

1. **Ledger-derived columns refresh** from the current ledger (no drift — always the latest scored truth).
2. **Your columns are carried forward untouched** and re-joined by company. Human input always wins (Rule 6).
3. **Any column you added yourself is preserved**, even ones this design didn't define — the pipeline only
   ever writes the columns it generates; it never deletes a column it doesn't recognize. (You can add working
   columns over time without the next run wiping them.)

Two safety behaviors (this is an autonomous segment — "no one is watching the run", so problems must be
surfaced, never silently resolved):

- **Changed since you last looked** — if a company you're pursuing changed priority/segment (e.g. a re-review
  moved it P1→P2), the refresh shows the new truth *and* flags the change, so your view stays accurate without
  moving under you silently.
- **Dropped from the gated ledger** — if a company you have notes on is no longer in the reviewed ledger, it is
  NOT silently deleted; it is surfaced ("you have notes on X but it's no longer in the reviewed ledger") for you
  to resolve.

**Round-trip discipline (Rule 4/5).** Your edits happen in the Sheet; a step reads them back into the durable
store and re-merges, then reopens + validates the written artifacts before calling the run done (same read-back
discipline as the `cards.csv` → ledger round-trip).

## 4. Gate invariant (§1a — hard rule)

Only **GATE-2-reviewed** ledger entries reach the dashboard. Presence in the dashboard ⟹ the entry passed
GATE-2 review. The build must enforce this (an un-gated entry must never appear).

**Enforcement (decided 2026-07-03):** at gate-2 finalization, stamp **every** entry with a "reviewed" mark (not
just the ones Katelynd changed). The dashboard checks the stamp and refuses any unstamped entry. This is NOT
surfaced in the UI — the review flow already forces her to view and accept/adjust every company in the batch, so
in practice nothing reaches the dashboard un-reviewed; the stamp is a belt-and-suspenders safety net, and it
also anchors the "changed since you last looked" reference (§3). Build-time detail (touches the review-finalize
step, in the decision/metadata region — never the write-once scores).

## 5. Information architecture — the tabs

Four working tabs (below) plus a **per-company detail view** (§5a, "Tab 5") reached from any row. The grid tabs
stay lean; the heavy per-company detail lives in the detail view, never in grid columns (see §6).

### Tab 1 — All companies (read-only + one editable flag)
Every gated company, one row, sorted by final-priority rank. A **filter row on the top** (Sheets filter view)
so Katelynd can slice/hide at will (e.g. filter out P3s, or show only `pursue = TRUE`).
- **Editable / persistent:** `pursue` (checkbox). Ticking it TRUE (a) flags the row — usable as a filter here,
  and (b) promotes the company into the Pursuit workspace (Tab 2). This is the one editable column on this tab.
- **Main visible columns (always on):** `pursue` · company · final priority (tier) · **segment (label — its own
  filterable column)** · model · stage · FINAL · open-detail control.
- **Collapsed "tags & scores" group (one toggle):** the four taxonomy tag types as **separate columns**
  (subsegment · product model · distribution model · data input — so you filter by segment but still read the
  tags for context) + the five scores (bg · PMF · ARR · growth · strain) + key flag names. These are all SHORT
  values — one line each.
- **Long-form content does NOT live in columns** — the "why" (rationales, floor reasons + evidence, flag notes)
  and the raw research all live in the per-company **detail view** (§5a), reached by the open-detail control.
  This is what keeps rows short (decided 2026-07-03 — long text can't go in grid cells without bloating row
  height or truncating).

### Tab 2 — Pursuit workspace (your active pursuits)
Only companies where `pursue = TRUE`. This is where Katelynd works daily.
- **Ledger read-only (refreshed):** company · final priority · segment · model · stage · FINAL (+ the same
  collapsible full-card group as Tab 1).
- **Editable / persistent (your layer):**
  - `status` — dropdown (data validation), the career-search pipeline (see below).
  - `next step` — the next action.
  - `HQ location`.
  - `desirability notes` — what makes it more/less desirable for you.
  - `deep-dive notes` — your manual research.
  - `last updated` — auto-stamped when you edit (nice-to-have).
  - *+ any columns you add later* (preserved by the merge rule).

**Pursuit pipeline stages (status dropdown, approved 2026-07-03):**
`Researching` → `Seeking warm intro` → `Outreach sent` → `In conversation` → `Interviewing` → `Offer` /
`Passed`. (`Offer` and `Passed` are terminal.)

### Tab 3 — Contacts (keyed to company)
A separate tab so multiple contacts per company stay legible (decided 2026-07-03). One row per contact.
- `company` (dropdown of pursuit companies) · `contact name` · `title / role` · `their org` (may differ from
  the target company) · `relationship / how I know them` · `warm-intro path` (who can connect us) ·
  `email / LinkedIn` · `the ask / status` · `notes`.
- All editable / persistent (your layer).

### Tab 4 — Segment radar (read-only)
Answers "where am I thin by segment." One row per market segment (label), across all gated companies.
- `segment` · `# companies` · `# P0` · `# P1` · `# P2` · `# P3` · `# desirable (P0–P2)` · `# I'm pursuing` ·
  `coverage read`.
- **Coverage read (LOCKED 2026-07-03 — the original research-coverage intent is kept: "have I researched this
  segment enough?" A poor-background-fit segment legitimately has few high-priority targets, and that is a fine,
  honest read — not a gap to close):** `Strong` = ≥3 companies AND ≥2 in P0–P2; `Directional` = ≥2 companies
  AND ≥1 in P0–P2; else `Sparse`.
- Thin segments highlighted. A compact overall tier tally (P0–P3 counts) can sit at the top of this tab.

### Tab 5 — Company detail view (per company; the deep-read surface) — layout LOCKED 2026-07-03
Reached by clicking a company's open-detail control on any tab. Holds everything long-form so the grids stay
short. Two macro-sections:

1. **Scoring & decision (from the ledger).** The §B scores + the "why" per component, the three floors with
   pass/fail + evidence, flags with their notes, and — when present — your override + its reason shown beside
   the model's original tier (Function Health is the canonical case: model P3 floored on the 2×/yr cadence,
   human P1).
2. **Research evidence (from the research output, joined at render).** The heavy content, in **three nested
   legibility layers** (decided 2026-07-03, designed against the real research file — findings run 2K–12K chars
   each, ~40K per company, so raw dumping is not legible):
   - **Layer 1 — at a glance:** rendered as a **two-column card grid** — one bounded card per scoring lever, each
     with a header, a chip naming the score it drives, and ALL its evidence rows (key value emphasized). Density
     fix (2026-07-03): the goal is the SAME information as a flat list, laid out cleaner — never fewer fields.
     Structured, labeled fields from `fit_brief_json`, chosen so EVERY input that moves a score is visible here
     (see the §5b audit) —
     The cards are grouped into two rows that mean something (LOCKED 2026-07-03):
     - **the gates — a fail here caps priority at P3** (two cards):
       - **classification & channel** — who-uses / who-pays + the one-line basis (drives PATH Test A, the B2B
         floor) + the institutional / payer channel signal (drives PATH Test B for a B2B2C company);
       - **funding & maturity** — rounds → stage, total raised, resets (drives the agency gate).
     - **the score — background fit + PMF + strain = FINAL** (three cards):
       - **product market fit** — revenue/ARR, growth **with its source-mode / fence status** (single-source or
         counts-scale → fenced → capped + `data_gap`), paying-member scale, pricing, evidence quality (`q4`);
       - **background fit** — cadence / data-feedback-loop only (dropped 2026-07-03: evidence-source line +
         `a1`/`a3` — they restate the cadence point and aren't inputs);
       - **operator needed** — `a2` (the ONLY capability score that feeds §B — drives strain).
   Do NOT put the LLM's parallel *timing* judgment (`role_timing_assessment` — why-now, stage-timing,
   `timing_penalty`) on the glance: §B agency is factual (funding-stage + reset) only; that judgment is not an
   input (B1). `q1–q4` and outcomes are CONTEXT (trust cues), not inputs — see §5b.
   - **Layer 2 — verified facts & sources (collapsed):** `verified_facts_with_sources` each with its citation,
     plus `inferences` and `unverified_or_weak_claims`, tagged by **evidence confidence**
     (`verified` / `inference` / `weak`). This is where Rule 9 shows up — a "not found" reads as an upper bound,
     not a measured zero.
   - **Layer 3 — full detail (collapsed):** the 8 raw markdown findings (with primary-source links) PLUS the
     **complete structured fit-brief** — `classification_rationale`, `scale_signal_assessment` (institutional +
     outcomes signals with reasons), commercial `q1–q4`, full capability bases, role/timing, reset evidence.
     The findings alone are NOT enough: some score inputs live only in the structured brief, so the deepest
     layer must expose both — otherwise a score input is unreachable even here.

**Correctness rules for the research layer:**
- `fit_brief_json` ALSO carries the OLD retired synthesis scores (`thesis_fit_score`, `pmf_scale_score`,
  `priority_level`, `calibration_flag`). Surface the **evidence** fields, NOT those stale scores — the current
  §B scores come from the ledger only. Never render a retired fit-brief score as if it were current.
- **`priority_gate_preliminary_result` is OMITTED from the dashboard entirely (decided 2026-07-03).** It is the
  LLM's own *preliminary* priority guess in the fit-brief schema (`research_runner.py`), it never feeds the §B
  scorer, and it is NOT on the Gate-2 card. It is not score-driving, so omitting it does not break the
  completeness rule. Do not confuse it with `recommended_action` — the deterministic `accept / review_override /
  normal` routing that IS the Gate-2 card recommendation Katelynd reviewed and acted on (Rule 7: the LLM
  gathers evidence; deterministic rules decide).
- **`recommended_action` is DROPPED from the dashboard entirely (decided 2026-07-03)** — grid and detail. It is a
  Gate-2 routing artifact Katelynd has already acted on; `final_priority` + the "was P3" override marker +
  `provenance` already tell the story.

### 5b. Scoring-input audit (2026-07-03) — every score lever is reachable in the view

Traced each §B component to what it consumes and where that evidence lives, so a score can always be audited
against its evidence. `L1` = at-a-glance, `L3` = full detail. Result: Layer 1 was extended (Gaps 1–3) so no
score lever is buried.

| Score component | Consumes | Research source | Surfaced |
|---|---|---|---|
| Business model → PATH Test A (B2B floor) | who_uses / who_pays + basis | `fit_brief.business_model_classification`; evidence findings | **L1 (added)** + L3 |
| PATH Test B — engine alive (B2C) | revenue OR user-scale/paying-count OR growth | `commercial_evidence.*` | L1 + L3 |
| PATH Test B — engine alive (B2B2C) | real institutional channel | `payer_institutional_finding` + `business_model_type` | **L1 (added)** + L3 |
| Agency | funding_stage (rounds+IPO), ipo_status, resets | `maturity_evidence.*`, `reset_evidence` | L1 + L3 |
| Background fit | LLM over op-char+commercial+outcomes; loop | those 3 findings; `background_fit_basis` | L1 (cadence, loop) + L3 |
| ARR | revenue_or_arr + stage | `commercial_evidence.revenue_or_arr` | L1 + L3 |
| Growth | growth band / basis / **source-mode / fence** | growth read; `commercial_evidence.growth_signal` + finding | **L1 (source-mode added)** + L3 |
| Strain | capability a2 + operating-char text | `capability_evidence.a2` + `operating_characteristics_finding` | L1 + L3 |

**Verified NON-inputs (code-checked 2026-07-03 — do NOT present as scoring drivers):**
- `role_timing_assessment` (why-now/why-not, `likely_agency_level`, `stage_timing_fit`, `timing_penalty_applied`)
  — ZERO scorer references; §B agency is factual (funding-stage + reset) only, the LLM timing judgment is
  barred (B1). A vestigial parallel judgment.
- commercial `q1–q4` — feed only `derive_commercial_signal` → `derive_funding_failsafe`, which has **no callers**
  (unwired). No live effect on any score or flag. `q4` (evidence quality) is a trust cue = context.
- capability `a1` / `a3` — persisted but never read by the scorer; only `a2` feeds §B (strain). Context for bg.
- the LLM's `scale_signal_assessment` signals (institutional / outcomes) — the deterministic PATH reads the raw
  `payer_institutional_finding` itself, not the LLM's parallel signal. LLM signal = context.
- retired synthesis scores (`thesis_fit_score` etc.) and `priority_gate_preliminary_result` — never surfaced as
  scores (Rule 7: LLM gathers evidence, deterministic rules decide).

The standalone "research's own read" section was DROPPED (Katelynd, 2026-07-03) — not scoring-related and thinner
than the rest. The one context cue kept is `q4` evidence-quality, shown inside the product-market-fit card as a
trust cue for the numbers (never tagged as a lever).

## 6. Legibility — "not 100×50"

- **Grid tabs** keep a lean, always-visible main view; the "tags & scores" band is a **collapsible group**
  (column grouping in a Sheet / a show-hide toggle in the HTML view), hidden by default.
- The **heavy per-company content is not in the grid at all** — it lives in the detail view (§5a), which layers
  it (card-grid glance → collapsed facts → collapsed raw findings) so rows never grow.
- **Frozen** header row + company column on the grid tabs; a **filter row** on top for sort/slice; saved
  **filter views** (e.g. "P0–P1 only", "pursue = TRUE", "by segment").

## 7. Format & delivery

**Direction (2026-07-03): the HTML view is the real target, not the Google Sheet.** The per-company detail view
(§5a) — click a row → a layered, collapsible research record — is what makes "a lot of information, still
legible" actually work, and it is a *front-end* capability a Google Sheet can't do natively (a Sheet would need
a linked detail tab or grouped rows). Since that interaction is central to the design, we build toward an HTML
view rendered from the durable artifact.

- **Durable artifact:** the pipeline writes a versioned, resumable data artifact (CSV/JSON — Rule 4) from the
  ledger + the research join. The HTML view is a pure render of it; nothing is authored in the HTML that isn't
  in the durable store (your edits round-trip back to it — §3).
- **Google Sheet:** still available as an interim/export view of the same artifact for quick edits; it just
  won't carry the detail-view interaction.

## 8. Read API (for the build — from `ledger.py`)

- `read_ledger(path)` → list of entry dicts (fixture: `tests/fixtures/sample_ledger.jsonl`, 5 cases).
- Per entry: `final_priority(e)` · `provenance(e)` · `final_priority_code(e)` · `final_priority_rank(e)`;
  plus `e["scoring"]`, `e["gates"]`, `e["flags"]`, `e["decision"]`, `e["recommended_action"]`, `e["model"]`,
  `e["stage"]`.
- **Segment:** `e["taxonomy"]["segment"]` (controlled CODE) + `subsegment_tags` / `product_model_tags` /
  `distribution_model_tags` / `data_input_tags`. Join `taxonomy/market_segments.csv` (`segment_code →
  segment_label`) for display names — via `taxonomy.code_label_maps(taxonomy.load_taxonomy_tables(dir))`.
  All 14 segments (incl. `OTHER_REVIEW` = "Other", `FINTECH`, `ENTERTAINMENT_TECH`) are dashboard-visible.
- **Research join (for §5a):** the research output CSV — one row per company, columns `company` +
  8 findings (`funding_finding`, `payer_institutional_finding`, `outcomes_finding`, `commercial_scale_finding`,
  `growth_finding`, `paying_finding`, `org_events_finding`, `operating_characteristics_finding`) +
  `fit_brief_json`. The detail view's Layer 1/2 read the STRUCTURED `fit_brief_json` fields
  (`verified_facts_with_sources`, `commercial_evidence`, `maturity_evidence`, `capability_evidence`,
  `role_timing_assessment`, `reset_evidence`, `taxonomy_classification`); Layer 3 renders the 8 raw findings.
  Reference sample: `~/Downloads/v42_full_regen_clean_slate_20260622_full56_checkpoint_FINAL.csv` (54 companies).

## 9. Open items — resolutions (2026-07-03)

- [x] **Segment-radar thresholds** — KEEP the original company-count basis (research-coverage intent); a poor-fit
  segment legitimately has few high-priority targets. (§5, Tab 4.)
- [x] **Gate-2-complete signal** — stamp every entry "reviewed" at gate-2 finalization; not surfaced; safety net
  for §1a + anchors "changed since you last looked." (§4.)
- [x] **Workspace columns** — current seed set stands; no additions (extensible later via the merge rule).
  (§5, Tabs 2/3.)
- [x] **`recommended_action`** — dropped from the dashboard entirely. (§5a.)
- [x] **Round-trip mechanism (§3)** — CONFIRMED 2026-07-03: her editable layer lives in a durable CSV store (the
  source of truth); she edits a Sheet/file → a step syncs it back → the refresh merges by company name (her
  columns preserved, ledger columns refreshed) → read-back validated. A true edit-in-the-page auto-save needs a
  backend (later).
- [x] **Legacy `dashboard.py`** — DELETED 2026-07-03 (Phase 6): `dashboard_legacy.py`, `run_dashboard_refresh`,
  `test_dashboard_rebuild`, and `test_calibration_recompute` removed; the three `colab_workflow` old-dashboard
  cells marked RETIRED. Full suite green (639).

## 10. Build status & Colab run steps

**BUILT + LIVE-VERIFIED (2026-07-03).** Live Colab run on the regen-2 batch (54 companies) confirmed: finalize
stamped all 54, build produced the artifacts + HTML, segment labels resolved, the Google-Sheet round-trip works,
edits persist across re-runs (`seeded: False`, input-only), and the orphaned/changed safety signals fire. New
ledger-based engine, importable package functions (Rule 1), on branch `dashboard-design`:

| Module / function | Role |
|---|---|
| `ledger.finalize_gate2_review` / `finalize_gate2_review_dir` / `is_reviewed` | §1a review stamp (Phase 1/4a) |
| `dashboard.build_company_records` (+ `all_companies_view`, `segment_radar_view`, `research_payload`) | read engine, §1a enforced (Phase 2) |
| `dashboard.merge_user_layer` (+ `pursuit_view`, `contacts_view`, `next_workspace_store`) | living layer / merge (Phase 3) |
| `dashboard_html.render_dashboard_html` | interim HTML surface (Phase 5) |
| `dashboard.build_dashboard` | orchestrator — the one Colab entry point (Phase 4) |

~40 tests added; full suite green. The old module is `dashboard_legacy.py` (Phase-6 delete).

**Editable store — a NATIVE Google Sheet (decided 2026-07-03 after the live run).** An `.xlsx` opened from Drive
in Google Sheets is a *converted copy*, so the build never saw the real edits and the first design (an `.xlsx`
the build rewrote) lost them. Fix: the store is a **native Google Sheet** read/written via `gspread`
(`dashboard_gsheet`), and it is **INPUT-ONLY** — the build reads it and NEVER overwrites it; it seeds the two
tabs (`Workspace` / `Contacts`) once, when missing. Change detection lives in an engine-owned
`_user_snapshot.json`, not in the sheet. (The `.xlsx` path via `user_store_path=` still exists as a fallback.)

**Colab run steps** (append AFTER the existing `render_views` cell; `OUT`/`df` are the current gate-2 vars):

```python
# 0. install the dashboard build (branch) — re-run + restart to pick up fixes
!pip -q install --force-reinstall --no-deps "git+https://github.com/cleverturnip/health-tech-research-agent.git@dashboard-design"

# 1. FINALIZE the GATE-2 review — stamp every entry reviewed (run once, after apply_gate2_decisions)
from health_tech_research_agent import ledger
OUT = "/content/drive/MyDrive/gate2_batch_2026-07-02"
print(ledger.finalize_gate2_review_dir(OUT, reviewed_date="2026-07-03", reviewed_at_gate="gate2_batch_regen2"))

# 2. taxonomy for segment LABELS (pip wheel doesn't ship taxonomy/) — idempotent clone for the label join
import os
if not os.path.exists("/content/htra"):
    !git clone -q https://github.com/cleverturnip/health-tech-research-agent.git /content/htra

# 3. AUTHENTICATE + open/create your dashboard Google Sheet
from google.colab import auth; auth.authenticate_user()
import gspread, google.auth
gc = gspread.authorize(google.auth.default()[0])
try:    sh = gc.open("Health Tech Dashboard")
except gspread.SpreadsheetNotFound:  sh = gc.create("Health Tech Dashboard")
print("your dashboard sheet:", sh.url)

# 4. BUILD the dashboard (reads the finalized ledger + research df + your Google Sheet)
from health_tech_research_agent import dashboard
DASH_OUT = "/content/drive/MyDrive/dashboard_2026-07-02"
res = dashboard.build_dashboard(f"{OUT}/ledger.jsonl", research=df, out_dir=DASH_OUT,
                                gsheet=sh, taxonomy_dir="/content/htra/taxonomy")
print("entries:", res.entries, "| tally:", res.tally, "| seeded:", res.store_seeded)
print("changed/orphaned:", res.report, "| EDIT NOTES HERE:", sh.url, "| HTML:", res.html_path)

# 5. (optional) preview the HTML inline
from IPython.display import HTML, display
display(HTML(open(res.html_path).read()))
```

**Working loop:** open `sh.url` (your Google Sheet) → on the `Workspace` tab tick `pursue` + fill notes; on the
`Contacts` tab add contacts → re-run step 4 → the read-only views + HTML refresh, your edits are read straight
from the sheet and NEVER overwritten, and any priority/segment moves since last run show as "changed" banners.

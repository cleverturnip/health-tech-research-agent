# Master Redesign — Design Spec (RECONCILED v1)

**Status:** **RECONCILED v1 — ADOPTABLE.** Committed target; Phase-3 hardening builds against this. Reconciled
from the brainstorm draft against the committed docs via two read-only passes (the design reconciliation +
the 6-column decision-verification trace). NO scoring/master code is built by this doc.
**Pairs with:** `SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md` (the §B scoring system; FRAMEWORK v1.11) and the
two-gate autonomous flow in `COLLABORATION_CONTEXT.md`.
**Supersedes:** the V4.2/V1 data-completeness master (Option 2 — ONE master going forward); the
`candidate_priority` V4.2 engine *as the master's priority source*; the old six priority columns; the
"Commit 5 / Commit 6" plan.

---

## 1. The three documents (architecture) — Option 2

The pipeline produces three documents with **different change-frequencies and different write-authority**.
Data flows one direction; authority flows one direction: **Research → Master → Dashboard.**

| Document | Role | Who writes | Change frequency | Mutability |
|---|---|---|---|---|
| **Research output** | Immutable record of completed research; the durable home of ALL raw research data | Autonomous research segment | Append per batch (new companies only) | Append-only; never mutated |
| **Master (= the ledger)** | GATE-2 scoring-review ledger; source of truth for **PRIORITY** (not raw data) | Autonomous scoring segment (scores) + Katelynd (decisions) | Per batch (new co) + on manual priority/taxonomy change | Scores write-once; `decision` human-mutable w/ audit |
| **Dashboard** | Daily working tracker (radar, next steps, contact notes) | Autonomous dashboard segment + Katelynd (notes) | Continuous | Format-fluid; Katelynd's workspace |

**Option 2 (DECIDED): the ledger is the ONE master — it SUPERSEDES the V4.2/V1 data master entirely.** There
are NOT two documents. This is safe because the **raw research data lives durably in the research output**
(verified against `review.py:REQUIRED_RESEARCH_COLUMNS`: the 8 findings + `fit_brief_json` hold the full
payload — revenue, payer/institutional, capability evidence, taxonomy/role-timing source; every old-master
landed/computed column is **Rule-7 re-derivable** from `fit_brief_json`). The ledger therefore stores **no
raw research data of its own** — it is a **pure scoring-decision layer** over the upstream research output.

**Maps to the two-gate flow** (`COLLABORATION_CONTEXT.md`): GATE 1 (approve research set) → autonomous
research+score segment → **GATE 2 = the master review** → autonomous dashboard segment. Load-bearing
constraint: **zero user input between gates.** The master must therefore be **self-contained at GATE 2** —
every fact needed to judge accept-vs-override is IN the entry (the autonomous segment can't ask, and Katelynd
reviews once).

## 1a. LOAD-BEARING GATE INVARIANT (hard rule — enforce, don't leave implicit)

**Presence in the dashboard ⟹ the entry passed GATE-2 review.** Nothing reaches the dashboard un-gated: the
second autonomous segment runs ONLY on GATE-2-reviewed ledger entries. This invariant is what makes
`provenance` (§3.2) unambiguous — "no override = reviewed-and-accepted" holds ONLY because every dashboard
entry was reviewed. **The pipeline must enforce it** (an un-gated entry must never reach the dashboard); if
any path could skip the gate, provenance collapses and the invariant is void.

## 2. Re-scoring policy (write-once scores; human-mutable priority + taxonomy)

- A company is **scored once, on entry** (the batch that admits it). Scores are **never re-scored** by later
  batches or framework changes (stability over freshness for a decision ledger; human decisions never get
  clobbered by an unattended re-run).
- The master changes **only** via two write-paths:
  1. **Autonomous segment** appends new scored companies at GATE 2.
  2. **Katelynd** changes `human_override` (priority) and/or `taxonomy_override` — at GATE-2 review, OR later
     from a dashboard deep-dive — with a dated reason. **This changes priority/taxonomy only, NEVER the scoring.**
- **`framework_version` is stamped per entry and IS the staleness signal (declarative).** An entry scored
  against a superseded version is visible as such by its stamp; it is **NOT auto-re-scored**, and there is
  **no drift flag** — under write-once scores, drift cannot occur, so the old `calibration_flag` drift
  detection is moot and **RETIRED** (see §3.1).

## 3. Master-entry schema (one structured object per company)

Emitted by the autonomous scoring segment → rendered by the front end → frozen as the master record. The
**`decision` block is the only human-writable region**; within it, `history` is append-only.

### 3.1 Priority model — CLEAN, from scratch (replaces all six old columns)

The 6-column trace confirmed the old priority columns were **internal to master-creation with ZERO
external-permanent consumers** — so we design clean (no aliasing onto the retired locked-6). These names are
canonical now.

| Field | Meaning | Stored? | Replaces |
|---|---|---|---|
| `model_priority` | §B deterministic tier (FINAL → §B7 threshold) | **stored, write-once** | `priority_level` (source now §B, not synthesis/candidate) |
| `decision.human_override` | Katelynd's manual tier; `null` until set | **stored, human** | `reviewed_priority_level` |
| `decision.override_reason` | why (strongly-prompted by the front end, NOT blocked) | **stored, human** | NEW (old model had none) |
| `decision.taxonomy_override` (+`_reason`) | human B2B/B2C/B2B2C override (Rule 6) | **stored, human** | NEW in the ledger (`_is_human_taxonomy_override` exists today) |
| `decision.history` | append-only dated decision trail `[{date, field, from, to, reason}]` | **stored, append-only** | NEW (old had only a batch-level change log) |
| `framework_version` | per-entry stamp; ALSO the staleness signal | **stored** | `candidate_priority_framework_version` + `calibration_flag` |
| `final_priority` | resolved: `human_override` if present, else `model_priority` | **DERIVED on read** | `final_priority_level` |
| `provenance` | OVERRIDE-ONLY: `human-overridden` if `human_override` set, else `model-accepted` | **DERIVED on read** | `priority_source` (inference RETIRED) |
| `final_priority_code` / `final_priority_rank` | tier letter / sort by FINAL | **DERIVED on read, NOT stored** | `final_priority_code` / `final_priority_rank` |

`final_priority_code` = the tier letter (the tier IS the code; domain is now **P0–P3**, no P4). `final_priority_rank`
= sort by FINAL score (finer ordering than the old 5-bucket rank). Both derive on read from the tier + FINAL —
**not stored** (no consumer needs a stored letter/rank; `dashboard.py` already re-derives the code today).

**RETIRED as scars — do NOT port:** the `priority_source` inference (`determine_priority_source`), the
`decision_priority` duplicate alias, the colab auto-seed of `reviewed_priority_level` (the §10 poison), the
`legacy_*_before_p0_migration` backup columns, the `step_12C` one-time migration script, and the
`calibration_flag` drift detection.

### 3.2 The two resolutions (decided)

- **`calibration_flag` → `framework_version`.** Under WRITE-ONCE scores, calibration drift between re-scores
  cannot occur, so a drift flag is moot. `framework_version`-per-entry surfaces staleness **declaratively** —
  a stale entry is visible by its version; no re-score, no flag. Drift detection RETIRED.
- **`provenance` = OVERRIDE-ONLY, leaning on the GATE INVARIANT (§1a).** We do **NOT** track "affirm = amend."
  Rationale: nothing reaches the dashboard without passing GATE-2 review (§1a), so "was this reviewed?" is
  ALWAYS yes for dashboard entries — storing affirmation is redundant. `provenance` records only the thing
  that VARIES: did Katelynd **override** (changed tier + reason) or **accept** (kept the model tier). Absence
  of override ⟹ reviewed-and-accepted, **guaranteed by the gate**.

### 3.3 Rule-6 / Rule-8 clause (hard — state explicitly)

The `decision` block edits **PRIORITY + TAXONOMY only** (Rule 6: human-reviewed priority AND taxonomy
overrides always take precedence). **Scores and research data are write-once and NEVER hand-edited** (Rule 8:
incorrect outputs are fixed via upstream regen / improved logic, never by editing the ledger). Editing a
score or a research fact in the ledger is forbidden; editing a priority/taxonomy *decision* is the ledger's job.

### 3.4 The entry (JSON-per-entry; format-agnostic — renders to card, table row, or CSV)

```jsonc
{
  "company": "function health",
  "batch_id": "batch_03_2026-06-30",
  "framework_version": "v1.11",       // per-entry; the staleness signal (§2)
  "date_scored": "2026-06-30",

  // IDENTITY / CONTEXT (from research output, for judging — re-derivable, not authored here)
  "model": "B2C",
  "stage": "series-b",
  "stage_basis": "Series B $298M, Nov 2025 ($2.5B val)",
  "one_liner": "Comprehensive biomarker lab testing, consumer membership",

  // DETERMINISTIC SCORING (write-once, never mutated, never hand-edited — Rule 8)
  "scoring": {
    "bg_fit": { "score": 4, "loop": false, "rationale": "2x/yr lab + results review — episodic, not a loop" },
    "pmf": { "score": 10,
             "arr_level": { "score": 10, "basis": "$298M ARR @ SerB → top of Scale A" },
             "growth":    { "score": 10, "basis": "+450% YoY (Sacra)" },
             "rationale": "Elite revenue scale + explosive growth for stage" },
    "strain": { "score": 2, "strength": "moderate", "rationale": "Rapid scale; structural" },
    "final_score": 16,
    "floor_rule": { "passed": false, "reason": "bg_fit 4 ≤ 4 → fails bg_fit>4 gate" }
  },

  // GATES
  "gates": {
    "path":   { "passed": true, "detail": "B2C consumer end-user; engine alive" },
    "agency": { "passed": true, "detail": "Series B → in-window" },
    "b2b_floor": false
  },

  // MODEL OUTPUT + REVIEW ROUTING (write-once)
  "model_priority": "P3",                       // §B FINAL → §B7 threshold
  "recommended_action": "review_override",      // accept | review_override | normal
  "override_candidate": true,

  // FLAGS (controlled vocabulary; surfaced, never buried)
  "flags": [
    { "type": "override_candidate", "severity": "info",
      "note": "Floor-fail is CORRECT (2x/yr cadence); flagged unicorn for revenue+complexity" }
  ],

  // DECISION — the ONLY human-writable region (priority + taxonomy; history append-only)
  "decision": {
    "human_override": null,            // Katelynd's manual tier; null until set
    "override_reason": null,           // strongly prompted by the front end, NOT blocked
    "taxonomy_override": null,         // human B2B/B2C/B2B2C (Rule 6); null until set
    "taxonomy_override_reason": null,
    "decided_date": null,
    "decided_at_gate": null,           // "gate2_batch03" | "deepdive_2026-08-12"
    "history": []                      // append-only: [{date, field, from, to, reason}]
  }

  // DERIVED ON READ (NOT stored):
  //   final_priority      = decision.human_override ?? model_priority
  //   provenance          = decision.human_override != null ? "human-overridden" : "model-accepted"
  //   final_priority_code = tier letter of final_priority   (P0–P3)
  //   final_priority_rank = sort key = FINAL score
}
```

### 3.5 Flag controlled vocabulary (emitted by the pipeline, from the project's work)
`override_candidate` · `fence_leak` · `under_extract` · `data_gap` · `evidence_thin` · `leak_discounted`
· `b2b_floor` · `agency_floor` · `stage_low_confidence`. Each: `{ type, severity (info|warn), note }`.

## 4. The GATE-2 review packet (what the front end hands Katelynd)

> *Absorbs the Gate-2 review-surface scoping formerly in `PHASE3_HARDENING_PLAN` §5 (that file is archived).
> Its two corrections to this section — the uniform ledger (Correction 1) and the precise card-eligibility
> predicate (Correction 2) — are folded in below.*

**EXTENDS the existing review packet** (`review.py:build_review_packet`) — it is a superset, not a rewrite:
the current flat summary becomes the summary table; cards + floor-reasons + routing are added on top. The
summary's score columns change to the §B set (bg_fit / pmf / strain / FINAL), replacing the old synthesis
scores. **Honor Rule 3:** CSV outputs are the human review surface — the summary table + cards are CSV
artifacts Katelynd reviews directly (the eventual front end renders them, but must not route decisions away
from the reviewed CSV artifacts). *(Google Sheets is retired — superseded by CSV.)*

The **master/ledger is UNIFORM — every company is a full scored + stored entry, gate-floored or not** (same
schema, same scoring). Floor status changes only HOW a company is surfaced at Gate 2, never WHETHER it is
scored or stored — do NOT carry the spike's "floor-before-scoring → em-dash the components" LLM-call shortcut
into the ledger (components may be computed lazily for cost, but the persisted entry holds the full scored
entry for every company). The **review packet** is a render-time VIEW over those entries, differentiated by
altitude (cards are never hand-built):
- **Cards** — the deliberate accept-or-override surface. Eligibility is a render-time predicate:
  **`card ⟺ model_tier ∈ {P0, P1, P2} OR override_candidate == true`** — NOT "all floor-eligible companies"
  (a floor-PASS company that lands at model-tier P3 gets no card; an **override candidate always gets a card
  even at model-tier P3** — e.g. Function Health, P3-by-rule but a P1-override candidate). Each card carries
  the scores + per-component rationale, flags (with severity, §3.5), the recommended tier and where it
  diverges from the rule, and `[accept] / [override → ___]` controls.
- **Summary table (top)** — every company, scannable: company · model · stage · tier · FINAL · key flag.
- **Gate-floored → one-line floor reason in the summary table, NO card.** (e.g. "medically home — B2B floor,
  enablement platform"; "hinge — agency floor, public.") Katelynd's **chance to catch a wrong floor** —
  glance-and-confirm, reverse if incorrect. The floor is reviewable, not a black hole.

### Review routing (`recommended_action`) makes a big batch reviewable in one sitting
- `accept` — clear tier (strong P0, clear P3-floor) → bulk-approvable.
- `review_override` — override candidates + borderline → Katelynd's real attention.
- `normal` — confirm.

### Override reason
**Strongly prompted, not blocked.** The front end nudges for a reason but saves without one (Katelynd's own
rigor). The field is present regardless; `history` still appends the change.

## 5. §B scoring supersedes the candidate_priority V4.2 engine (as the master's priority source)

- The **§B scoring system** (`SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`) is the master's priority source —
  `model_priority` = §B FINAL → §B7 threshold. The old **"Commit 5: wire `candidate_priority` →
  `final_priority_level`" plan is OBSOLETE** (`candidate_priority.py:485` already notes it never writes
  `final_priority` — "Commit 5 held"). **Commit 5 and Commit 6 are obsolete.**
- `candidate_priority` **retires**, or **recasts as GATE-1 candidate discovery** with its own
  `candidate_priority_level` — a separate concern ("does a company merit *research*?") from the ledger's
  priority ("does a *researched* company merit pursuit?"). It does NOT write the master's priority.

## 6. Open / deferred
- Dashboard schema — separate doc; format-fluid by design (Katelynd iterates).
- Exact front-end render + controls — front-half track (later/unstarted per COLLABORATION); must honor Rule 3.
- Storage/format of the master (repo artifact / CSV) — decide at build time; schema is
  format-agnostic (JSON-per-entry renders to card, table row, or CSV equally).
- Whether `recommended_action: accept` allows true bulk-approve or still one-click-per-company.

## 7. Phase-3 migration punch-list (code to re-point / retire — built later, not now)
- `priority.py` — **rewrite** to the clean model (§3.1); derive `final_priority`/`provenance`/code/rank on
  read; delete `determine_priority_source` (inference), `decision_priority`, `build_calibration_flag`.
- `master_update.py` — **re-point** to write ledger entries (not the wide data-master CSV); keep the
  transactional backup/read-back/rollback discipline; extend taxonomy-override protection into the decision block.
- `reland.py` — **retire** (taxonomy + role/timing live in `fit_brief_json` / the ledger's context block;
  no wide master to land into).
- `dashboard.py` — **rebuild** to read the ledger (`final_priority` + flags); built LAST; enforce the gate
  invariant (only gate-2-reviewed entries).
- `candidate_priority.py` (+ `candidate_priority_reference_spec.md`) — **retire or recast** as Gate-1 discovery.
- `decisions.py` — **reconcile** the APPROVE/HOLD/REJECT decision flow into the ledger decision-block writes.
- `review.py` — **extend** to cards + summary + routing (§4), emitting CSV artifacts; **`google_sheets.py` retires** (Sheets superseded; Rule 3 → CSV).
- `colab_workflow.py` — the STEP-12 / 12B master-build loops, the summary→master parse, and the dashboard/
  market-map cells — **re-point/retire** as the package functions are.
- `maintenance/step_12C_priority_label_migration.py` — **delete** (one-time migration; no legacy labels under the ledger).

---

*RECONCILED v1 — adoptable. Committed doc-first as the target; Phase-3 hardening builds the §B scorer that
populates the ledger's scores, then the ledger, then the dashboard. The spec is the contract; the spike is not
the system.*

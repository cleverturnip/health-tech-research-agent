# Front-End Phase 2 — In-App GATE-2 Review (build spec)

**Build contract for Phase 2 of the front-end milestone.** *Build status + what's next live ONLY in
`COLLABORATION_CONTEXT.md` § Status & roadmap (not here — avoids drift).*

**Reuses (does not re-design):**
- **The card = the dashboard detail view** (`dashboard_html._detail_html`) — LOCKED with Katelynd 2026-07-04:
  the GATE-2 review card IS the exact per-company detail view we built for the dashboard (SCORING & DECISION +
  the gates/score evidence cards), **plus a priority decision control**. No new card design.
- `ledger.apply_decisions` / `finalize_gate2_review` — the tested priority-only decision + §1a stamp logic
  (Rule 6/8: sets `human_override` + `override_reason` + history; never scores/gates/`model_priority`).
- `dashboard.build_company_records` — built with `require_reviewed=False` so **un-finalized** entries render.
- `webapp/gsource.py` — the Google source (Drive read); Phase 2 adds a Drive **write** path.

Pairs with `MASTER_REDESIGN_SPEC.md` §4 (the GATE-2 render contract + card layout + routing) and
`FRONT_END_DIRECTION.md` (phase order).

---

## 1. What Phase 2 delivers

Review the **pending** companies (a batch that's been researched + scored but **not yet finalized**) as full
cards inside the app, and decide priority per company — **Accept** the model's tier, or **Override** → pick a
tier + reason — saved durably to the ledger, then **Finalize** → they flow into the dashboard. Replaces editing
`cards.csv`. (Nothing to review until a new batch lands unfinalized in the ledger; the current ledger is all
finalized, so `/review` is empty until then.)

## 2. The card — dashboard detail view + one added control (LOCKED)

Render each pending company with the **exact** dashboard detail view (`_detail_html`). Add **one** thing: the
**priority decision control** —
- **[ Accept `<model tier>` ]** (keep the model's priority), or **[ Override → pick P0 / P1 / P2 / P3 ]** + a
  **reason** (strongly prompted, NOT blocked — Katelynd's own rigor, `MASTER_REDESIGN_SPEC.md` §4).
- The model's **recommendation** (`recommended_action`: `accept` / `review_override` / `normal`) shown **beside**
  the control so it triages attention while deciding.
- Katelynd never edits a score or un-floors a company (Rule 8); disagreement with a floor = a priority bump
  (Function Health is the canonical case). Taxonomy override is NOT a routine card control (MASTER §4).

## 2a. Recommendation write-up — source fields (2026-07-04)

The card shows a **"why this recommendation"** block. The recommendation (`recommended_action`) is **deterministic**
(Rule 7 — the model routes, it does not reason in prose), so the write-up is **assembled from the drivers already
in the ledger**, not a separate LLM narrative:
- `entry["recommended_action"]` — the routing verdict (`accept` / `review_override` / `normal`).
- `entry["flags"][].note` — each triggered flag's note (e.g. `override_candidate` → "documented priority-override
  candidate"; `low_score_floor` → "Floor rule … → capped at P3 …"). These notes are the closest thing to a written
  rationale (pipeline-authored, per the §3.5 flag vocabulary in `MASTER_REDESIGN_SPEC.md`).
- `entry["scoring"]["floor_rule"]["reason"]` — the floor explanation when a floor fired.

**There is NO dedicated LLM-prose "recommendation rationale" field today** (the recommendation is deterministic).
If a true LLM narrative is wanted, that is a **pipeline addition** (a new research/scoring field) — Phase-3 /
doc-first, not a render change. `review._recommendation_html` renders the assembled block.

**Per-company review state (green rows):** a decision stamps `decision.decided_date` on that company (even an
unchanged Accept) — the "you reviewed this" marker that turns its list row green. The §1a `decision.reviewed_date`
is still stamped only by **Finalize** (which admits the batch to the dashboard). Two distinct stamps.

## 3. Data flow + persistence

1. The app reads `ledger.jsonl` from the **Drive data folder** (same folder the dashboard reads). **Pending** =
   entries where `ledger.is_reviewed(entry)` is False.
2. A decision → `ledger.apply_decisions` (priority-only + history) → the updated `ledger.jsonl` is written **back
   to Drive** (a targeted `files.update` on the existing file, **read-back verified** — Rule 4/5).
3. **Finalize** → `ledger.finalize_gate2_review` stamps EVERY reviewed entry → written back to Drive. Only then
   does the dashboard admit them (§1a gate invariant).
4. The three CSV views (`cards` / `summary_table` / `master_full_export`) are re-rendered and uploaded back to
   Drive too, so the Rule-3 CSV surface stays in sync (the in-app review is now the primary decision surface;
   the CSVs remain a read-only export/record).

## 4. Drive write — narrow revision of P1.5 (2026-07-04)

- The service account needs **Editor** on the **"HTRA Dashboard Data" Drive folder** (was Viewer). Write session
  uses the `drive` scope (actual access still bounded by what's shared with the account); a **targeted
  `files.update`** on the existing `ledger.jsonl` (keeps the same file id the dashboard reads), read-back verified.
- This mirrors the Phase-1 pursue→Sheet write (§8a). Reads still use the read-only scope.
- **Katelynd's one setup step:** change the Drive **data folder** share for `dashboard-reader@…` from Viewer → Editor.

## 5. App surface (routes, gated by login)

- `GET /review` — index of **pending** companies: company · model · stage · model priority · recommendation ·
  key flag · decided?, sorted by recommendation (review_override first), with progress (n of m decided).
- `GET /review/{company}` — the full card (dashboard detail view) + the decision control.
- `POST /review/decision` `{company, decision: accept|override, tier?, reason?}` → apply + write to Drive →
  return to the index (or next pending).
- `POST /review/finalize` → stamp all reviewed + write to Drive → redirect to the dashboard.
- Dashboard (`/`) and review (`/review`) coexist with simple nav between them.

## 6. Rules honored (guardrails)

- **Rule 3** — decisions land in the durable **ledger** (not a spreadsheet).
- **Rules 6/8** — priority + reason ONLY; scores / gates / `model_priority` never edited; overrides win.
- **Rules 4/5** — every ledger write is durable + **read-back-verified** before it's "done".
- **Reuse the engine** — `apply_decisions` / `finalize_gate2_review` / `_detail_html`; the web layer adds routes,
  the decision control, and the Drive write path — no new decision/scoring logic.
- Public repo — no secrets/data committed.

## 7. Out of scope

GATE-1 + the long research run + progress/notification (Phase 3); taxonomy override as a routine control
(priority bump only); moving the research/scoring producer off Colab (Phase 3 — Phase 2 reviews whatever landed
unfinalized in the Drive ledger).

## 8. Build order

1. **Drive write in `gsource`** — `update_file` (files.update) + a decided-ledger write flow (download → apply →
   upload, read-back). Tests with a fake session.
2. **Review logic** — pending selection (un-reviewed records), the decision-apply-to-Drive + finalize flows.
3. **Review UI** — `/review` index + card view (reuse `_detail_html`) + the decision control + `POST` routes.
4. **Tests** green; then **live-verify** on the next real batch (after Katelynd grants folder Editor).

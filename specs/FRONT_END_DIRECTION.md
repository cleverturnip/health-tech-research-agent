# Front-End Direction — the full-flow app

**DIRECTION contract — decided with Katelynd 2026-07-03.** This is the direction contract for the front-end
milestone: the hosted app that houses the two-gate flow end-to-end and replaces the hand-run Colab cells.
*Build status + what's next live ONLY in `COLLABORATION_CONTEXT.md` § Status & roadmap (not here — avoids drift).* It records *what we're building and in what order*; it does **not** yet specify the
Phase-1 build (that's the next doc) and it does **not** lock any LLM-facing prompt wording (designed together
before build, per `CLAUDE.md`).

**Builds on / pairs with:**
- `COLLABORATION_CONTEXT.md` — the North-Star two-gate flow + the "front end + the data system that houses the
  flow so it runs autonomously" milestone this realizes.
- `DASHBOARD_DESIGN.md` §7 — the front end **swaps the presentation surface but reuses the dashboard engine
  unchanged**; it renders the durable artifact (`dashboard_records.json`), authoring nothing that isn't in the
  durable store. This doc extends that principle from the dashboard to the *whole flow*.
- `MASTER_REDESIGN_SPEC.md` §4 (GATE-2 render contract, `cards.csv` → `apply_gate2_decisions`) and §5/§7
  (`candidate_priority` "recast as GATE-1 discovery").

---

## 1. What we're building (one sentence)

A **hosted, private (login-gated), desktop-first web app** that runs the full two-gate research flow —
GATE 1 → autonomous research + scoring → GATE 2 → dashboard — with the scored **`ledger.jsonl` as the shared
brain** under every surface, progressively replacing the Colab cells.

## 2. The flow, inside the app (the four surfaces)

1. **GATE 1 — conversational candidate discovery.** You talk to an LLM that reads your **existing researched +
   scored companies (the ledger) as reference**, so it proposes new candidates grounded in your revealed
   preferences ("here's who scored well for you → who should you look at next?") rather than starting cold. You
   approve/edit the candidate list. *(Rule-compatible: the LLM **proposes** who to research and gathers
   evidence; the deterministic pipeline still does the scoring, and you still approve the list — evidence vs.
   decision stays separated. Prompt wording designed together before build — highest-stakes change.)*
2. **Autonomous research + score run.** On approval, the run kicks off on the hosted backend and executes for
   **30 min–several hours, independently** — you close the laptop and it keeps going, resuming from the last
   durable state after any interruption (Rule 4). You get a **live progress page you can close and reopen**,
   **plus a notification** when the run finishes and GATE 2 is ready.
3. **GATE 2 — fully in-app review.** The locked card layout (`MASTER_REDESIGN_SPEC.md` §4): per-company cards
   with scores, floors, flags, evidence, and the **priority Accept / Override + reason** control. Decisions are
   written **durably to the ledger** via `apply_gate2_decisions` (priority only; scores never hand-edited;
   history appended; your overrides always win — Rules 6/8).
4. **Dashboard — hosted working tracker.** The company list + per-company detail **cards render in-app,
   read-only** from `dashboard_records.json`. Your **input layer stays in a Google Sheet** — contacts and
   pursuit/priority notes — because that's easiest for you to edit (this is exactly the engine's existing
   *input-only* user-store round-trip, `DASHBOARD_DESIGN.md` §3/§10 — not a compromise). A **Refresh button**
   re-reads your Sheet + the latest scored data and rebuilds the view on the spot.

## 3. Locked direction decisions (with the judgement behind each)

| # | Decision | Rationale (Katelynd, 2026-07-03) |
|---|---|---|
| D1 | **Scope = the full flow** (GATE 1 + GATE 2 + dashboard), not just a viewer. | It's the app that replaces running Colab cells. |
| D2 | **Hosted**, with a background job runner. | The research run must go for hours **independently**; Colab can't do that reliably (it was always the dev shell, Architecture rule 2). Hosting is effectively *required* by the long-independent-job constraint, not optional. |
| D3 | **Private, behind a login.** | Holds private career research, priority calls, and personal contacts on a public URL. |
| D4 | **Desktop-first.** | It'll open on a phone, but the dense company table + cards are built for a wide screen; no small-screen optimization now. |
| D5 | **GATE 1 = conversational, grounded in the ledger.** | Talking to the LLM is the ideal; the already-scored set is the best base to find adjacent companies from. |
| D6 | **GATE 2 = fully in-app editing**, decisions written to the ledger. | This is the spreadsheet-editing pain point to remove. |
| D7 | **Dashboard = in-app cards (read-only) + Google-Sheet input layer + Refresh button.** | Cards need an app; contacts/notes are easiest in a Sheet. Maps onto the existing input-only architecture. |
| D8 | **Long run = live progress page (closeable/reopenable) + notification when GATE 2 is ready.** | "Launch it and walk away" is the whole point of hosting. |

## 4. Build order (phasing)

Chosen so a real hosted tool exists early and the hardest migration (the long job off Colab) comes last, once
the surfaces around it exist. "Static vs. interactive" is resolved by *order*, not as a fork.

- **Phase 1 — Hosted dashboard first.** Host what's already built (the dashboard engine + its
  `dashboard_records.json`) behind a login, with the Refresh button. Proves the hosting/deploy/auth pipeline
  end-to-end with the lowest-risk piece. Editing stays in the Google Sheet.
- **Phase 2 — GATE 2 review in-app.** The interactive card review + priority Accept/Override, writing to the
  ledger.
- **Phase 3 — GATE 1 + the long-run orchestration.** Conversational discovery + kicking off / progress /
  notification for the multi-hour research+score run as a background job. **This is where Colab gets replaced
  as the engine** — the hardest part, done last.

## 5. Non-negotiables carried in from the rules

- **Durable + read-back on every write (Rules 4/5).** A save isn't "saved" until it's reopened and confirmed;
  the long job resumes from the last durable state after any interruption.
- **GATE decisions land in the durable ledger (Rule 3).** The app renders durable artifacts and routes
  decisions back into `ledger.jsonl` — never a non-durable channel.
- **Human overrides always win; scores never hand-edited (Rules 6/8).** GATE-2 in-app editing changes
  **priority only**.
- **LLM gathers/proposes; deterministic rules + your approvals decide (Rule 7).** GATE 1 proposes candidates;
  scoring stays deterministic; the two gates are the only human input.
- **Reuse the engine (`DASHBOARD_DESIGN.md` §7).** The backend calls the existing tested functions
  (`build_dashboard`, `apply_gate2_decisions`, `research_runner`, the user-store round-trip); the new work is
  the web + hosting layer, not a new data model.
- **Prompt wording designed together before build.** GATE-1 discovery wording is the highest-stakes change.

## 6. Cost (order-of-magnitude)

Data volume is a non-factor (≤200 companies, likely ≤100). Hosting the app + a small always-on background job
runner is roughly **coffee-a-month** — the long research run is I/O-bound (waiting on the OpenAI API), so it
runs fine on a small, cheap instance; the hours don't cost much. A modest *paid* tier is realistic because
free/hobby tiers sleep or cap runtime, which fights a multi-hour job. **OpenAI API spend is unchanged** (it
stays the dominant variable cost and is separate from hosting).

## 7. Open / deferred (decide at Phase-1 planning or later — NOT locked here)

- **Tech stack + hosting platform** — Claude Code recommends at Phase-1 planning (implementation choice).
- **Where the durable data lives so the hosted app can read it** — the ledger + research files are in Google
  Drive today; the Refresh button (D7) and the app need a readable home for them. Decide at Phase-1 planning.
- **Notification channel** (email vs. other) for D8 — decide when Phase 3 is scoped.
- **Login mechanism** (email/password vs. Google sign-in) — decide at Phase-1 planning.
- **Colab's fate** — whether Phase 3 replaces Colab entirely or keeps it as the research engine at first is
  deferred to when Phase 3 is scoped (depends on the Phase-1 architecture).
- **GATE-1 prompt wording + how `candidate_priority.py` is recast as GATE-1 discovery** (`MASTER_REDESIGN_SPEC.md`
  §5/§7) — designed together when Phase 3 is scoped.

---

*DIRECTION — decided with Katelynd 2026-07-03. Next: the Phase-1 (hosted dashboard) build spec. This doc is the
picture; the phase specs are the contracts Claude Code builds against.*

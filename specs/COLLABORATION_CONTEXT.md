# Collaboration Context — Health-Tech Research Agent

> **How to use this file:** Starting a NEW chat with Claude, upload or paste this file's full contents
> and say: *"I'm continuing a project — read this context doc and confirm you understand where we are
> before we continue."* Whether a browser Claude chat can read my repo on its own depends on that chat's
> tools: the repo is **public**, so a chat with web-search / fetch enabled CAN pull individual files, but
> a plain chat without browsing tools can't — and even when it can, pasting this file is the reliable,
> complete handoff (no partial or stale fetches). Claude Code has direct repo access.

## Who I am / how we work
I'm Katelynd (GitHub: cleverturnip), a non-coder building a health-tech company
research-and-prioritization agent. Repo: github.com/cleverturnip/health-tech-research-agent

Working model: **design and strategize with Claude in chat; hand finished specs/prompts to
Claude Code** (which has live repo access) to execute. I run live research in a **Colab notebook**
and keep data in Google Drive. Keep this division: Claude helps me think, design, and review;
Claude Code builds.

## North Star — the end-state flow (every decision moves toward this)
A research agent that runs as a mostly-autonomous flow bounded by exactly TWO human-in-the-loop gates:

1. User defines the parameters for the kinds of companies to research → the LLM offers candidate
   suggestions → **[GATE 1]** user approves/edits the candidates.
2. From that approval, a FULLY AUTONOMOUS segment runs with NO user input: it researches the
   approved companies and writes a raw-research batch CSV; scores that research into a **scoring
   ledger** (the §B model); reviews its own output; and produces **review cards + a short summary
   table** with a recommendation attached → **[GATE 2]** user reviews and edits/approves. (The
   review surface is CSV.)
3. From that approval, a second FULLY AUTONOMOUS segment runs with NO user input: it outputs the
   **dashboard**.

**The load-bearing design fact: between GATE 1 and GATE 2, and between GATE 2 and the dashboard,
there is ZERO user input.** Those segments must be architected to run unattended end-to-end — a
problem inside a segment cannot rely on a human noticing it mid-flow. It must be handled
autonomously or surfaced AT THE NEXT GATE for review. When architecting any change inside an
autonomous segment, design for "no one is watching this run" — the flag-for-review pattern (e.g.
`capability_needs_review` routing a row to human attention) is how an autonomous segment defers a
judgment to a gate instead of stalling or guessing.

## How we work — disciplines
> Claude Code's binding working rules are canonical in **`CLAUDE.md`** (Architecture rules + "How I
> want you to work"). This is the design-chat summary of the ones that shape design:

- Investigate (read-only) → plan (no code) → implement red→green, in small reviewable commits.
- Never weaken a validation gate to make something pass.
- Capture every decision durably in the repo (specs / status / runbook) — nothing important lives
  only in chat.
- The single full data regeneration is **run-once** — everything must be right before it.
- Prompt wording for any LLM-facing change is the highest-stakes review — design it together before
  Claude Code builds it.
- **Intent-to-action:** when a recorded intent isn't directly, unambiguously actionable, STOP and
  confirm the exact translation before building — the plausible-but-wrong reading is the recurring
  failure mode (it reads reasonably and only a live run exposes it).
- **Rule 7** — the LLM gathers EVIDENCE; deterministic rules DECIDE. Persist evidence as columns so
  labels/signals are recomputable without re-research.
- **Rule 9 — absence is an upper bound, not a measurement:** a blank / "not found" in our OWN output
  means the data isn't IN our output — it does NOT establish the data doesn't exist. Never attribute
  a cause to an empty field from output alone; convert the bound to a measurement with a live test
  (e.g. a repeat-N variance probe) before building on it.
- Every temporary measure is built toward the North Star end state — solve the immediate step in the
  shape the end state will reuse, not a throwaway shape.
- The scoring + priority framework has ONE source of truth
  (`specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`, FRAMEWORK_VERSION-stamped): scoring changes edit the
  DOC FIRST (version bumps), committed BEFORE anything that depends on it. Output cites the framework
  version it was built against, so staleness is visible.

## Source-of-truth files (current)
1. `specs/COLLABORATION_CONTEXT.md` — this file: flow, how-we-work, and current status/roadmap.
2. `specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md` — the §B scoring + priority framework (locked).
3. `specs/MASTER_REDESIGN_SPEC.md` — the scoring-ledger + cards + summary-table design (current build).
4. `specs/regen_execution_runsheet.md` + `specs/phase2_refresh_runbook.md` — regeneration runbooks (active).
5. `CLAUDE.md` — Claude Code's working rules and repo map.

Superseded/historical material (finished slices, the old `candidate_priority` engine, Phase-3 process
history, audits, one-off probes) lives in `archive/` — reference only.

## Status & roadmap (single source of truth for where we are)

**Done & locked:**
- **Research-prompt overhaul** — the search layer gathers enough quantity/quality/breadth to score
  off of; wording-locked and tested.
- **Data repopulated (regen 2)** — the main company list re-researched on the hardened pipeline; the
  research CSV holds the current raw data.
- **Scoring-model overhaul (§B)** — the gated-then-ranked scoring + priority framework, locked at
  FRAMEWORK v1.25 in Phase 3 and merged. Rules: `SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`; why-history:
  `archive/specs/PHASE3_PROCESS_HISTORY.md`.

**Current milestone (NEXT):** Build the **scoring ledger** (the "master") + the **cards + summary
table** review packet, per `MASTER_REDESIGN_SPEC.md`. The ledger is a pure scoring-decision layer
(write-once §B scores + human priority/taxonomy overrides); the review surface is **CSV** (Google
Sheets retired). Done when a live Colab run verifies the ledger and the cards+table output as designed.

Two design requirements carried into this build:
- **Floored-vs-low legibility** — the ledger must make a FLOORED company (correctly gated: B2B /
  non-consumer) legibly DISTINCT from one that merely scored LOW (consumer but weak). Don't conflate a
  gated `bg=None` with a low bg score.
- **A "how the scoring works" walkthrough doc** — a plain end-to-end walkthrough (classifier → PATH →
  AGENCY → bg → growth-band → PMF → strain → floor → override → threshold → flags) so the system is
  legible without chat history. Division of labor: SOT = rules, `archive/specs/PHASE3_PROCESS_HISTORY.md`
  = why, the new doc = walkthrough.

**Then:** Build + verify the **dashboard** (the autonomous segment after GATE 2).

**Last:** The **front end** + the data system that houses the flow so it runs autonomously end-to-end
instead of through Colab cells. Front end: not started.

*This section is the single status record (replaces the standalone PROJECT_TRACKER.md). Update it as
milestones move; keep done/next honest.*

## Carry-forward engineering notes (open, not yet built)
- **Fit-brief JSON-retry hardening** — the research fit-brief occasionally fails with a `JSONDecodeError`
  (the `videahealth`-class failure; happens ~once per run and can drop a company). Retry/repair the fit
  brief on decode failure. Real, recurring; not yet built.
- **Ledger-review watch-item (data credibility)** — several HIGH growth bands rest on GetLatka `$0→$N`
  single-source series where "$0 in year one" may reflect missing early data rather than a true zero
  (`fay` / `foodsmart` / `nourish` / `berry street` / `summer` / `visana`). Surface in the ledger review
  — NOT a scoring fix. Detail: `archive/specs/PHASE3_PROCESS_HISTORY.md` "Known watch-items."
- **Parked side-task — Claude Code approval-prompt hook** — a PreToolUse auto-approve hook to cut constant
  approval prompts; full spec archived at `archive/specs/spec_pretooluse_autoapprove_hook.md`. Not started.

> Scoring-model open items (e.g. the PATH Test B employer-direct institutional-channel scope fix, and the
> ^c3 B2C viable-engine LINE) live in `SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md` §B3 — that's their home, not here.

## Verification anchors
- **ZOE** = canonical reset test case; **Function Health** = canonical maturity/commercial test case.
- Code logic is proven offline (red→green unit tests); notebook wiring + real-LLM-output behavior are
  proven only by a live Colab run. Package-green is necessary, not sufficient.

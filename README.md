# Health Tech Research Agent

A research agent that discovers health-tech companies, researches them, scores and
prioritizes them against a locked framework, and produces review-ready output — with
human approval gates and full resumability.

## The flow (two human gates)

The agent runs as a mostly-autonomous flow bounded by exactly two human-in-the-loop gates:

1. You define the kind of companies to research → the agent proposes candidates →
   **[GATE 1]** you approve/edit the list.
2. An autonomous segment researches the approved companies, writes a raw-research batch,
   scores it into a **scoring ledger**, reviews its own output, and produces **review cards
   + a summary table** with a recommendation → **[GATE 2]** you review and approve/edit.
3. A second autonomous segment builds the **dashboard**.

Between the gates there is **zero user input** — each segment runs unattended, handling
problems autonomously or surfacing them for review at the next gate.

**Front end:** the flow is being wrapped in a hosted, private web app — a hosted dashboard, plus (later) the
in-app GATE-2 review and GATE-1 conversational discovery. Design + phases:
[`specs/FRONT_END_DIRECTION.md`](specs/FRONT_END_DIRECTION.md).

The full flow, working model, and **current status/roadmap** live in
[`specs/COLLABORATION_CONTEXT.md`](specs/COLLABORATION_CONTEXT.md) — the single source of truth for status.

## Operating model

The workflow currently runs in **Google Colab**. It is being migrated out of notebook cells
into an importable Python package (`src/health_tech_research_agent/`) so the flow can run
autonomously rather than through hand-run cells. **CSV artifacts are the human review surface**
(the GATE-2 packet: `summary_table.csv` / `cards.csv` / `master_full_export.csv`, rendered from the
durable `ledger.jsonl`); Google Sheets is retired **as the gate-decision surface**. (The post-GATE
dashboard is a separate, format-fluid workspace — its editable store is a native Google Sheet, which is
not a gate-decision channel.)

## Core philosophy

The LLM **gathers and interprets evidence**. Deterministic rules **decide priority**. Human
review handles only true edge cases, at the two gates. Incorrect outputs are treated as
calibration data that improves the decision logic — not fixed by manual spreadsheet editing.

## Where to look

| Doc | What it holds |
|---|---|
| [`specs/COLLABORATION_CONTEXT.md`](specs/COLLABORATION_CONTEXT.md) | The North-Star flow, how we work, and current status/roadmap |
| [`specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`](specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md) | The locked scoring + priority framework (the one source of truth for scoring logic) |
| [`specs/MASTER_REDESIGN_SPEC.md`](specs/MASTER_REDESIGN_SPEC.md) | Design for the scoring ledger + review cards + summary table |
| [`specs/DASHBOARD_DESIGN.md`](specs/DASHBOARD_DESIGN.md) | Design + Colab run steps for the dashboard segment |
| [`specs/FRONT_END_DIRECTION.md`](specs/FRONT_END_DIRECTION.md) | The full-flow front-end direction + phase order |
| [`specs/FRONT_END_PHASE1_HOSTED_DASHBOARD.md`](specs/FRONT_END_PHASE1_HOSTED_DASHBOARD.md) | Phase 1 hosted dashboard — build contract + deploy runbook |
| [`specs/SCORING_WALKTHROUGH.md`](specs/SCORING_WALKTHROUGH.md) | Plain end-to-end walkthrough of how a company gets scored |
| [`CLAUDE.md`](CLAUDE.md) | Working rules and guardrails for making changes in this repo |

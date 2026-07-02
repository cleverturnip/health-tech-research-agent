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

The full flow, working model, and current status live in
[`specs/COLLABORATION_CONTEXT.md`](specs/COLLABORATION_CONTEXT.md).

## Operating model

The workflow currently runs in **Google Colab**. It is being migrated out of notebook cells
into an importable Python package (`src/health_tech_research_agent/`) so the flow can run
autonomously rather than through hand-run cells. Google Sheets remains the human review surface.

## Core philosophy

The LLM **gathers and interprets evidence**. Deterministic rules **decide priority**. Human
review handles only true edge cases, at the two gates. Incorrect outputs are treated as
calibration data that improves the decision logic — not fixed by manual spreadsheet editing.

## Where to look

| Doc | What it holds |
|---|---|
| [`specs/COLLABORATION_CONTEXT.md`](specs/COLLABORATION_CONTEXT.md) | The North-Star flow, how we work, and current status/roadmap |
| [`specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`](specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md) | The locked scoring + priority framework (the one source of truth for scoring logic) |
| [`specs/MASTER_REDESIGN_SPEC.md`](specs/MASTER_REDESIGN_SPEC.md) | Design for the scoring ledger + review cards + summary table (current build) |
| [`CLAUDE.md`](CLAUDE.md) | Working rules and guardrails for making changes in this repo |

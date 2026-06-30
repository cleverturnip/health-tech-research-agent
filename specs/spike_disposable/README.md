# Phase-2 scoring SPIKE — DISPOSABLE cells (throwaway reference)

⚠️ **These are throwaway.** This is the Phase-2 scoring spike (clean-room from the SOT) that produced
`../SPIKE_FINAL_RANKING.md`. Committed here **only** so the Phase-3 hardening scoping pass can inventory what
to port. **Do NOT build the production scorer from this code.** Port the LOGIC — clean-room from
`../SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`, logic-faithful per `../spike_pass1_notes.md` **R1** — then **delete
this directory**. The spike is NOT the system.

| File | What it is | Det/LLM |
|---|---|---|
| `spike_scoring_spine.py` | gates (PATH §B3 / AGENCY §B4) + human-locked B2B floor + reset v1.5 (+ basis-regex bridge) + Scale A/B + geometric interp + PMF (zero-baseline / derived / §B6.1 fence / cap@7) + strain §B7 + the §B4 v1.10 `STAGE_OVERRIDE` + `run`/`print_report` | deterministic |
| `spike_step_b5_bgfit.py` | §B5 Background-Fit cell — the LOCKED bg_fit prompt + the Colab runner | LLM (run in Colab) |
| `bg_fit_scores.py` | the frozen `BG_FIT` dict from the validated Colab run (bg_fit is the ONLY LLM output; frozen here so the assembler is reproducible offline) | data (frozen LLM output) |
| `spike_assemble_full_table.py` | assembly driver: runs the spine, applies the Step-A overlays (Function override-candidate; outcomes4me leak-discount), prints the ranked table + floor rule + distribution | deterministic |

**Not self-contained.** The spine imports
`health_tech_research_agent.structured_evidence.funding_stage_from_rounds` (the SOT-B4 mapper — current copy
on branch `research-search-recovery`, `structured_evidence.py:200`) and reads the 54-company research output
`v42_full_regen_clean_slate_20260622_full56_checkpoint_FINAL.csv` (NOT in the repo). It is
offline-deterministic except bg_fit (frozen above).

**Header caveat (do not trust the comment over the code).** `spike_scoring_spine.py` declares "clean-room
from SOT v1.4 §B3–B7" at the top, but its BODY implements later logic (committed Scale A/B + geometric interp
per §B6 v1.8; `STAGE_OVERRIDE` per §B4 v1.10). For "what the spike did," the **code** is the artifact of
record; for "what the hardened scorer must do," the **SOT (v1.11)** is.

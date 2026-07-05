"""Phase 3 (GATE-1) — in-app candidate discovery.

Step 1 (this): the grounding + prompt builders — pure, offline, no OpenAI. Builds the ledger-grounded context
(thesis + full scored roster + manual overrides + exclude list) and fills the locked discovery system prompt
(spec §2a). The OpenAI web-search call + the chat/curate/approve UI come in later steps.

Rule 7: this only assembles CONTEXT for the LLM to PROPOSE candidates; the human approves at GATE-1 and the
deterministic §B scoring happens downstream (research).
"""

from __future__ import annotations

from typing import Any

from .. import dashboard, ledger

# The locked discovery system prompt (spec §2a — signed off 2026-07-04). Only {thesis} / {researched} /
# {overrides} / {roster} are filled; the rest is fixed wording (highest-stakes change — do not edit without sign-off).
PROMPT_TEMPLATE = """You are helping Katelynd find health-tech companies to research for her career search — she wants a ROLE at a company that fits her, not an investment. Propose real, current companies to add to her research list.

Her target market (her saved thesis — the baseline; she may refine it in the chat):
{thesis}

Already researched — do NOT propose any of these again:
{researched}

Her manual priority overrides — where she personally disagreed with the model and set her own priority, in her own words. This is the strongest signal of her taste:
{overrides}
Lean toward companies that resemble the ones she raised; treat the ones she lowered as a weaker fit.

Her full scored roster (how everything she's researched ranks, and why — the numbers-led view):
{roster}

Propose 6-10 candidates that:
- are real, currently-operating health-tech companies — USE WEB SEARCH to verify each exists and get its latest status (stage, recent funding). Never invent or guess; if you can't verify it, drop it.
- fit her thesis (plus anything she adds in the chat) and resemble her raised overrides where it makes sense.
- are NOT already in her researched list.

For each: company name; one line on why it fits (tie to her thesis or her overrides); a quick search signal (stage + latest funding, or what they do).

Then ask if she wants to refine (more like one, earlier-stage, different segment, drop some). Keep it a conversation; approval is a separate step. Be honest about assumptions and about any company you're unsure fits - don't pad the list."""


def _roster_line(record: dict) -> str:
    s = record["scores"]
    return (f'{record["company"]} · {record["segment_label"]} · {record["model"]} · {record["stage"]} · '
            f'{record["final_priority"]} · Bg {record["bg_display"]}/PMF {s["pmf"]}/Strain {s["strain"]}/'
            f'FINAL {record["final_display"]} · {record["key_flag"]}')


def grounding_payload(entries: list[dict], thesis: str, *, taxonomy_dir: Any = None) -> dict:
    """Build the four grounding strings from the ledger: thesis, exclude list, overrides (with reasons), and the
    full compact scored roster. Raw research write-ups are deliberately NOT included (spec §2)."""
    records = dashboard.build_company_records(entries, require_reviewed=False, taxonomy_dir=taxonomy_dir)
    by_company = {r["company"].lower(): r for r in records}

    researched = ", ".join(sorted(r["company"] for r in records)) or "(none yet)"
    roster = "\n".join(_roster_line(r) for r in records) or "(no companies scored yet)"

    override_lines = []
    for entry in entries:
        decision = entry.get("decision") or {}
        if decision.get("human_override"):
            r = by_company.get(str(entry.get("company", "")).lower(), {})
            context = f'{r.get("segment_label", "")} · {r.get("model", "")} · {r.get("stage", "")}'
            override_lines.append(
                f'{entry.get("company")} ({context}): model said {entry.get("model_priority")}, '
                f'she set {ledger.final_priority(entry)} — \'{decision.get("override_reason") or ""}\'')
    overrides = "\n".join(override_lines) if override_lines else "(no manual overrides yet)"

    return {"thesis": (thesis or "").strip() or "(no thesis saved yet)",
            "researched": researched, "overrides": overrides, "roster": roster}


def build_system_prompt(entries: list[dict], thesis: str, *, taxonomy_dir: Any = None) -> str:
    """The full discovery system prompt (locked wording) with the ledger grounding filled in."""
    return PROMPT_TEMPLATE.format(**grounding_payload(entries, thesis, taxonomy_dir=taxonomy_dir))

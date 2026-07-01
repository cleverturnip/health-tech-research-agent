"""Commit 8 (Option B) — the standalone hardened v1.16 reset RE-EMITTER.

The R1 checkpoint's reset_evidence came from the OLD liberal emitter; Option B re-runs the COMMITTED
substance-classifier over org_events so derive_reset_signal stays clean (type + opening, no shim). These
tests prove the standalone prompt carries the committed substance rules AND is byte-identical to the block
embedded in build_fit_brief_prompt (so the two can never silently drift). No LLM.
"""

from health_tech_research_agent import research_runner as rr


def test_reset_emitter_prompt_carries_the_substance_rules():
    p = rr.build_reset_emitter_prompt("ACME", "first-ever CFO appointed to build finance")
    # the load-bearing v1.16 rules
    assert "CLASSIFY BY SUBSTANCE, NOT PRESS FRAMING" in p
    assert "FIRST-EVER / NEWLY-CREATED C-suite seat" in p          # structural-role EXEC ADD
    assert "ipo-prep" in p and "NEVER fire" in p                    # ipo-prep non-firing
    assert "strategic-pivot" in p
    # the evidence + schema are wired
    assert "first-ever CFO appointed to build finance" in p
    assert '"reset_events"' in p and "creates_high_agency_opening" in p


def test_reset_block_is_byte_identical_to_the_fit_brief_block():
    # the standalone re-emitter must run the SAME committed wording embedded in the fit-brief prompt —
    # a sync guard so an edit to one can't silently diverge from the other.
    fit_brief = rr.build_fit_brief_prompt("ACME", "findings", "")
    assert rr._RESET_SUBSTANCE_BLOCK in fit_brief


def test_reset_emitter_prompt_is_pure_and_formats_cleanly():
    # no leftover unfilled placeholders / brace errors
    p = rr.build_reset_emitter_prompt("Season Health", "CEO transition 2025")
    assert "{company}" not in p and "{events}" not in p
    assert p.count("{") == p.count("}")   # only the balanced JSON-schema braces remain

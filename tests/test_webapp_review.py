"""Phase-2 Step 2 — in-app GATE-2 review logic + rendering (offline, on the sample fixture)."""

from pathlib import Path

from health_tech_research_agent import ledger
from health_tech_research_agent.webapp import review

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"


def _entries():
    return ledger.read_ledger(FIXTURE)


def test_pending_is_the_unreviewed_entries():
    entries = _entries()
    assert len(review.pending(entries)) == len(entries)          # raw fixture is un-finalized
    finalized = review.finalize(entries)
    assert review.pending(finalized) == []                        # after finalize, nothing pending


def test_apply_one_override_sets_priority_and_history():
    entries = _entries()
    company = entries[0]["company"]
    merged = review.apply_one(entries, company, "P1", "looks stronger than the model")
    decision = {e["company"].lower(): e for e in merged}[company.lower()]["decision"]
    assert decision["human_override"] == "P1"
    assert decision["override_reason"] == "looks stronger than the model"
    assert len(decision["history"]) == 1
    # scores untouched (Rule 8): model_priority unchanged
    assert merged[0]["model_priority"] == entries[0]["model_priority"]


def test_apply_one_accept_clears_any_override():
    entries = review.apply_one(_entries(), _entries()[0]["company"], "P1", "x")
    company = entries[0]["company"]
    cleared = review.apply_one(entries, company, None, "")            # Accept -> tier None
    decision = {e["company"].lower(): e for e in cleared}[company.lower()]["decision"]
    assert decision["human_override"] in (None, "")


def test_finalize_stamps_every_entry_reviewed():
    finalized = review.finalize(_entries())
    assert all(ledger.is_reviewed(e) for e in finalized)


def test_render_index_lists_pending_and_finalize():
    entries = _entries()
    recs = review.review_records(review.pending(entries))
    html = review.render_index(recs, {e["company"].lower(): e for e in entries})
    assert html.startswith("<!DOCTYPE")
    assert "GATE-2 Review" in html
    for company in ["alpha health", "beta health"]:
        assert company in html
    assert "onclick=\"location.href='/review/alpha%20health'\"" in html   # whole row clickable (no Review button)
    assert "Review &rarr;" not in html                                    # the button was removed
    assert "/review/finalize" in html                                     # the finalize action


def test_render_index_empty_state():
    finalized = review.finalize(_entries())
    recs = review.review_records(review.pending(finalized))           # none pending
    html = review.render_index(recs, {})
    assert "Nothing pending review" in html


def test_render_card_has_detail_body_and_decision_control():
    entries = _entries()
    recs = review.review_records(review.pending(entries))
    by = {e["company"].lower(): e for e in entries}
    card = review.render_card(recs[0], by[recs[0]["company"].lower()])
    assert "SCORING &amp; DECISION" in card                           # reuses the dashboard detail body
    assert "Your decision — priority only" in card
    assert ">P0<" in card and ">P1<" in card                          # override tier buttons


def test_decision_marks_decided_even_on_accept():
    entries = _entries()
    company = entries[0]["company"]
    merged = review.apply_one(entries, company, None, "")             # Accept (no override)
    decided = {e["company"].lower(): e for e in merged}[company.lower()]["decision"]
    assert decided.get("decided_date")                                # marked reviewed-by-you -> green row
    html = review.render_index(review.review_records(merged), {e["company"].lower(): e for e in merged})
    assert "clickrow done" in html and "<th>Score</th>" in html        # green (done) row + a Score column


def test_card_recommendation_and_deferred_save():
    entries = _entries()
    recs = review.review_records(review.pending(entries))
    by = {e["company"].lower(): e for e in entries}
    fh = next((r for r in recs if r["company"] == "function health"), recs[0])
    card = review.render_card(fh, by[fh["company"].lower()])
    assert "Recommendation:" in card                                   # the 'why this recommendation' write-up
    assert 'id="rv-save"' in card and "Save decision" in card          # explicit Save — nothing submits on tier pick
    assert 'type="button"' in card and "rvpick" in card                # tier buttons are non-submitting
    assert '<textarea class="dreason"' in card                          # full-width reason box

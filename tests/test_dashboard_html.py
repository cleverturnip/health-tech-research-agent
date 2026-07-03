"""Phase 5 — the HTML render (interim review surface). Smoke tests: the page is self-contained and reflects
the data model (companies, tiers, segments, override markers, tabs, per-company detail, and safety banners)."""

import json
from pathlib import Path

from health_tech_research_agent import dashboard, dashboard_html, ledger

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"


def _records(with_research=False, workspace=None, contacts=None):
    entries = ledger.finalize_gate2_review(
        ledger.read_ledger(FIXTURE), reviewed_date="2026-07-03", reviewed_at_gate="gate2_sample")
    research = None
    if with_research:
        research = [{"company": "alpha health",
                     "fit_brief_json": json.dumps({"commercial_evidence": {"revenue_or_arr": "$80M ARR"},
                                                   "verified_facts_with_sources": ["Raised $50M. (prnewswire)"]}),
                     "funding_finding": "Series B raised $50M in 2024."}]
    records = dashboard.build_company_records(entries, research=research)
    report = None
    if workspace is not None or contacts is not None:
        records, report = dashboard.merge_user_layer(records, workspace, contacts)
    return records, report


def test_page_is_self_contained_and_lists_every_company():
    records, _ = _records()
    html = dashboard_html.render_dashboard_html(records)
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html.strip()[-10:]
    for company in ["alpha health", "beta health", "gamma health", "delta health", "epsilon health"]:
        assert company in html


def test_tabs_and_grid_render():
    records, _ = _records()
    html = dashboard_html.render_dashboard_html(records)
    for tab in ["All companies", "Pursuit", "Contacts", "Segment radar"]:
        assert tab in html
    assert "Metabolic, nutrition &amp; weight health" in html   # segment label joined
    assert "showDetail('co-beta-health')" in html               # per-company detail wired


def test_override_marker_and_detail_view_present():
    records, _ = _records()
    html = dashboard_html.render_dashboard_html(records)
    assert "was P3" in html                       # beta overridden P3 -> P1
    assert 'id="co-beta-health"' in html          # detail block exists
    assert "SCORING &amp; DECISION" in html
    assert "the gates — a fail here caps priority at P3" in html


def test_research_findings_render_when_joined():
    records, _ = _records(with_research=True)
    html = dashboard_html.render_dashboard_html(records)
    assert "Series B raised $50M in 2024." in html            # raw finding text
    assert "verified facts &amp; sources" in html


def test_no_research_shows_a_note():
    records, _ = _records()
    html = dashboard_html.render_dashboard_html(records)
    assert "No research joined for this company." in html


def test_safety_banners_render_from_report():
    workspace = [
        {"company": "beta health", "pursue": "TRUE", "last_seen_priority": "P3"},   # changed P3 -> P1
        {"company": "zombie health", "pursue": "TRUE", "status": "x"},              # orphaned
    ]
    records, report = _records(workspace=workspace)
    html = dashboard_html.render_dashboard_html(records, report)
    assert "changed since you last looked" in html
    assert "priority P3→P1" in html
    assert "no longer in the reviewed ledger" in html


def test_write_reads_back(tmp_path):
    records, _ = _records()
    path = dashboard_html.write_dashboard_html(tmp_path / "dashboard.html", records)
    text = path.read_text(encoding="utf-8")
    assert "alpha health" in text and text.startswith("<!DOCTYPE html>")

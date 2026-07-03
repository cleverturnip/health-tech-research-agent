"""Phase 3 — the living layer: merge the durable user store into the records, preserve your columns, and
surface the 'changed since you last looked' / 'dropped from ledger' safety signals."""

from pathlib import Path

from health_tech_research_agent import dashboard, ledger

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"


def _records():
    entries = ledger.finalize_gate2_review(
        ledger.read_ledger(FIXTURE), reviewed_date="2026-07-03", reviewed_at_gate="gate2_sample")
    return dashboard.build_company_records(entries)


def _workspace():
    return [
        {"company": "alpha health", "pursue": "TRUE", "status": "Researching", "next_step": "find intro",
         "HQ": "Boston, MA", "desirability_notes": "great", "deep_dive_notes": "", "last_updated": "",
         "last_seen_priority": "P0", "last_seen_segment": "Metabolic, nutrition & weight health",
         "my_custom_col": "keepme"},                       # a column the user added — must survive
        {"company": "beta health", "pursue": "true", "status": "Seeking warm intro",
         "last_seen_priority": "P3",                        # beta is now P1 -> changed since last looked
         "last_seen_segment": "Metabolic, nutrition & weight health"},
        {"company": "zombie health", "pursue": "TRUE", "status": "note"},   # not in the ledger -> orphaned
    ]


def _contacts():
    return [
        {"company": "beta health", "contact": "Dana Rivera", "title": "Head of Growth"},
        {"company": "ghost health", "contact": "Nobody"},                   # orphaned contact
    ]


def test_merge_sets_pursue_and_preserves_user_columns():
    records, _ = dashboard.merge_user_layer(_records(), _workspace(), _contacts())
    by = {r["company"]: r for r in records}

    assert by["alpha health"]["pursue"] is True
    assert by["alpha health"]["workspace"]["status"] == "Researching"
    assert by["alpha health"]["workspace"]["my_custom_col"] == "keepme"   # user-added column preserved
    assert "last_seen_priority" not in by["alpha health"]["workspace"]     # engine key not leaked as a user col

    assert by["gamma health"]["pursue"] is False
    assert by["gamma health"]["workspace"] == {}
    assert by["gamma health"]["contacts"] == []


def test_changed_since_last_looked_flagged():
    records, report = dashboard.merge_user_layer(_records(), _workspace())
    beta = next(r for r in records if r["company"] == "beta health")
    assert beta["changed"] == {"priority": {"from": "P3", "to": "P1"}}
    assert {"company": "beta health", "priority": {"from": "P3", "to": "P1"}} in report["changed"]
    # alpha's snapshot matches -> no change
    alpha = next(r for r in records if r["company"] == "alpha health")
    assert alpha["changed"] is None


def test_orphaned_notes_and_contacts_surfaced_not_deleted():
    _, report = dashboard.merge_user_layer(_records(), _workspace(), _contacts())
    assert report["orphaned_workspace"] == ["zombie health"]
    assert report["orphaned_contacts"] == ["ghost health"]


def test_ledger_side_never_mutated_by_user_data():
    """Rule 6: the user store can carry notes, but it can NEVER change a ledger-derived value."""
    records, _ = dashboard.merge_user_layer(_records(), _workspace())
    alpha = next(r for r in records if r["company"] == "alpha health")
    assert alpha["final_priority"] == "P0"      # unchanged by the workspace row
    assert alpha["segment_label"] == "Metabolic, nutrition & weight health"


def test_contacts_attached_to_their_company():
    records, _ = dashboard.merge_user_layer(_records(), _workspace(), _contacts())
    beta = next(r for r in records if r["company"] == "beta health")
    assert beta["contacts"] == [{"company": "beta health", "contact": "Dana Rivera", "title": "Head of Growth"}]


def test_next_workspace_store_refreshes_snapshot_and_keeps_extra_columns():
    records, _ = dashboard.merge_user_layer(_records(), _workspace())
    store = dashboard.next_workspace_store(records)
    assert set(store["company"]) == {"alpha health", "beta health"}   # only pursued
    assert "my_custom_col" in store.columns                            # user-added column persists

    beta = store[store["company"] == "beta health"].iloc[0]
    assert beta["last_seen_priority"] == "P1"      # snapshot refreshed to the current tier
    alpha = store[store["company"] == "alpha health"].iloc[0]
    assert alpha["my_custom_col"] == "keepme"


def test_pursuit_view_shows_changed_note_and_user_columns():
    records, _ = dashboard.merge_user_layer(_records(), _workspace())
    view = dashboard.pursuit_view(records)
    assert set(view["company"]) == {"alpha health", "beta health"}
    assert "status" in view.columns and "my_custom_col" in view.columns
    beta = view[view["company"] == "beta health"].iloc[0]
    assert beta["changed"] == "priority P3→P1"
    assert beta["status"] == "Seeking warm intro"


def test_contacts_view_one_row_per_contact():
    records, _ = dashboard.merge_user_layer(_records(), _workspace(), _contacts())
    view = dashboard.contacts_view(records)
    assert list(view.columns)[:3] == ["company", "contact", "title"]
    assert view[view["contact"] == "Dana Rivera"].iloc[0]["company"] == "beta health"
    assert "Nobody" not in list(view["contact"])   # orphaned contact isn't attached to any record


def test_merge_with_no_store_defaults_cleanly():
    records, report = dashboard.merge_user_layer(_records())
    assert all(r["pursue"] is False for r in records)
    assert report == {"orphaned_workspace": [], "orphaned_contacts": [], "changed": []}

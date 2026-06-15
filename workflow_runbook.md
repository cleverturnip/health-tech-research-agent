# Health Tech Research Agent — Workflow Runbook

## Source of truth

GitHub is the source of truth for workflow code.

Colab is the execution environment only.

Standard workflow:

1. Edit code in GitHub.
2. Commit changes.
3. Pull latest repo in Colab.
4. Run the workflow from the pulled code.
5. Do not make permanent edits directly in Colab.

---

## Colab startup

Run the GitHub pull/setup cell first.

Then verify:

```python
%cd /content/health-tech-research-agent

!git branch --show-current
!git log -1 --oneline
!git status
!ls -la
```

Expected branch for normal work:

```text
main
```

Expected status:

```text
nothing to commit, working tree clean
```

If generated dashboard files appear in `git status`, see the **Generated file policy** section below.

---

## Normal dashboard refresh

Use this when the master data is already current and you only need to rebuild the dashboard workbook.

Default path:

```text
GitHub pull/setup cell → Step 20
```

Step 20 runs the dashboard refresh sequence:

```text
13 → 14 → 15 → 16 → 17 → 18 → 19 → 19A
```

Step 20 is the default refresh path because it:

* Imports the shared priority helper directly from `src/health_tech_research_agent/priority.py`
* Runs dashboard preparation, market map, segment summary, segment priority summary, data depth audit, segment coverage audit, workbook export, and workbook formatting
* Handles duplicate step markers safely by selecting the longest matching step block
* Produces the final Excel dashboard workbook locally and in Google Drive

Successful output should include:

```text
DASHBOARD REFRESH RUNNER COMPLETE
dashboard_workbook_path = health_tech_dashboard_export_YYYYMMDD_HHMMSS.xlsx
```

The workbook is also written to:

```text
/content/drive/MyDrive/Job Search/Health Tech Research/
```

After Step 20, confirm the repo is still clean:

```python
%cd /content/health-tech-research-agent
!git status
```

Expected output:

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

---

## Manual dashboard refresh fallback

Use this only for debugging, not normal dashboard refreshes.

```text
13 → 14 → 15 → 16 → 17 → 18 → 19 → 19A
```

Use manual step-by-step execution if Step 20 fails and you need to isolate the failing dashboard step.

Do not permanently replace Step 20 with manual execution unless the runner itself is being refactored.

---

## New research batch

Use this when researching new companies or rerunning a batch.

Research sequence:

```text
6 → 6B → 7 → 8 → 8A → 9 → 10 → 10A → 10 → 10B → 11 → 11A → 12
```

Then refresh the dashboard with:

```text
Step 20
```

The full conceptual sequence is:

```text
6 → 6B → 7 → 8 → 8A → 9 → 10 → 10A → 10 → 10B → 11 → 11A → 12 → Step 20
```

---

## Priority adjudication sequence

Use this after Step 7 has produced or loaded `df`.

```text
10 → 10A → 10 → 10B
```

Step 10 parses the model output.

Step 10A applies deterministic priority gates.

Step 10 is rerun to confirm the updated JSON parses correctly.

Step 10B runs QA before export or master update.

---

## Maintenance scripts

Maintenance scripts live in:

```text
maintenance/
```

Current maintenance scripts:

```text
maintenance/step_12C_priority_label_migration.py
```

Step 12C was a one-time priority-label migration from legacy labels into the native P0-P4 model. Do not run it as part of the normal workflow.

Run it only if restoring an old master backup or migrating another master file.

---

## Current priority model

```text
P0 = Highest-priority target / active pursuit
P1 = Near-priority target
P2 = Worth deeper diligence
P3 = Watch list
P4 = Low priority / likely reject
```

Dashboard source of truth:

```text
final_priority_level
final_priority_code
final_priority_rank
priority_source
```

Traceability fields:

```text
priority_level
reviewed_priority_level
legacy_priority_level_before_p0_migration
legacy_reviewed_priority_level_before_p0_migration
```

Shared priority logic lives in:

```text
src/health_tech_research_agent/priority.py
```

Steps currently using shared priority logic:

```text
12B
14
17
18
19
20
```

Do not recreate local priority-ranking, priority-code, or P0-P4 parsing logic inside individual workflow steps unless there is a specific refactor reason.

---

## Stable dashboard checks

After Step 20 completes, confirm these workbook tabs exist:

```text
Read Me
Master Dashboard
Priority Focus
Segment Summary
Companies by Segment
Commercial Scale Review
Data Depth Audit
Segment Coverage Audit
Priority Logic Audit
```

Expected behavior:

```text
P0 companies sort first.
P0 companies are not marked Unprioritized.
Priority Focus includes P0, P1, P2, and calibration-flagged companies.
Segment Summary includes P0 Count.
Segment Coverage Audit counts P0 + P1 + P2 as Priority or Diligence Count.
Priority Logic Audit keeps traceability without breaking dashboard priority logic.
```

---

## Generated file policy

Dashboard refreshes create temporary local files such as:

```text
health_tech_dashboard_export_*.xlsx
health_tech_market_map_snapshot_*.csv
health_tech_market_research_summary_MASTER.csv
```

These files are generated outputs and should not be committed to GitHub.

They are ignored by `.gitignore`.

Python cache files should also not be committed:

```text
__pycache__/
*.pyc
src/**/__pycache__/
```

If generated files appear in `git status`, clean them with:

```python
%cd /content/health-tech-research-agent

!rm -f health_tech_dashboard_export_*.xlsx
!rm -f health_tech_market_map_snapshot_*.csv
!rm -f health_tech_market_research_summary_MASTER.csv
!rm -rf src/health_tech_research_agent/__pycache__

!git status
```

Expected clean state:

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

Do not commit generated dashboard workbooks, snapshots, master CSV outputs, or Python cache files.

---

## Current stable operating loop

For normal dashboard refresh:

```text
GitHub pull/setup cell → Step 20 → confirm workbook path → confirm git status is clean
```

For code changes:

```text
Create branch → edit code → pull branch in Colab → run targeted test → run Step 20 regression → merge to main → pull main → run Step 20 smoke test
```

Do not merge refactors unless Step 20 passes on the branch and then again on `main`.

---

## Branch / merge workflow

Use a branch for any code or workflow change.

Recommended pattern:

```text
1. Create a branch from main.
2. Edit the target file in GitHub.
3. Commit the change to the branch.
4. Pull the branch in Colab.
5. Run the smallest relevant test.
6. Run Step 20 as regression test.
7. If the branch passes, open a pull request.
8. Merge the pull request into main.
9. Delete the branch.
10. Pull main in Colab.
11. Run Step 20 smoke test on main.
12. Confirm git status is clean.
```

Common branch naming:

```text
refactor/<short-description>
chore/<short-description>
fix/<short-description>
```

Examples:

```text
refactor/dashboard-priority-logic
chore/update-runbook-dashboard-runner
fix/step-20-runner-extraction
```

---

## Current productization status

Completed:

```text
Centralized priority logic
Native P0-P4 priority model
Shared priority helper module
Step 14 market map priority refactor
Step 17 data depth audit priority refactor
Step 18 segment coverage priority refactor
Step 19 dashboard export priority refactor
Step 20 one-step dashboard refresh runner
Generated dashboard file .gitignore cleanup
Main branch smoke-tested and clean
```

Next productization target:

```text
Modularize dashboard logic out of colab_workflow.py into reusable Python modules.
```

Recommended next module target:

```text
src/health_tech_research_agent/dashboard.py
```

Recommended first extraction scope:

```text
Pure helper functions used by Steps 14-19.
```

Keep Step 20 as the user-facing Colab runner while moving implementation details underneath it into reusable modules.

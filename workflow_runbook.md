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

Run the GitHub pull cell first.

Then verify:

```python
%cd /content/health-tech-research-agent

!git log -1 --oneline
!git status
!ls -la
```

Expected status:

```text
nothing to commit, working tree clean
```

---

## Normal dashboard refresh

Use this when the master data is already current and you only need to rebuild the dashboard workbook.

```text
12B → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 19A
```

---

## New research batch

Use this when researching new companies or rerunning a batch.

```text
6 → 6B → 7 → 8 → 8A → 9 → 10 → 10A → 10 → 10B → 11 → 11A → 12 → 12B → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 19A
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

---

## Stable dashboard checks

After Step 19A, check these workbook tabs:

```text
Master Dashboard
Priority Focus
Segment Summary
Segment Coverage Audit
Priority Logic Audit
```

Expected behavior:

```text
P0 companies sort first.
P0 companies are not marked Unprioritized.
Segment Summary includes P0 Count.
Segment Coverage Audit counts P0 + P1 + P2 as Priority or Diligence Count.
Priority Logic Audit keeps traceability without breaking dashboard priority logic.
```

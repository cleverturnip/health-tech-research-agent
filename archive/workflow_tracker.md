# Workflow Tracker

## Normal batch workflow

Run order:

```text
1 → 2 → 3 → 4 → 5 → 6 → 6B → 7 → 8 → 8A → 9 → 10 → 10A → 10 → 10B → 11 → 11A → 12 → 12B → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 19A
```

## Special rubric-rerun workflow

Use this when the scoring rubric changes and existing research should be rescored or reinterpreted.

```text
1 → 2 → 3 → 4 → 5 → 6 → TEMP 6B → 7 → 8 → 8A → 9 → 10 → 10A → 10 → 10B → 11 → 11A → 12 → 12B → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 19A
```

## Step definitions

| Step    | Purpose                                                                          |
| ------- | -------------------------------------------------------------------------------- |
| 1       | Environment / imports / setup                                                    |
| 2       | Company/source config                                                            |
| 3       | Search / research helpers                                                        |
| 4       | Raw research functions: funding, payer/institutional, outcomes, commercial scale |
| 5       | Company fit synthesis prompt and scoring                                         |
| 6       | Batch config / paths / company list                                              |
| 6B      | Standard cross-batch checkpoint recovery                                         |
| TEMP 6B | Temporary special rerun setup                                                    |
| 7       | Run research + fit briefs                                                        |
| 8       | Save current batch checkpoint                                                    |
| 8A      | Save raw research archive                                                        |
| 9       | Print raw batch results                                                          |
| 10      | Parse fit brief JSON into score/summary table                                    |
| 10A     | Deterministic priority adjudication                                              |
| 10B     | Batch QA checks before export/master update                                      |
| 11      | Export current batch only                                                        |
| 11A     | Final raw archive QA                                                             |
| 12      | Add/update current batch in master                                               |
| 12B     | Priority field helper: creates final priority fields                             |
| 13      | Load master dashboard using final priority                                       |
| 14      | Build market map view                                                            |
| 15      | Segment-level summary                                                            |
| 16      | Segment priority summary                                                         |
| 17      | Company data depth audit                                                         |
| 18      | Segment coverage audit                                                           |
| 19      | Export dashboard workbook                                                        |
| 19A     | Format exported dashboard workbook                                               |

## Maintenance-only steps

| Step    | Purpose                                                   |
| ------- | --------------------------------------------------------- |
| 12A–12E | Maintenance, rescore, manual-update, or repair flows only |

These are not part of the normal batch workflow unless explicitly needed.

## Priority model

| New priority | Meaning                                  | Old equivalent            |
| ------------ | ---------------------------------------- | ------------------------- |
| P0           | Highest-priority target / active pursuit | Old P1                    |
| P1           | Near-priority target                     | Old Strong P2 / P1-border |
| P2           | Worth deeper diligence                   | Same                      |
| P3           | Watch list                               | Same                      |
| P4           | Low priority / likely reject             | Same                      |

## Dashboard priority fields

| Field                     | Meaning                                |
| ------------------------- | -------------------------------------- |
| `priority_level`          | Automated/adjudicated system priority  |
| `reviewed_priority_level` | Optional human override                |
| `final_priority_level`    | Dashboard priority after normalization |
| `priority_source`         | Auto Adjudicated or Human Reviewed     |
| `final_priority_code`     | P0/P1/P2/P3/P4                         |
| `final_priority_rank`     | Numeric sort helper                    |


# Health Tech Research Agent

This repo contains the working code, workflow documentation, and decision logic for a health tech company research agent.

The goal is to automate repeatable company research for Katelynd LaVallee’s job search, including:

* funding and company-stage research
* payer, employer, provider, and institutional distribution signals
* outcomes and product-value evidence
* commercial scale and revenue-quality evidence
* company fit scoring
* deterministic priority adjudication
* dashboard and market-map export

## Current operating model

The workflow currently runs in Google Colab.

The codebase is being migrated from notebook cells into version-controlled files so the process can become more automated and easier for an LLM/agent to maintain.

## Priority model

The dashboard uses a clean P0–P4 priority model:

| Priority | Meaning                                  |
| -------- | ---------------------------------------- |
| P0       | Highest-priority target / active pursuit |
| P1       | Near-priority target / former P1-border  |
| P2       | Worth deeper diligence                   |
| P3       | Watch list                               |
| P4       | Low priority / likely reject             |

The system preserves source fields for traceability:

* `priority_level` = automated/adjudicated system priority
* `reviewed_priority_level` = optional human override
* `final_priority_level` = dashboard priority after normalization
* `priority_source` = Auto Adjudicated or Human Reviewed
* `final_priority_rank` = helper field for clean sorting

## Core philosophy

The LLM should gather and interpret evidence.

The deterministic rules should decide priority.

Human review should only handle true edge cases.

Incorrect outputs are treated as calibration data and should lead to better decision logic, not manual spreadsheet cleanup.

## Current files

* `README.md` — project overview
* `workflow_tracker.md` — step-by-step workflow and run order
* `colab_workflow.py` — working Colab code, organized by numbered steps

## Near-term roadmap

1. Move current Colab workflow into `colab_workflow.py`
2. Split prompts and rules into separate files
3. Add reusable helper functions
4. Add a one-command batch runner
5. Add QA tests and failure checks
6. Experiment with agentic automation

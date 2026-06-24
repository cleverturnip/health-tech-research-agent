# =============================================================================
# ## Field-landing re-land (remediation)   -- thin notebook caller
#
# Paste as a NEW cell in the authoritative notebook, AFTER the STEP 12 cell
# (the executed master-update cell) and BEFORE the dashboard region. It is the
# only piece of the re-land that runs in Colab; all logic lives in the tested
# package function `health_tech_research_agent.reland.reland_llm_clusters`.
#
# What it does: reads the already-written master + the saved research checkpoint
# and fills ONLY the 10 dropped role/timing + taxonomy-LLM columns, blank-only.
# It does NOT run STEP 10 (summary_rows) or STEP 12 (optional_model_cols), and it
# never touches the master's other 50 columns (read-not-rerun; printed below).
#
# Step-3 protocol (gated on review of the dry-run counts):
#   1. Run with DRY_RUN = True. Eyeball the printed table: per column, target ==
#      readback, and `subsegment_tags` target is 54 (one legitimately-empty row),
#      not 55. Confirm match: checkpoint == master == matched == 55.
#   2. Only then set DRY_RUN = False and re-run for the real write (backs the
#      master up first; rolls back automatically on any read-back failure).
#
# DEFERRED (not written here): primary_market_segment_code (validated code -> STEP
# 14 classifier), the 4 role/timing siblings, and the 5 deterministic-taxonomy
# fields -- all owned by later deterministic steps (dashboard milestone).
# =============================================================================
from health_tech_research_agent.reland import reland_llm_clusters, format_report

DRY_RUN = True  # flip to False ONLY after eyeballing the dry-run counts

# Confirm these resolve to your Colab paths before running:
# - master: the REAL Drive master (same file STEP 12 wrote)
# - checkpoint: the saved 55-row regen research output (note: the local download
#   copy is named "...checkpoint (2).csv"; in Colab it is the un-suffixed file).
MASTER_PATH = (
    "/content/drive/MyDrive/Job Search/Health Tech Research/"
    "health_tech_market_research_summary_MASTER.csv"
)
CHECKPOINT_PATH = (
    "research_batches/v42_full_regen_clean_slate_20260622_full56_checkpoint.csv"
)

result = reland_llm_clusters(MASTER_PATH, CHECKPOINT_PATH, dry_run=DRY_RUN)
print(format_report(result))

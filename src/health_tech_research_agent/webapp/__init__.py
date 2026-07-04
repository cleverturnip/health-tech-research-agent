"""Front-end Phase 1 — the hosted-dashboard web shell.

A thin FastAPI layer over the existing dashboard engine (`dashboard` + `dashboard_html`), per
`specs/FRONT_END_PHASE1_HOSTED_DASHBOARD.md`. It authors no data model and no scoring/merge logic — it gates
access behind a simple-password login and serves / refreshes the render the engine already produces (Rule 1:
reuse the package functions, don't reimplement them).

Step 1 (this): the local skeleton — password login + session gate, rendering from the bundled sample-ledger
fixture (offline). Step 2 swaps the fixture source for a Google-backed source that runs `build_dashboard`.
"""

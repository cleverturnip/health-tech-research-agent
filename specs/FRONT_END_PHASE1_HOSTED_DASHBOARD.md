# Front-End Phase 1 — Hosted Dashboard (build spec)

**Build contract + deploy runbook for Phase 1 of the front-end milestone.** Code lives in
`src/health_tech_research_agent/webapp/`. *Build status + what's next live ONLY in `COLLABORATION_CONTEXT.md`
§ Status & roadmap (not here — avoids drift).* This is the contract
for Phase 1 of the front-end milestone. Phase order + rationale: `FRONT_END_DIRECTION.md` §4. Phase 1 hosts the
**already-built** dashboard engine behind a login, with a Refresh button — the lowest-risk piece, chosen to prove
the hosting/deploy/auth/data-access pipeline end-to-end before the interactive surfaces (GATE 2, GATE 1).

**Reuses (does not rewrite):** the dashboard engine — `dashboard.build_dashboard` + `dashboard_html.render_dashboard_html`
+ the `gspread` user-store round-trip (`DASHBOARD_DESIGN.md` §7/§10). Phase 1 is a **thin web shell over those
package functions** (Architecture rule 1); it adds no new data model and no new scoring/merge logic.

---

## 1. What Phase 1 delivers

A private, login-gated web app at a real URL that renders the dashboard from live data:
- The four grid tabs (all companies · pursuit · contacts · segment radar) + the per-company detail cards, exactly
  as `dashboard_html.render_dashboard_html` already produces them.
- A **Refresh button** that re-runs `build_dashboard` — re-reading your Google Sheet + the latest scored data and
  rebuilding the view on the spot (D7).
- **No in-app editing** (that's Phase 2). Your notes/contacts stay in the Google Sheet.
- The merge safety banners (changed-since / orphaned) render as today.

## 2. Locked Phase-1 decisions

| # | Decision | Detail |
|---|---|---|
| P1.1 | **Backend = Python / FastAPI** | The engine is Python and must be reused, so the backend is Python. FastAPI serves the pages + the Refresh endpoint. |
| P1.2 | **Front end = server-rendered HTML + light HTMX** | Reuse the existing `dashboard_html` render (keeps the designed look); HTMX handles the Refresh action (and sets up Phase-2 interactivity). Phase 1 barely needs JS. |
| P1.3 | **Hosting = Render** | Deploys from the GitHub repo; always-on web service (~$7/mo — free tiers sleep). Same platform will host the Phase-3 background job runner, so no later migration. |
| P1.4 | **Login = simple password** | One password on a login page; a session cookie gates every page. Password stored **hashed** as a Render secret/env var — never in the repo. Served over HTTPS (Render provides TLS). |
| P1.5 | **Data access = least-privilege Google, read-only** | A Google **service account** with read-only access to ONE dedicated Drive folder (holds `ledger.jsonl` + the research CSV) + the dashboard Google Sheet. Nothing else in Drive. Credentials live as a Render secret, never in the repo. |
| P1.6 | **App working files on a small Render persistent disk** | The build's output artifacts + the change-detection snapshot (`_user_snapshot.json`) live on a small persistent disk so the "changed since you last looked" signal survives restarts/redeploys. (Durable sources of truth remain in Google.) |

## 3. How it works (request flow)

1. **Login.** Unauthenticated request → login page. Correct password → a signed session cookie; all routes require it.
2. **View (`GET /`).** Serves the most recently built dashboard HTML from the app's working dir (persistent disk).
   First run (no artifact yet) → triggers a build.
3. **Refresh (`POST /refresh`, HTMX).** Runs the engine:
   - `gspread` authorizes with the **service account**; opens the dashboard Sheet (read-only).
   - Downloads the finalized `ledger.jsonl` + research CSV from the dedicated Drive folder to the working dir.
   - Calls `dashboard.build_dashboard(ledger_path, research=<csv>, out_dir=<working dir>, gsheet=<sheet>,
     taxonomy_dir=<repo taxonomy/>)` — which enforces §1a (finalized ledger), merges your layer, writes the CSV
     views + `dashboard_records.json` + the HTML, and refreshes the snapshot (with its built-in read-back check,
     `readback_ok`).
   - Re-serves the fresh HTML.
   - **Read-only Sheet:** the app never seeds or writes the Sheet (seeding stays a Colab/first-run concern), so
     read-only credentials suffice and your edits are never touched.
4. **taxonomy/** ships with the deployed repo (public, non-sensitive) → the segment-label join needs no Drive read.

## 4. Honoring the rules (guardrails this build must not break)

- **Reuse the engine (rule 1 / §7).** The web layer calls `build_dashboard` / `render_dashboard_html`; it adds no
  merge or scoring logic of its own.
- **§1a gate invariant.** Only a **finalized** (GATE-2-reviewed) ledger renders; `build_dashboard` already raises on
  an un-finalized ledger. Phase-1 finalization still happens upstream (Colab) — the Drive ledger is the finalized one.
- **Input-only user layer (rules 6/3).** The Sheet is read-only to the app; the build never overwrites your edits.
- **Read-back before "done" (rule 5).** The build's `readback_ok` is surfaced; a failed read-back shows an error,
  not a silent success. Live verification (below) is required before Phase 1 is called done (package-green ≠ done).
- **Public repo — nothing sensitive in it.** The repo is PUBLIC. NO secrets and NO private data (ledger / research /
  contacts / the password) are ever committed. All of it lives in Render secrets + Google. The app **code** lives in
  the repo; the app **data + credentials** do not.

## 5. Where the code lives

A thin web package in the repo, importing the engine: `src/health_tech_research_agent/webapp/` (FastAPI `app.py`,
password/session auth, the Refresh route, a Google-service-account data client, minimal templates/static). Deploy
entrypoint: `uvicorn`. A `render.yaml` (or Render dashboard config) + a `requirements`/extras for the web deps.

## 6. Build order within Phase 1

1. **Local skeleton** — FastAPI app + password login + session gate; serve the existing `dashboard.html` /
   `dashboard_records.json` from a local fixture. (Tests: auth gate blocks/allows; page renders.)
2. **Wire Refresh locally** — the Refresh route runs `build_dashboard` against a local ledger/research fixture + a
   test Google Sheet via the service account. (Tests: refresh triggers a build + re-serves; read-only Sheet.)
3. **Deploy to Render** — repo → Render web service; set secrets (password hash, service-account JSON, Sheet id,
   Drive folder id); attach the small persistent disk.
4. **Live-verify (required)** — on the hosted URL: log in, see the dashboard render from live data, edit the Sheet,
   click Refresh, confirm the view updates and your edits are preserved, confirm the safety banners still fire.

## 7. Katelynd's setup checklist (I'll guide each step)

- [ ] A **Render** account + connect the GitHub repo.
- [ ] A **Google Cloud service account**; share the dedicated **Drive folder** (holding `ledger.jsonl` + research CSV)
  and the **dashboard Sheet** with the service-account email, **read-only** ("Viewer").
- [ ] Choose the **app password**; I'll store its hash as a Render secret.

## 8. Definition of done (Phase 1)

- Hosted URL, reachable only after the password login.
- The dashboard renders (4 tabs + detail cards) from the live finalized ledger + research + your Sheet.
- Refresh re-reads the Sheet + latest data and rebuilds on the spot; your Sheet edits are preserved; safety banners fire.
- Read-back verified live (`readback_ok`); no secrets or private data in the public repo; web-layer tests green.

## 8a. Amendment — in-app `pursue` editing (2026-07-04, from demo feedback)

Katelynd asked for `pursue` to be clickable in the app (not only in the Sheet). Adopted, scoped narrowly:
- **The app writes ONLY the `pursue` cell** for a company in the Workspace tab (`dashboard_gsheet.set_pursue`) — a
  **targeted single-cell update**, read-back verified (Rules 4/5); it never touches any other cell, so your other
  edits are safe and the Sheet stays the single source of truth (D7 intact for everything else).
- **Narrow revision of P1.5:** the SHEET now needs **write** scope (`spreadsheets`) and the service account must be
  shared on the Sheet as **Editor** (not Viewer). The Drive **data folder** (ledger/research) stays **read-only**.
- The interactivity is injected at the **app layer** (`_PURSUE_JS`, only when the source supports `set_pursue`); the
  shared engine render stays read-only (correct for the Colab/interim surface). A pursue toggle reloads → rebuild,
  so All + Pursuit stay consistent (a lighter in-place update is a possible later optimization).
- Notes/contacts editing is still out of scope (stays in the Sheet); only `pursue` is in-app editable.

## 8b. Deploy to Render (Step 3) — runbook

Config lives in `render.yaml` (Blueprint) at the repo root — nothing sensitive in it. Editable install
(`pip install -e ".[web]"`) keeps the package importable from the repo checkout so `taxonomy/` resolves at
runtime. Start: `uvicorn health_tech_research_agent.webapp.asgi:app`; health check `/healthz`. `plan: free`
(spins down when idle, ~1 min cold start; upgrade to `starter` for always-on / before the Phase-3 long jobs).

**Steps:**
1. **Generate the password hash** (locally, password never leaves the machine):
   `PYTHONPATH=src python3 -m health_tech_research_agent.webapp.hash_password` → prompts twice → prints the hash.
2. **Render → New → Blueprint**, connect the GitHub repo (`cleverturnip/health-tech-research-agent`, branch `main`).
   Render reads `render.yaml` and creates the `htra-dashboard` web service.
3. **Set the secrets:** `HTRA_PASSWORD_HASH` (step 1 output) + `HTRA_DRIVE_FOLDER_ID` (the "HTRA Dashboard Data"
   folder id) as env vars; and add the service-account key as a **Render Secret File** named
   `service_account.json` (Dashboard → Environment → Secret Files — a mounted file avoids env-var JSON mangling).
   `HTRA_GOOGLE_CREDENTIALS_FILE` (`/etc/secrets/service_account.json`) + `HTRA_SESSION_SECRET` come from
   `render.yaml`; sheet name defaults to "Health Tech Dashboard". (`credentials_info` prefers the file and
   ignores a stray/mangled `HTRA_GOOGLE_CREDENTIALS_JSON`.)
4. **Deploy**, then **live-verify (Step 4)** on the Render URL: log in, dashboard renders from live Google data,
   Refresh works, pursue saves (Sheet shared as **Editor**), no secrets/data in the repo.

## 9. Out of scope (this dashboard shell's design boundary)

- In-app editing of notes / contacts (stays in the Sheet; `pursue` is in-app editable per §8a).
- The GATE-2 review surface and GATE-1 + the research run — their own build specs.
- Notification channel; multi-user sharing; phone-optimized layout (`FRONT_END_DIRECTION.md` §7 / D4).

---

*BUILD SPEC — decided with Katelynd 2026-07-03. This spec is the contract Claude Code builds against. Status/roadmap:
`COLLABORATION_CONTEXT.md` § Status & roadmap only.*

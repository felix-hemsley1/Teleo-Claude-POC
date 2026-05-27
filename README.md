# Teleo — MVP / POC

Teleo is a Windows desktop application that observes how you work (via
structured telemetry — no screenshots, no computer vision), discovers the tasks
you repeat, builds AI agent workflows to automate them, and runs those agents
against real applications with you in the loop.

This repository is the pre-seed POC. It optimizes for a working end-to-end demo,
not production quality.

---

## What it does

```
capture  ->  enrich  ->  sessionize  ->  discover  ->  generate  ->  deploy  ->  execute
(Win32)     (Haiku)      (rules)        (Opus 4.7)    (Opus 4.7)    (UI)        (Playwright)
```

1. **Capture** — A background agent hooks Win32 accessibility events and reads
   UI Automation metadata to record *structured* events (app, control, value,
   URL). Passwords and PII are filtered before anything is stored.
2. **Enrich** — Each event gets a human-readable semantic label (Claude Haiku).
3. **Sessionize** — Events are grouped into coherent work sessions.
4. **Discover** — Recurring tasks are surfaced from sessions (Claude Opus 4.7).
5. **Generate** — Each task is compiled into a Playwright agent script.
6. **Deploy & Execute** — You review/deploy in the UI; agents run with approval
   gates before any irreversible action.

---

## Quick start

> **Platform note:** capture and live agent execution require **Windows**.
> The pipeline, generation, and UI run on any platform. On Linux/macOS you can
> develop and demo everything except live Win32 capture and the visible browser
> run (use seeded demo data — see below).

```bash
# 1. Clone and enter
git clone <repo> && cd teleo-poc

# 2. Virtualenv
python -m venv venv
# Windows:  venv\Scripts\activate
# Unix:     source venv/bin/activate

# 3. Install
#   Windows (full capture stack):
pip install -r requirements.txt
#   Linux/macOS (everything except Win32 capture):
pip install -r requirements-dev.txt

# 4. Browser for agent execution
playwright install chromium

# 5. Configure
cp .env.example .env      # add ANTHROPIC_API_KEY and VOYAGE_API_KEY
```

### Run it

```bash
# Capture (Windows only) — runs in the background, logs event counts
python scripts/start_capture.py

# Pipeline — enrich, sessionize, discover, generate (needs ANTHROPIC_API_KEY)
python scripts/run_pipeline.py                 # all stages
python scripts/run_pipeline.py enrich sessionize   # subset

# UI — review tasks, deploy agents, watch runs
python scripts/start_ui.py                     # http://localhost:8501

# Agent auth (Windows demo) — save logged-in browser state
python scripts/setup_auth.py
```

### Demo without keys or Windows capture

The pipeline stages call Claude, and capture needs Windows. To exercise the
**discovery → deploy → execute** loop and the full UI without either, seed
realistic demo data:

```bash
python scripts/seed_demo_data.py     # ~2 weeks of events, 17 sessions, 3 tasks
python scripts/start_ui.py
```

This populates pre-labeled events, sessions, three discovered workflows, and
generated agent scripts (including a polished "Friday forecast email" demo
agent).

---

## Architecture

| Layer | Module | Notes |
|---|---|---|
| Capture | `capture/` | Win32 `SetWinEventHook`, UIA via pywinauto, browser URL extraction, typing aggregation, redaction |
| Storage | `storage/` | SQLite (`schema.sql`) + data-access layer (`db.py`) |
| Pipeline | `pipeline/` | enrichment (Haiku), sessionization (rules), discovery (Opus), generation (Opus), orchestrator |
| Execution | `execution/` | Playwright runner, DB-backed approval gating, APScheduler, notifications |
| UI | `ui/` | Streamlit app + four tabs + hidden `?demo=true` control panel |
| Shared | `shared/` | Pydantic schemas, config, Claude/Voyage wrappers |

All events flow as typed Pydantic models.

### Privacy / redaction

- Deny-listed processes (password managers, RDP, lock screen) are dropped
  entirely — see `capture/deny_list.py`.
- Deny-listed URLs (banking, payments) are dropped entirely.
- Password fields are nulled and flagged.
- Credit-card / SSN patterns are replaced with `[REDACTED]`.

Redaction runs on **every** event before storage (`capture/redaction.py`).

---

## How to demo

1. Open `http://localhost:8501/?demo=true` for the presenter control panel.
2. **Activity Log** — show structured, semantically-labeled events; note
   redaction indicators.
3. **Discovered Tasks** — open the "Friday forecast email" task; show steps,
   confidence (92%), and estimated time saved (45 min).
4. **Deploy** it (one click).
5. **Deployed Agents → Run Now** — the browser drives Salesforce/Excel/Gmail;
   the approval gate fires before sending the email; approve to finish.
6. **Dashboard** — time-saved metrics update.

Presenter shortcuts (`?demo=true`): reset state, re-seed demo data, simulate a
new discovery.

---

## Known limitations

- **Windows-only capture and live execution.** Win32 hooks/UIA and the visible
  browser run require Windows; on other platforms use seeded demo data.
- **Single user, single machine.** No auth, no multi-tenancy, no cloud.
- **Static agents.** No self-improvement / feedback loop in the POC.
- **LLM-dependent pipeline.** Enrich/discover/generate require an Anthropic key;
  enrichment cost is ~cents per 1k events with Haiku.
- **Brittle selectors.** Generated Playwright scripts prefer role/text
  selectors, but real apps still require per-target hardening.
- **Throwaway code.** This is a POC to close pre-seed, not a product.

---

## Repository layout

```
capture/    Win32 capture + redaction
pipeline/   enrich, sessionize, discover, generate, orchestrate
execution/  Playwright runner, approval, scheduler, notifications
storage/    SQLite schema + data-access layer
ui/         Streamlit app (4 tabs + demo panel)
shared/     schemas, config, LLM wrappers
scripts/    entry points (capture, pipeline, ui, auth, seed)
tests/      manual_test_plan.md
```

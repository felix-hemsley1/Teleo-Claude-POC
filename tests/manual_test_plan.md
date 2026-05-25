# Teleo — Manual Test Plan

Per the build spec, verification is manual at each milestone. Check the boxes as
they pass. Items marked **(Windows)** require a Windows machine; items marked
**(keys)** require a valid `ANTHROPIC_API_KEY`.

---

## Milestone 0 — Foundation

- [x] `python -c "from shared.schemas import ActionEvent; print('ok')"` runs
- [x] `python -c "from storage.db import init_db; init_db()"` creates `teleo.db`
- [x] `python -c "from shared.llm import claude_client; print(claude_client)"` succeeds
- [x] Repo structure matches the spec

## Milestone 1 — Capture

- [x] `redaction.py`: deny-listed process drops the event
- [x] deny-listed URL drops the event
- [x] password field value is nulled and flagged
- [x] credit-card / SSN values are `[REDACTED]` and flagged
- [x] clean events survive unchanged
- [x] all capture modules import (Win32 internals guarded)
- [ ] **(Windows)** `python scripts/start_capture.py` runs; console event counts increment
- [ ] **(Windows)** after ~30 min of use, `events` table has thousands of rows
- [ ] **(Windows)** Salesforce/Gmail events carry URLs, control labels, values
- [ ] **(Windows)** opening 1Password produces NO events
- [ ] **(Windows)** a typed fake password never appears in the DB
- [ ] **(Windows)** CPU < 3%, no perceptible lag

## Milestone 2 — Enrichment & Sessionization

- [ ] **(keys)** `python scripts/run_pipeline.py enrich` labels pending events
- [ ] **(keys)** every processed event has a readable `semantic_label`
- [ ] **(keys)** re-running enrichment does not re-process labeled events (cache hit)
- [x] `python scripts/run_pipeline.py sessionize` populates `sessions`
- [x] sessions split on 3+ minute idle gaps (verified via `_is_boundary`)
- [x] sessions split on process change + >30s gap (verified via `_is_boundary`)
- [x] each session `summary` reads as a coherent narrative (seeded data)
- [ ] **(keys)** enriching 1000 events costs < $1 with Haiku

## Milestone 3 — Discovery

- [ ] **(keys)** pipeline against 2+ weeks of data discovers ≥3 workflows
- [x] discovered workflows persist with `status='detected'` (seeded path)
- [x] each `definition_json` is accurate and specific (seeded data)
- [x] rejecting a task stores a fingerprint and excludes it next run
      (`task_fingerprint` + `rejected_fingerprints`)
- [ ] **(keys)** false-positive rate < 30% on real data

## Milestone 4 — Generation

- [x] ≥3 agent scripts exist in `agents` (seeded path)
- [x] each script parses as valid Python (`ast.parse`)
- [x] each defines `async def run(page, log, approve)`
- [x] each contains at least one `await approve(...)` call
- [x] demo target identified: "Friday forecast email to leadership"

## Milestone 5 — Streamlit UI

- [x] `python scripts/start_ui.py` serves on `localhost:8501` (HTTP 200)
- [x] all four tabs render without exceptions (AppTest)
- [x] Discovered Tasks shows real workflows from the DB
- [x] Deploy moves a workflow to Deployed Agents
- [x] "Not a Real Task" removes it from view
- [x] Edit dialog saves changes (`user_edits_json`)
- [x] Activity Log shows recent events
- [x] Dashboard shows zeros before any runs

## Milestone 6 — Execution

- [x] approval gate fires and pauses execution (approve → True)
- [x] rejecting terminates cleanly (reject → False)
- [x] approval timeout is treated as rejection
- [x] run lifecycle: running → success with `minutes_saved` + `completed_at`
- [x] failed runs record a clear `error_message` and a readable log
- [x] notifications fire (console fallback verified; toast is **(Windows)**)
- [ ] **(Windows)** auth state file contains valid sessions for target apps
- [ ] **(Windows)** demo agent runs successfully 10× with no code changes
- [ ] **(Windows)** approving from the UI resumes; rejecting terminates
- [ ] **(Windows)** toast notifications appear on start/approval/completion

## Milestone 7 — Demo Polish

- [x] hidden demo control panel at `?demo=true` (reset / seed / new discovery)
- [x] README complete: quick start, architecture, demo, limitations
- [ ] **(Windows)** full demo flow runs 10× consistently, under 10 minutes
- [ ] **(Windows)** backup video recorded (`demo_backup.mp4`)

---

## Repro commands (Linux/macOS, no keys)

```bash
python -m venv venv && ./venv/bin/pip install -r requirements-dev.txt
./venv/bin/playwright install chromium      # optional; needed for live runs
./venv/bin/python scripts/seed_demo_data.py
./venv/bin/python scripts/start_ui.py
```

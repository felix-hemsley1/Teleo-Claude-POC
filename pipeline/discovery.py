"""Task discovery: from sessions, surface recurring tasks (Opus 4.7)."""
import calendar
import hashlib
import json
from datetime import datetime

from shared import config
from shared.llm import claude_json
from storage import db
from pipeline.sessionization import session_duration_minutes

MIN_CONFIDENCE = 0.7
MIN_MINUTES = 5
MIN_OCCURRENCES = 3

DISCOVERY_PROMPT = """You are analyzing work sessions captured from a single
user's Windows desktop activity over the past two weeks. Your job: identify
RECURRING TASKS this person does repeatedly.

A "recurring task" means:
- A coherent unit of work with a clear outcome
- Achieves a specific goal (e.g., "send weekly status report", "process new leads")
- Recurs across multiple sessions (a one-time activity is NOT a task)
- Has identifiable inputs and outputs

Good examples of tasks:
- "Friday afternoon: pull Salesforce pipeline report, build summary in Excel,
   email to leadership"
- "Daily morning: review overnight Slack threads, log priorities in Notion,
   reply to urgent messages"
- "When new lead arrives in HubSpot: research company, find LinkedIn profile,
   create Salesforce contact, schedule outreach"

Bad examples (these are NOT tasks):
- "Checks email" (too vague, happens constantly)
- "Opens Salesforce" (an action, not a task)
- "Has a meeting" (calendar event, not workflow)

SESSIONS:
{sessions_json}

For each recurring task you identify (3+ occurrences), return JSON:
{{
  "task_name": "Concise human-readable name",
  "description": "What the user is accomplishing",
  "frequency": "daily|weekly|on-trigger",
  "occurrences": ["2025-MM-DD", ...],
  "steps": [
    {{
      "step_number": 1,
      "action_type": "navigate|read|write|decide|wait|approve",
      "target_app": "Salesforce",
      "description": "Plain-English description",
      "automatable": true,
      "requires_approval": false
    }}
  ],
  "inputs": "What triggers or feeds this task",
  "outputs": "What changes in the world when this task is done",
  "automation_confidence": 0.0-1.0,
  "estimated_minutes_per_run": int,
  "trigger_condition": "How to detect this task should run"
}}

Return ONLY a JSON array of tasks. No preamble. No explanation.
If no recurring tasks found, return [].
"""


def parse_weekday(ts: str) -> str:
    return calendar.day_name[datetime.fromisoformat(ts).weekday()]


def parse_time_of_day(ts: str) -> str:
    h = datetime.fromisoformat(ts).hour
    if h < 12:
        return "morning"
    if h < 17:
        return "afternoon"
    return "evening"


def build_session_summaries(days_back: int = 14) -> list[dict]:
    sessions = db.fetch_recent_sessions(days_back)
    summaries = []
    for s in sessions:
        try:
            apps = json.loads(s.get("apps_used") or "[]")
        except json.JSONDecodeError:
            apps = []
        summaries.append({
            "session_id": s["session_id"],
            "date": s["started_at"][:10],
            "weekday": parse_weekday(s["started_at"]),
            "time_of_day": parse_time_of_day(s["started_at"]),
            "duration_minutes": session_duration_minutes(s),
            "apps": apps,
            "actions": s["summary"].split("\n") if s.get("summary") else [],
        })
    return summaries


def task_fingerprint(task: dict) -> str:
    apps = sorted({
        (step.get("target_app") or "").lower()
        for step in task.get("steps", [])
    })
    step_count = len(task.get("steps", []))
    name_words = (task.get("task_name") or "").lower().split()
    key_phrases = " ".join(sorted(name_words)[:5])
    raw = f"{'|'.join(apps)}::{step_count}::{key_phrases}"
    return hashlib.sha256(raw.encode()).hexdigest()


def discover_workflows(days_back: int = 14) -> int:
    summaries = build_session_summaries(days_back)
    if not summaries:
        print("  no sessions available for discovery")
        return 0

    if not config.has_anthropic():
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set; cannot run discovery. "
            "Set the key or seed demo workflows directly."
        )

    prompt = DISCOVERY_PROMPT.format(sessions_json=json.dumps(summaries, indent=2))
    tasks = claude_json(prompt, model=config.CLAUDE_OPUS_MODEL, max_tokens=8192)
    if not isinstance(tasks, list):
        print("  discovery returned no list")
        return 0

    rejected = db.fetch_rejected_fingerprints()
    stored = 0
    for task in tasks:
        try:
            confidence = float(task.get("automation_confidence", 0))
            minutes = int(task.get("estimated_minutes_per_run", 0))
            occurrences = task.get("occurrences", []) or []
        except (TypeError, ValueError):
            continue

        if confidence < MIN_CONFIDENCE or minutes < MIN_MINUTES:
            continue
        if len(occurrences) < MIN_OCCURRENCES:
            continue
        if task_fingerprint(task) in rejected:
            continue

        db.insert_workflow({
            "status": "detected",
            "task_name": task["task_name"],
            "description": task.get("description"),
            "frequency": task.get("frequency"),
            "estimated_minutes_per_run": minutes,
            "automation_confidence": confidence,
            "occurrence_count": len(occurrences),
            "source_session_ids": [],
            "definition_json": json.dumps(task),
        })
        stored += 1

    print(f"  discovered {stored} workflows")
    return stored

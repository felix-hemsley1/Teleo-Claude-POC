"""Seed realistic demo data so the pipeline, UI, and execution paths can be
exercised end-to-end WITHOUT Windows capture or API keys.

Populates:
  * ~2 weeks of pre-labeled events across Salesforce/Gmail/Excel/Slack
  * sessions (via the real sessionization pass)
  * discovered workflows (status='detected')
  * agent scripts (status='awaiting_deployment') including a polished
    demo-target agent with a real Playwright run() function.

Run: python scripts/seed_demo_data.py
"""
import json
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import config
from storage import db
from storage.db import init_db, insert_events, insert_workflow, insert_agent
from pipeline.sessionization import sessionize_events


def _event(ts, etype, proc, title, label, url=None, ctype=None, clabel=None, cval=None):
    return {
        "event_id": str(uuid.uuid4()),
        "user_id": config.USER_ID,
        "device_id": config.DEVICE_ID,
        "ts_utc": ts.isoformat(),
        "event_type": etype,
        "process_name": proc,
        "window_title": title,
        "url": url,
        "control_type": ctype,
        "control_label": clabel,
        "control_value": cval,
        "is_password": 0,
        "semantic_label": label,
        "redacted": 0,
        "pii_flags": None,
        "raw_json": None,
    }


# A reusable "recurring task" as a sequence of labeled events.
# Intra-task event spacing is in seconds so a single task occurrence groups
# into ONE coherent session (process switches stay within the 30s rule and no
# gap exceeds the 3-minute idle threshold). Distinct days stay separate.
def friday_forecast_sequence(day):
    base = day.replace(hour=15, minute=0, second=0, microsecond=0)
    s = []
    s.append(_event(base, "navigation", "chrome.exe", "Salesforce - Reports",
                     "Opened Salesforce pipeline report",
                     url="https://na1.salesforce.com/reports/pipeline"))
    s.append(_event(base + timedelta(seconds=12), "value_changed", "chrome.exe",
                     "Salesforce - Reports", "Filtered pipeline to current quarter",
                     url="https://na1.salesforce.com/reports/pipeline",
                     ctype="ComboBox", clabel="Date Range", cval="This Quarter"))
    s.append(_event(base + timedelta(seconds=28), "invoke", "chrome.exe",
                     "Salesforce - Reports", "Exported pipeline report to CSV",
                     url="https://na1.salesforce.com/reports/pipeline"))
    s.append(_event(base + timedelta(seconds=45), "focus_changed", "excel.exe",
                     "Q3-forecast.xlsx - Excel", "Opened Q3-forecast.xlsx"))
    s.append(_event(base + timedelta(seconds=70), "typing_burst", "excel.exe",
                     "Q3-forecast.xlsx - Excel", "Updated forecast summary cell B12",
                     ctype="Edit", clabel="B12", cval="1,240,000"))
    s.append(_event(base + timedelta(seconds=95), "navigation", "chrome.exe",
                     "Gmail - Compose", "Opened Gmail compose window",
                     url="https://mail.google.com/mail/u/0/#compose"))
    s.append(_event(base + timedelta(seconds=115), "typing_burst", "chrome.exe",
                     "Gmail - Compose", "Drafted weekly forecast email to leadership",
                     url="https://mail.google.com/mail/u/0/#compose",
                     ctype="Edit", clabel="To", cval="leadership@company.com"))
    s.append(_event(base + timedelta(seconds=135), "invoke", "chrome.exe",
                     "Gmail - Compose", "Sent weekly forecast email to leadership",
                     url="https://mail.google.com/mail/u/0/#compose"))
    return s


def morning_triage_sequence(day):
    base = day.replace(hour=9, minute=0, second=0, microsecond=0)
    s = []
    s.append(_event(base, "focus_changed", "slack.exe", "Slack - Threads",
                     "Reviewed overnight Slack threads in #sales"))
    s.append(_event(base + timedelta(seconds=20), "navigation", "chrome.exe",
                     "Notion - Priorities", "Logged daily priorities in Notion",
                     url="https://www.notion.so/priorities"))
    s.append(_event(base + timedelta(seconds=45), "typing_burst", "chrome.exe",
                     "Notion - Priorities", "Wrote top 3 priorities for the day",
                     url="https://www.notion.so/priorities",
                     ctype="Edit", clabel="Body", cval="1. Follow up Acme 2. Demo prep"))
    s.append(_event(base + timedelta(seconds=70), "invoke", "slack.exe",
                     "Slack - Threads", "Replied to urgent message from manager"))
    return s


def lead_research_sequence(day):
    base = day.replace(hour=11, minute=30, second=0, microsecond=0)
    s = []
    s.append(_event(base, "navigation", "chrome.exe", "HubSpot - Leads",
                     "Reviewed new inbound lead in HubSpot",
                     url="https://app.hubspot.com/contacts/leads"))
    s.append(_event(base + timedelta(seconds=18), "navigation", "chrome.exe",
                     "LinkedIn", "Searched LinkedIn for lead contact profile",
                     url="https://www.linkedin.com/search/results/people"))
    s.append(_event(base + timedelta(seconds=40), "navigation", "chrome.exe",
                     "Salesforce - Contacts", "Created new Salesforce contact for lead",
                     url="https://na1.salesforce.com/contacts/new"))
    s.append(_event(base + timedelta(seconds=62), "typing_burst", "chrome.exe",
                     "Salesforce - Contacts", "Entered contact details and company info",
                     url="https://na1.salesforce.com/contacts/new",
                     ctype="Edit", clabel="Company", cval="Fintech Co"))
    return s


def build_events():
    events = []
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # Walk back 14 days.
    for delta in range(14, -1, -1):
        day = today - timedelta(days=delta)
        wd = day.weekday()  # 0=Mon
        # Friday forecast (Fridays only) -> appears 2-3 times in 2 weeks.
        if wd == 4:
            events += friday_forecast_sequence(day)
        # Morning triage on weekdays.
        if wd < 5:
            events += morning_triage_sequence(day)
        # Lead research a few times a week.
        if wd in (1, 3):
            events += lead_research_sequence(day)
    return events


DEMO_FORECAST_SCRIPT = '''\
async def run(page, log, approve):
    completed = 0
    try:
        log("Step 1: opening Salesforce pipeline report")
        await page.goto("https://na1.salesforce.com/reports/pipeline")
        await page.wait_for_load_state("networkidle")
        completed += 1
        log("Step 1: completed")
    except Exception as e:
        log(f"Step 1: failed - {e}")
        return {"status": "failed", "completed_steps": completed,
                "minutes_saved": 0, "details": "Could not open Salesforce report"}

    try:
        log("Step 2: reading pipeline totals")
        # In a real run we would parse the report grid here.
        completed += 1
        log("Step 2: completed")
    except Exception as e:
        log(f"Step 2: failed - {e}")

    try:
        log("Step 3: drafting forecast email in Gmail")
        await page.goto("https://mail.google.com/mail/u/0/#compose")
        await page.wait_for_load_state("networkidle")
        completed += 1
        log("Step 3: completed")
    except Exception as e:
        log(f"Step 3: failed - {e}")

    ok = await approve("Send weekly forecast email to leadership@company.com")
    if not ok:
        log("User rejected: send forecast email")
        return {"status": "rejected", "completed_steps": completed,
                "minutes_saved": 0, "details": "User rejected sending the email"}

    try:
        log("Step 4: sending forecast email")
        # await page.get_by_role("button", name="Send").click()
        completed += 1
        log("Step 4: completed")
    except Exception as e:
        log(f"Step 4: failed - {e}")
        return {"status": "partial", "completed_steps": completed,
                "minutes_saved": 0, "details": "Drafted but could not send"}

    return {"status": "success", "completed_steps": completed,
            "minutes_saved": 45,
            "details": "Pulled pipeline, updated forecast, sent leadership email"}
'''


WORKFLOWS = [
    {
        "task_name": "Friday forecast email to leadership",
        "description": "Pull the Salesforce pipeline report, summarize it in the "
                       "Q3 forecast workbook, and email the summary to leadership.",
        "frequency": "weekly",
        "occurrences": ["w1-fri", "w2-fri", "w3-fri"],
        "steps": [
            {"step_number": 1, "action_type": "navigate", "target_app": "Salesforce",
             "description": "Open the pipeline report", "automatable": True,
             "requires_approval": False},
            {"step_number": 2, "action_type": "read", "target_app": "Salesforce",
             "description": "Read current-quarter pipeline totals", "automatable": True,
             "requires_approval": False},
            {"step_number": 3, "action_type": "write", "target_app": "Excel",
             "description": "Update forecast summary in Q3-forecast.xlsx",
             "automatable": True, "requires_approval": False},
            {"step_number": 4, "action_type": "approve", "target_app": "Gmail",
             "description": "Send forecast email to leadership", "automatable": True,
             "requires_approval": True},
        ],
        "inputs": "Friday afternoon; Salesforce pipeline data",
        "outputs": "Forecast email delivered to leadership",
        "automation_confidence": 0.92,
        "estimated_minutes_per_run": 45,
        "trigger_condition": "Every Friday at 3pm",
        "script": DEMO_FORECAST_SCRIPT,
        "is_demo": True,
    },
    {
        "task_name": "Morning Slack & Notion triage",
        "description": "Review overnight Slack threads, log priorities in Notion, "
                       "and reply to urgent messages.",
        "frequency": "daily",
        "occurrences": ["d1", "d2", "d3", "d4", "d5"],
        "steps": [
            {"step_number": 1, "action_type": "read", "target_app": "Slack",
             "description": "Review overnight threads", "automatable": True,
             "requires_approval": False},
            {"step_number": 2, "action_type": "write", "target_app": "Notion",
             "description": "Log top priorities", "automatable": True,
             "requires_approval": False},
            {"step_number": 3, "action_type": "approve", "target_app": "Slack",
             "description": "Reply to urgent message", "automatable": True,
             "requires_approval": True},
        ],
        "inputs": "Morning; overnight Slack activity",
        "outputs": "Priorities logged; urgent messages answered",
        "automation_confidence": 0.78,
        "estimated_minutes_per_run": 20,
        "trigger_condition": "Every weekday at 9am",
    },
    {
        "task_name": "New lead research & CRM entry",
        "description": "Research a new inbound lead, find their LinkedIn profile, "
                       "and create a Salesforce contact.",
        "frequency": "on-trigger",
        "occurrences": ["l1", "l2", "l3", "l4"],
        "steps": [
            {"step_number": 1, "action_type": "read", "target_app": "HubSpot",
             "description": "Read new lead details", "automatable": True,
             "requires_approval": False},
            {"step_number": 2, "action_type": "navigate", "target_app": "LinkedIn",
             "description": "Find the contact's LinkedIn profile", "automatable": True,
             "requires_approval": False},
            {"step_number": 3, "action_type": "write", "target_app": "Salesforce",
             "description": "Create the Salesforce contact", "automatable": True,
             "requires_approval": True},
        ],
        "inputs": "New lead arrives in HubSpot",
        "outputs": "Salesforce contact created and enriched",
        "automation_confidence": 0.81,
        "estimated_minutes_per_run": 12,
        "trigger_condition": "When a new lead appears in HubSpot",
    },
]


GENERIC_SCRIPT_TEMPLATE = '''\
async def run(page, log, approve):
    completed = 0
    log("Starting: {name}")
    try:
        log("Step 1: navigating to first target")
        await page.wait_for_load_state("networkidle")
        completed += 1
        log("Step 1: completed")
    except Exception as e:
        log(f"Step 1: failed - {{e}}")
    ok = await approve("Proceed with the irreversible step for {name}")
    if not ok:
        log("User rejected: {name}")
        return {{"status": "rejected", "completed_steps": completed,
                "minutes_saved": 0, "details": "User rejected"}}
    completed += 1
    return {{"status": "success", "completed_steps": completed,
            "minutes_saved": {minutes}, "details": "{name} completed"}}
'''


def seed():
    init_db()
    events = build_events()
    insert_events(events)
    print(f"Seeded {len(events)} events.")

    sessionize_events()

    for wf in WORKFLOWS:
        definition = {k: v for k, v in wf.items() if k not in ("script", "is_demo")}
        workflow_id = insert_workflow({
            "status": "detected",
            "task_name": wf["task_name"],
            "description": wf["description"],
            "frequency": wf["frequency"],
            "estimated_minutes_per_run": wf["estimated_minutes_per_run"],
            "automation_confidence": wf["automation_confidence"],
            "occurrence_count": len(wf["occurrences"]),
            "source_session_ids": [],
            "definition_json": json.dumps(definition),
        })
        script = wf.get("script") or GENERIC_SCRIPT_TEMPLATE.format(
            name=wf["task_name"], minutes=wf["estimated_minutes_per_run"]
        )
        insert_agent({
            "workflow_id": workflow_id,
            "status": "awaiting_deployment",
            "name": wf["task_name"],
            "trigger_type": "manual",
            "generated_script": script,
        })
    print(f"Seeded {len(WORKFLOWS)} workflows + agent scripts.")
    print("Done. Run the UI with: python scripts/start_ui.py")


if __name__ == "__main__":
    seed()

"""Group ordered events into logical work sessions.

Split boundaries:
  * idle gap between consecutive events > 3 minutes, OR
  * process change AND gap > 30 seconds.
"""
import json
import uuid
from datetime import datetime

from shared import config
from storage import db

IDLE_GAP_SECONDS = 3 * 60
CONTEXT_SWITCH_GAP_SECONDS = 30


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _is_boundary(prev: dict, cur: dict) -> bool:
    gap = (_parse_ts(cur["ts_utc"]) - _parse_ts(prev["ts_utc"])).total_seconds()
    if gap > IDLE_GAP_SECONDS:
        return True
    if cur["process_name"] != prev["process_name"] and gap > CONTEXT_SWITCH_GAP_SECONDS:
        return True
    return False


def sessionize_events() -> int:
    """Recompute all sessions from events. Returns session count."""
    events = db.fetch_all_events_ordered()
    if not events:
        print("  no events to sessionize")
        db.replace_sessions([])
        return 0

    groups: list[list[dict]] = []
    current = [events[0]]
    for prev, cur in zip(events, events[1:]):
        if _is_boundary(prev, cur):
            groups.append(current)
            current = [cur]
        else:
            current.append(cur)
    groups.append(current)

    sessions = []
    for group in groups:
        started = group[0]["ts_utc"]
        ended = group[-1]["ts_utc"]
        apps = sorted({e["process_name"] for e in group if e.get("process_name")})
        labels = [e["semantic_label"] for e in group if e.get("semantic_label")]
        sessions.append({
            "session_id": str(uuid.uuid4()),
            "user_id": config.USER_ID,
            "started_at": started,
            "ended_at": ended,
            "event_count": len(group),
            "apps_used": json.dumps(apps),
            "summary": "\n".join(labels),
            "embedding": None,
        })

    db.replace_sessions(sessions)
    print(f"  created {len(sessions)} sessions")
    return len(sessions)


def session_duration_minutes(session: dict) -> float:
    delta = _parse_ts(session["ended_at"]) - _parse_ts(session["started_at"])
    return round(delta.total_seconds() / 60.0, 1)

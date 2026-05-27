"""Semantic enrichment: raw events -> human-readable action labels (Haiku)."""
import hashlib

from shared import config
from shared.llm import claude_json
from storage import db

ENRICHMENT_PROMPT = """You are labeling user activity events captured from a
Windows desktop. For each event, generate a concise semantic label (under 15
words) describing what the user did, focused on the meaningful work action.

Examples of good labels:
- "Saved Salesforce opportunity for Acme Corp"
- "Sent email to john@example.com about Q3 expansion"
- "Updated forecast cell B12 in Q3-forecast.xlsx"
- "Searched LinkedIn for VP Sales contacts at fintech companies"

Examples of bad labels:
- "Clicked button at coordinates 423,891" (not semantic)
- "User performed an action" (too vague)
- "Saved" (insufficient context)

Events to label:
{events_json}

Return JSON array only, no preamble:
[{{"event_id": "...", "label": "..."}}, ...]
"""

BATCH_SIZE = 50


def _cache_key(event: dict) -> str:
    value = event.get("control_value") or ""
    sig = value[:40]
    raw = f"{event.get('process_name')}|{event.get('control_label')}|{sig}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _event_for_prompt(event: dict) -> dict:
    return {
        "event_id": event["event_id"],
        "event_type": event.get("event_type"),
        "process_name": event.get("process_name"),
        "window_title": event.get("window_title"),
        "url": event.get("url"),
        "control_type": event.get("control_type"),
        "control_label": event.get("control_label"),
        "control_value": event.get("control_value"),
    }


def enrich_pending_events(max_batches: int | None = None) -> int:
    """Label all events with NULL semantic_label. Returns count labeled."""
    import json

    labeled = 0
    batches = 0
    while True:
        if max_batches is not None and batches >= max_batches:
            break
        events = db.fetch_unenriched_events(limit=BATCH_SIZE)
        if not events:
            break
        batches += 1

        # Cache pass first.
        to_call = []
        for ev in events:
            key = _cache_key(ev)
            cached = db.cache_get(key)
            if cached is not None:
                db.set_event_label(ev["event_id"], cached)
                labeled += 1
            else:
                to_call.append((ev, key))

        if not to_call:
            continue

        if not config.has_anthropic():
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set; cannot enrich uncached events. "
                "Set the key or seed pre-labeled demo data."
            )

        prompt = ENRICHMENT_PROMPT.format(
            events_json=json.dumps([_event_for_prompt(e) for e, _ in to_call], indent=2)
        )
        result = claude_json(prompt, model=config.CLAUDE_HAIKU_MODEL, max_tokens=2048)
        labels = {item["event_id"]: item["label"] for item in result}

        for ev, key in to_call:
            label = labels.get(ev["event_id"])
            if not label:
                continue
            db.set_event_label(ev["event_id"], label)
            db.cache_put(key, label)
            labeled += 1

    print(f"  enriched {labeled} events")
    return labeled

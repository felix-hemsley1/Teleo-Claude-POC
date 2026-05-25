"""Typing aggregation.

We never store individual keystrokes (that trips EDR keylogger heuristics).
Instead we track focus on each editable element: when focus is gained we record
a start time; when focus is lost, if the element was held for >2s we emit a
single TYPING_BURST event carrying the field's name and final value.
"""
import time
from dataclasses import dataclass
from typing import Optional

MIN_BURST_SECONDS = 2.0


@dataclass
class FocusState:
    hwnd: int
    field_key: str
    label: Optional[str]
    started_at: float


class TypingAggregator:
    def __init__(self):
        self._current: Optional[FocusState] = None

    def on_focus(self, hwnd: int, field_key: str, label: Optional[str]) -> None:
        # Switching focus does not by itself emit; emission happens on blur via
        # on_blur(). Callers that only see focus changes should call
        # focus_changed() which handles the transition.
        self._current = FocusState(hwnd, field_key, label, time.time())

    def focus_changed(self, hwnd: int, field_key: str, label: Optional[str],
                      final_value: Optional[str]) -> Optional[dict]:
        """Handle a focus transition. Returns a TYPING_BURST payload for the
        element that just lost focus if it qualifies, else None."""
        emitted = None
        prev = self._current
        if prev is not None and prev.field_key != field_key:
            duration = time.time() - prev.started_at
            if duration >= MIN_BURST_SECONDS and final_value:
                emitted = {
                    "label": prev.label,
                    "value": final_value,
                    "duration_seconds": round(duration, 1),
                }
        self._current = FocusState(hwnd, field_key, label, time.time())
        return emitted

    def flush(self, final_value: Optional[str]) -> Optional[dict]:
        prev = self._current
        self._current = None
        if prev is None:
            return None
        duration = time.time() - prev.started_at
        if duration >= MIN_BURST_SECONDS and final_value:
            return {
                "label": prev.label,
                "value": final_value,
                "duration_seconds": round(duration, 1),
            }
        return None

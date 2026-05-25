"""Main capture agent: hooks -> UIA enrichment -> redaction -> batched storage.

Threads:
  * Hook thread (HookManager): Win32 message pump, enqueues RawHookEvent.
  * Processor thread: drains the raw queue, runs UIA/browser/typing logic and
    redaction, enqueues storage rows.
  * Storage thread: batches rows (100 or 5s) and writes to SQLite.

Pause/resume is file-based for the POC: the presence of ./.paused halts
processing without tearing down hooks.

Windows-only at runtime; imports cleanly elsewhere so tests can introspect it.
"""
import json
import os
import queue
import sys
import threading
import time
import uuid
from datetime import datetime

from shared import config
from capture.redaction import redact_event
from capture.hooks import (
    HookManager, RawHookEvent,
    EVENT_OBJECT_VALUECHANGE, EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_FOCUS,
)
from capture.uia import UIAReader
from capture.browser import BrowserUrlReader
from capture.typing_aggregator import TypingAggregator
from storage.db import init_db, insert_events

BATCH_SIZE = 100
BATCH_SECONDS = 5
STATS_INTERVAL = 30


class CaptureAgent:
    def __init__(self):
        self.raw_q: "queue.Queue[RawHookEvent]" = queue.Queue(maxsize=10000)
        self.store_q: "queue.Queue[dict]" = queue.Queue(maxsize=10000)
        self.hooks = HookManager(self.raw_q)
        self.uia = UIAReader()
        self.browser = BrowserUrlReader()
        self.typing = TypingAggregator()
        self._stop = threading.Event()
        self._captured = 0
        self._stored = 0
        self._dropped = 0

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        if sys.platform != "win32":
            print("WARNING: capture requires Windows. Hooks will not start here.")
        init_db()
        threading.Thread(target=self._processor_loop, daemon=True).start()
        threading.Thread(target=self._storage_loop, daemon=True).start()
        threading.Thread(target=self._stats_loop, daemon=True).start()
        try:
            self.hooks.start()
        except RuntimeError as e:
            print(f"Hook manager not started: {e}")
        print("Teleo capture agent started. Ctrl-C to stop.")
        try:
            while not self._stop.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self._stop.set()
        self.hooks.stop()
        print(
            f"Stopping. captured={self._captured} stored={self._stored} "
            f"dropped={self._dropped}"
        )

    def _paused(self) -> bool:
        return os.path.exists(config.PAUSE_FLAG_PATH)

    # -- processing --------------------------------------------------------
    def _processor_loop(self):
        while not self._stop.is_set():
            if self._paused():
                time.sleep(1)
                continue
            try:
                raw = self.raw_q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                row = self._build_row(raw)
            except Exception:
                row = None
            if row is None:
                self._dropped += 1
                continue
            try:
                self.store_q.put_nowait(row)
                self._captured += 1
            except queue.Full:
                self._dropped += 1

    def _build_row(self, raw: RawHookEvent) -> dict | None:
        hwnd = raw.hwnd
        process_name = self.uia.process_name_for_hwnd(hwnd)
        window_title = self.uia.window_title_for_hwnd(hwnd)
        url = self.browser.get_url(hwnd, process_name)

        control = self.uia.read_focused_control(hwnd)
        event_type = raw.event_name
        value = control.get("value")

        # Typing-burst handling on focus transitions.
        if raw.event_const in (EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_FOCUS):
            field_key = f"{hwnd}:{control.get('automation_id') or control.get('label')}"
            burst = self.typing.focus_changed(
                hwnd, field_key, control.get("label"), value
            )
            if burst:
                # Emit the burst for the *previous* field as its own row.
                self._enqueue_burst(process_name, window_title, url, burst)

        row = {
            "event_id": str(uuid.uuid4()),
            "user_id": config.USER_ID,
            "device_id": config.DEVICE_ID,
            "ts_utc": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "process_name": process_name or "unknown",
            "window_title": window_title,
            "url": url,
            "control_type": control.get("control_type"),
            "control_label": control.get("label"),
            "control_value": value,
            "is_password": 1 if control.get("is_password") else 0,
            "semantic_label": None,
            "redacted": 0,
            "pii_flags": None,
            "raw_json": None,
        }
        redacted = redact_event(row)
        if redacted is None:
            return None
        redacted["is_password"] = 1 if redacted.get("is_password") else 0
        redacted["redacted"] = 1 if redacted.get("redacted") else 0
        redacted["pii_flags"] = (
            json.dumps(redacted.get("pii_flags")) if redacted.get("pii_flags") else None
        )
        return redacted

    def _enqueue_burst(self, process_name, window_title, url, burst):
        row = {
            "event_id": str(uuid.uuid4()),
            "user_id": config.USER_ID,
            "device_id": config.DEVICE_ID,
            "ts_utc": datetime.utcnow().isoformat(),
            "event_type": "typing_burst",
            "process_name": process_name or "unknown",
            "window_title": window_title,
            "url": url,
            "control_type": "Edit",
            "control_label": burst.get("label"),
            "control_value": burst.get("value"),
            "is_password": 0,
            "semantic_label": None,
            "redacted": 0,
            "pii_flags": None,
            "raw_json": json.dumps({"duration_seconds": burst.get("duration_seconds")}),
        }
        redacted = redact_event(row)
        if redacted is None:
            return
        redacted["is_password"] = 0
        redacted["redacted"] = 1 if redacted.get("redacted") else 0
        redacted["pii_flags"] = (
            json.dumps(redacted.get("pii_flags")) if redacted.get("pii_flags") else None
        )
        try:
            self.store_q.put_nowait(redacted)
        except queue.Full:
            pass

    # -- storage -----------------------------------------------------------
    def _storage_loop(self):
        batch: list[dict] = []
        last_flush = time.time()
        while not self._stop.is_set():
            timeout = max(0.1, BATCH_SECONDS - (time.time() - last_flush))
            try:
                row = self.store_q.get(timeout=timeout)
                batch.append(row)
            except queue.Empty:
                pass
            if batch and (len(batch) >= BATCH_SIZE or
                          time.time() - last_flush >= BATCH_SECONDS):
                self._stored += insert_events(batch)
                batch = []
                last_flush = time.time()
        if batch:
            self._stored += insert_events(batch)

    def _stats_loop(self):
        while not self._stop.is_set():
            time.sleep(STATS_INTERVAL)
            print(
                f"[capture] captured={self._captured} stored={self._stored} "
                f"dropped={self._dropped} qdepth={self.store_q.qsize()}"
            )

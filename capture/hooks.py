"""Win32 event hooks via SetWinEventHook (ctypes).

Runs a dedicated thread with a Win32 message pump. The hook callback must
return fast (<5ms) and never raise, so it only enqueues a lightweight record
onto a thread-safe queue; all heavy work (UIA queries, redaction, storage)
happens on consumer threads.

Windows-only. Importing on non-Windows is allowed but start() will raise.
"""
import ctypes
import queue
import sys
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass

# WinEvent constants.
EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_OBJECT_FOCUS = 0x8005
EVENT_OBJECT_VALUECHANGE = 0x800E
EVENT_OBJECT_INVOKED = 0x8013
EVENT_OBJECT_SELECTION = 0x8006

WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

_EVENT_NAMES = {
    EVENT_SYSTEM_FOREGROUND: "focus_changed",
    EVENT_OBJECT_FOCUS: "focus_changed",
    EVENT_OBJECT_VALUECHANGE: "value_changed",
    EVENT_OBJECT_INVOKED: "invoke",
    EVENT_OBJECT_SELECTION: "selection_changed",
}

IS_WINDOWS = sys.platform == "win32"


@dataclass
class RawHookEvent:
    event_const: int
    event_name: str
    hwnd: int
    id_object: int
    id_child: int
    ts: float


# WinEventProc signature.
if IS_WINDOWS:
    WinEventProcType = ctypes.WINFUNCTYPE(
        None,
        wintypes.HANDLE,  # hWinEventHook
        wintypes.DWORD,   # event
        wintypes.HWND,    # hwnd
        wintypes.LONG,    # idObject
        wintypes.LONG,    # idChild
        wintypes.DWORD,   # idEventThread
        wintypes.DWORD,   # dwmsEventTime
    )
else:  # placeholder so the module imports
    WinEventProcType = None


class HookManager:
    """Registers WinEvent hooks and pumps messages on a dedicated thread."""

    EVENTS = [
        EVENT_SYSTEM_FOREGROUND,
        EVENT_OBJECT_FOCUS,
        EVENT_OBJECT_VALUECHANGE,
        EVENT_OBJECT_INVOKED,
        EVENT_OBJECT_SELECTION,
    ]

    def __init__(self, out_queue: "queue.Queue[RawHookEvent]"):
        self.out_queue = out_queue
        self._thread = None
        self._stop = threading.Event()
        self._hooks = []
        self._proc = None  # keep a reference so it isn't GC'd

    def start(self):
        if not IS_WINDOWS:
            raise RuntimeError("HookManager requires Windows (Win32 APIs).")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _callback(self, hWinEventHook, event, hwnd, idObject, idChild,
                  idEventThread, dwmsEventTime):
        # MUST be fast and exception-free.
        try:
            self.out_queue.put_nowait(
                RawHookEvent(
                    event_const=int(event),
                    event_name=_EVENT_NAMES.get(int(event), "unknown"),
                    hwnd=int(hwnd) if hwnd else 0,
                    id_object=int(idObject),
                    id_child=int(idChild),
                    ts=time.time(),
                )
            )
        except Exception:
            pass

    def _run(self):
        user32 = ctypes.windll.user32
        ole32 = ctypes.windll.ole32
        ole32.CoInitialize(0)

        self._proc = WinEventProcType(self._callback)
        for ev in self.EVENTS:
            h = user32.SetWinEventHook(
                ev, ev, 0, self._proc, 0, 0,
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
            )
            if h:
                self._hooks.append(h)

        msg = wintypes.MSG()
        while not self._stop.is_set():
            # PeekMessage loop so we can honor the stop flag.
            if user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.005)

        for h in self._hooks:
            user32.UnhookWinEvent(h)
        ole32.CoUninitialize()

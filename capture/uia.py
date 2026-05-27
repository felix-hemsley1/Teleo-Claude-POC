"""UI Automation queries for hook events.

Given a window handle (and optionally the focused element), pull human-readable
control metadata: control type, name/label, automation id, value, password
flag, class name. Uses pywinauto's UIA backend, initialized once and reused.

Windows-only. Every query is wrapped in try/except because UIA throws
frequently on transient UI state.
"""
import sys

IS_WINDOWS = sys.platform == "win32"

try:  # pywinauto + comtypes are Windows-only
    from pywinauto import Desktop
    import win32gui
    import win32process
    import psutil  # optional; fall back if absent
except Exception:  # pragma: no cover
    Desktop = None
    win32gui = None
    win32process = None
    psutil = None


# UIA ControlType id -> readable name (common subset).
CONTROL_TYPE_NAMES = {
    50000: "Button", 50001: "Calendar", 50002: "CheckBox", 50003: "ComboBox",
    50004: "Edit", 50005: "Hyperlink", 50006: "Image", 50007: "ListItem",
    50008: "List", 50009: "Menu", 50010: "MenuBar", 50011: "MenuItem",
    50012: "ProgressBar", 50013: "RadioButton", 50014: "ScrollBar",
    50015: "Slider", 50016: "Spinner", 50017: "StatusBar", 50018: "Tab",
    50019: "TabItem", 50020: "Text", 50021: "ToolBar", 50022: "ToolTip",
    50023: "Tree", 50024: "TreeItem", 50025: "Custom", 50026: "Group",
    50027: "Thumb", 50028: "DataGrid", 50029: "DataItem", 50030: "Document",
    50031: "SplitButton", 50032: "Window", 50033: "Pane", 50034: "Header",
    50035: "HeaderItem", 50036: "Table", 50037: "TitleBar", 50038: "Separator",
}


class UIAReader:
    def __init__(self):
        self._desktop = None
        if IS_WINDOWS and Desktop is not None:
            try:
                self._desktop = Desktop(backend="uia")
            except Exception:
                self._desktop = None

    def process_name_for_hwnd(self, hwnd: int) -> str:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if psutil is not None:
                return psutil.Process(pid).name().lower()
        except Exception:
            pass
        return ""

    def window_title_for_hwnd(self, hwnd: int) -> str:
        try:
            return win32gui.GetWindowText(hwnd)
        except Exception:
            return ""

    def read_focused_control(self, hwnd: int) -> dict:
        """Best-effort metadata for the focused control in a window."""
        info = {
            "control_type": None,
            "label": None,
            "automation_id": None,
            "value": None,
            "is_password": False,
            "class_name": None,
        }
        if self._desktop is None:
            return info
        try:
            elem = self._desktop.from_handle(hwnd)
            focused = None
            try:
                focused = elem.get_focus()
            except Exception:
                focused = elem
            target = focused or elem
            ei = target.element_info
            try:
                info["control_type"] = CONTROL_TYPE_NAMES.get(
                    ei.control_type, str(ei.control_type)
                )
            except Exception:
                pass
            for attr, key in (("name", "label"), ("automation_id", "automation_id"),
                              ("class_name", "class_name")):
                try:
                    info[key] = getattr(ei, attr, None)
                except Exception:
                    pass
            try:
                info["value"] = target.get_value()
            except Exception:
                pass
            try:
                info["is_password"] = bool(target.is_password())
            except Exception:
                pass
        except Exception:
            pass
        return info

"""Browser URL extraction from the UIA tree.

Walks the accessibility tree of Chrome/Edge/Firefox windows to find the address
bar edit control and read the current URL. URLs are cached per window handle so
we don't re-walk the tree on every event within the same tab.

Windows-only.
"""
import sys

IS_WINDOWS = sys.platform == "win32"

try:
    from pywinauto import Desktop
except Exception:  # pragma: no cover
    Desktop = None

CHROMIUM_PROCESSES = {"chrome.exe", "msedge.exe", "brave.exe"}
FIREFOX_PROCESSES = {"firefox.exe"}


class BrowserUrlReader:
    def __init__(self):
        self._cache: dict[int, str] = {}
        self._desktop = None
        if IS_WINDOWS and Desktop is not None:
            try:
                self._desktop = Desktop(backend="uia")
            except Exception:
                self._desktop = None

    def invalidate(self, hwnd: int):
        self._cache.pop(hwnd, None)

    def get_url(self, hwnd: int, process_name: str) -> str | None:
        process_name = (process_name or "").lower()
        if process_name not in CHROMIUM_PROCESSES | FIREFOX_PROCESSES:
            return None
        if self._desktop is None:
            return None
        # Cache hit short-circuits the tree walk.
        if hwnd in self._cache:
            return self._cache[hwnd]
        url = self._extract(hwnd, process_name)
        if url:
            self._cache[hwnd] = url
        return url

    def _extract(self, hwnd: int, process_name: str) -> str | None:
        try:
            window = self._desktop.from_handle(hwnd)
        except Exception:
            return None

        names = (
            ["Address and search bar", "Address bar"]
            if process_name in CHROMIUM_PROCESSES
            else ["Search with Google or enter address", "Address"]
        )
        for name in names:
            try:
                edit = window.child_window(title=name, control_type="Edit")
                if edit.exists():
                    val = edit.get_value()
                    if val:
                        return self._normalize(val)
            except Exception:
                continue
        # Fallback: first Edit control inside a toolbar.
        try:
            for edit in window.descendants(control_type="Edit"):
                val = edit.get_value()
                if val and ("." in val or val.startswith("http")):
                    return self._normalize(val)
        except Exception:
            pass
        return None

    @staticmethod
    def _normalize(val: str) -> str:
        val = val.strip()
        if val and not val.startswith(("http://", "https://", "about:", "chrome:")):
            val = "https://" + val
        return val

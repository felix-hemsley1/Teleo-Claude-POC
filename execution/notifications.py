"""User notifications. Windows toast where available, console fallback elsewhere."""
import sys

_toaster = None
if sys.platform == "win32":
    try:
        from windows_toasts import Toast, WindowsToaster
        _toaster = WindowsToaster("Teleo")
    except Exception:  # pragma: no cover
        _toaster = None


def notify_user(title: str, message: str) -> None:
    """Show a Windows toast notification (or print on non-Windows)."""
    if _toaster is not None:
        try:
            from windows_toasts import Toast
            toast = Toast()
            toast.text_fields = [title, message]
            _toaster.show_toast(toast)
            return
        except Exception:
            pass
    print(f"[notify] {title} - {message}")

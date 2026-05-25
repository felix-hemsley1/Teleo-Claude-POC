"""Background execution helper for the Streamlit UI.

Streamlit reruns the script on every interaction, so we keep a module-level
registry of running threads (module globals persist for the process lifetime).
"""
import threading

from execution.runner import execute_agent_sync

# agent_id -> Thread
_threads: dict[str, threading.Thread] = {}


def launch_run(agent_id: str, trigger_context: dict | None = None) -> bool:
    """Start an agent run in a background thread. Returns False if already running."""
    existing = _threads.get(agent_id)
    if existing is not None and existing.is_alive():
        return False

    def _worker():
        try:
            execute_agent_sync(agent_id, trigger_context)
        except Exception:
            # Errors are recorded on the run row by the runner; swallow here so
            # the thread exits cleanly.
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    _threads[agent_id] = t
    return True


def is_running(agent_id: str) -> bool:
    t = _threads.get(agent_id)
    return t is not None and t.is_alive()

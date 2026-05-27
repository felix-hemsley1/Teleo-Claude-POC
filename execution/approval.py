"""Approval gating: agents block on user approval via the database."""
import asyncio

from storage.db import get_approval_status, create_approval_request


async def wait_for_approval(
    run_id: str, description: str = "", timeout_seconds: int = 600
) -> bool:
    """Create an approval request and poll until resolved.

    Returns True if approved, False if rejected or timed out.
    """
    request_id = create_approval_request(run_id, description)

    elapsed = 0
    poll_interval = 2
    while elapsed < timeout_seconds:
        status = get_approval_status(request_id)
        if status == "approved":
            return True
        if status == "rejected":
            return False
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    return False  # timeout == rejection

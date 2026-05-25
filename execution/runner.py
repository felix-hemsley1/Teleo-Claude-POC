"""Execute a deployed agent end-to-end against a real browser via Playwright."""
import asyncio
import os
from datetime import datetime

from shared import config
from storage.db import (
    create_run, update_run_status, update_run_log, load_agent,
)
from execution.approval import wait_for_approval
from execution.notifications import notify_user
from execution import playwright_helpers


async def execute_agent(agent_id: str, trigger_context: dict = None) -> dict:
    """Execute a deployed agent end-to-end."""
    agent = load_agent(agent_id)
    if agent is None:
        raise ValueError(f"Agent not found: {agent_id}")

    run_id = create_run(agent_id, trigger_context)
    log_buffer: list[str] = []

    def log(message: str):
        line = f"[{datetime.utcnow().isoformat()}] {message}"
        log_buffer.append(line)
        update_run_log(run_id, "\n".join(log_buffer))
        print(line)

    async def approve(description: str) -> bool:
        log(f"AWAITING APPROVAL: {description}")
        update_run_status(run_id, "awaiting_approval")
        notify_user(f"{agent['name']} needs approval", description)
        response = await wait_for_approval(run_id, description, timeout_seconds=600)
        if response:
            log(f"APPROVED: {description}")
            update_run_status(run_id, "running")
        else:
            log(f"REJECTED: {description}")
        return response

    try:
        from playwright.async_api import async_playwright
    except Exception as e:  # pragma: no cover
        log(f"FATAL ERROR: Playwright not available: {e}")
        update_run_status(run_id, "failed", error_message=str(e),
                          completed_at=datetime.utcnow())
        raise

    try:
        async with async_playwright() as p:
            launch_kwargs = {"headless": config.HEADLESS, "args": ["--start-maximized"]}
            browser = await p.chromium.launch(**launch_kwargs)
            context_kwargs = {"no_viewport": True}
            if os.path.exists(config.AUTH_STATE_PATH):
                context_kwargs["storage_state"] = config.AUTH_STATE_PATH
            else:
                log(f"WARNING: no auth state at {config.AUTH_STATE_PATH}; "
                    "running unauthenticated")
            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()

            log(f"Starting agent: {agent['name']}")

            # Execute the generated script. The script defines `run(...)`.
            exec_globals = {
                "asyncio": asyncio,
                "page": page,
                "log": log,
                "approve": approve,
                "helpers": playwright_helpers,
            }
            exec(agent["generated_script"], exec_globals)  # noqa: S102
            run_fn = exec_globals.get("run")
            if run_fn is None:
                raise RuntimeError("Generated script does not define run().")

            result = await run_fn(page, log, approve)

            await browser.close()

            if not isinstance(result, dict):
                result = {"status": "success", "minutes_saved": 0,
                          "details": str(result)}

            update_run_status(
                run_id,
                result.get("status", "success"),
                minutes_saved=int(result.get("minutes_saved", 0)),
                completed_at=datetime.utcnow(),
            )
            notify_user(f"{agent['name']} completed",
                        result.get("details", "Task completed"))
            return result

    except Exception as e:  # noqa: BLE001
        log(f"FATAL ERROR: {str(e)}")
        update_run_status(run_id, "failed", error_message=str(e),
                          completed_at=datetime.utcnow())
        notify_user(f"{agent['name']} failed", str(e)[:100])
        raise


def execute_agent_sync(agent_id: str, trigger_context: dict = None) -> dict:
    """Blocking wrapper for use from threads (e.g. the Streamlit UI)."""
    return asyncio.run(execute_agent(agent_id, trigger_context))

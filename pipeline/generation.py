"""Compile discovered workflows into executable Playwright agent scripts."""
import ast
import json

from shared import config
from shared.llm import claude_complete
from storage import db

GENERATION_PROMPT = """Generate a Playwright Python script that automates this
recurring task.

TASK DEFINITION:
{workflow_json}

REQUIREMENTS:
1. Define a single async function: `async def run(page, log, approve)`
   - `page`: pre-configured Playwright Page object
   - `log`: callable(str) for progress logging - use frequently
   - `approve`: async callable(str) -> bool - call BEFORE any irreversible action
2. Use `await approve("description of action")` before:
   - Sending emails, messages, or external communications
   - Saving/submitting forms
   - Modifying or deleting any data
   - Any action that affects external systems
3. If `await approve(...)` returns False:
   - Log "User rejected: <action>"
   - Return early with status "rejected"
4. Selectors (in order of preference):
   - `page.get_by_role("button", name="Save")` - most robust
   - `page.get_by_text("Send")` - readable
   - `page.locator("css=...")` - last resort
5. Each step:
   - Wrap in try/except
   - Log start: `log("Step N: starting <description>")`
   - Log result: `log("Step N: completed")` or `log("Step N: failed - <reason>")`
   - Continue if non-critical, return early if critical
6. Return a dict at the end:
   {{
     "status": "success" | "partial" | "failed" | "rejected",
     "completed_steps": int,
     "minutes_saved": int,
     "details": "Plain English summary"
   }}

TARGET APPLICATIONS: {target_apps}
PRE-AUTHENTICATED CONTEXT: The browser is already logged in. Skip login steps.

Return ONLY valid Python code. No markdown fences. No explanation."""


def _strip_fences(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        code = "\n".join(lines)
    return code.strip()


def _validate(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    has_run = any(
        isinstance(node, ast.AsyncFunctionDef) and node.name == "run"
        for node in ast.walk(tree)
    )
    return has_run


def generate_workflow_scripts() -> int:
    workflows = db.fetch_workflows_needing_scripts()
    if not workflows:
        print("  no workflows need scripts")
        return 0

    if not config.has_anthropic():
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set; cannot generate scripts. "
            "Set the key or seed demo agents directly."
        )

    generated = 0
    for wf in workflows:
        definition = wf.get("definition_json") or "{}"
        try:
            parsed = json.loads(definition)
        except json.JSONDecodeError:
            parsed = {}
        target_apps = sorted({
            step.get("target_app") for step in parsed.get("steps", [])
            if step.get("target_app")
        })

        prompt = GENERATION_PROMPT.format(
            workflow_json=definition,
            target_apps=", ".join(target_apps) or "browser",
        )
        raw = claude_complete(prompt, model=config.CLAUDE_OPUS_MODEL, max_tokens=8192)
        code = _strip_fences(raw)

        if not _validate(code):
            # One repair attempt.
            repair = (
                "The following Python script is invalid or missing "
                "`async def run(page, log, approve)`. Fix it and return ONLY "
                "valid Python, no fences:\n\n" + raw
            )
            code = _strip_fences(
                claude_complete(repair, model=config.CLAUDE_OPUS_MODEL, max_tokens=8192)
            )
            if not _validate(code):
                print(f"  skipped {wf['task_name']}: could not produce valid script")
                continue

        db.insert_agent({
            "workflow_id": wf["workflow_id"],
            "status": "awaiting_deployment",
            "name": wf["task_name"],
            "trigger_type": "manual",
            "generated_script": code,
        })
        generated += 1

    print(f"  generated {generated} agent scripts")
    return generated

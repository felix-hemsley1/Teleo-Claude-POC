"""Small resilience helpers for generated Playwright scripts."""
import asyncio


async def goto_stable(page, url: str, timeout_ms: int = 30000) -> None:
    """Navigate and wait for the network to settle."""
    await page.goto(url, timeout=timeout_ms)
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        # networkidle can never fire on some apps; fall back to domcontentloaded.
        await page.wait_for_load_state("domcontentloaded")


async def dismiss_modals(page) -> None:
    """Best-effort dismissal of common blocking modals."""
    for name in ("Dismiss", "Close", "No thanks", "Got it", "Skip"):
        try:
            btn = page.get_by_role("button", name=name)
            if await btn.count():
                await btn.first.click(timeout=1500)
        except Exception:
            continue


async def with_retry(coro_factory, attempts: int = 3, delay: float = 1.0):
    """Run an async step with retries and exponential backoff."""
    last = None
    for i in range(attempts):
        try:
            return await coro_factory()
        except Exception as e:  # noqa: BLE001
            last = e
            await asyncio.sleep(delay * (2 ** i))
    if last:
        raise last

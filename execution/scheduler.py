"""Cron scheduling for deployed agents (APScheduler)."""
import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from execution.runner import execute_agent

scheduler = BackgroundScheduler()


def schedule_agent(agent_id: str, cron_expression: str) -> None:
    """Schedule an agent to run on a cron schedule."""
    def job():
        asyncio.run(execute_agent(agent_id))

    scheduler.add_job(
        job,
        CronTrigger.from_crontab(cron_expression),
        id=f"agent_{agent_id}",
        replace_existing=True,
    )


def unschedule_agent(agent_id: str) -> None:
    try:
        scheduler.remove_job(f"agent_{agent_id}")
    except Exception:
        pass


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()

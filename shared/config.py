"""Environment configuration loading for Teleo."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Repo root (one level up from this file's package).
ROOT = Path(__file__).resolve().parent.parent

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")

DB_PATH = os.getenv("TELEO_DB_PATH", str(ROOT / "teleo.db"))
USER_ID = os.getenv("TELEO_USER_ID", "felix-default")
DEVICE_ID = os.getenv("TELEO_DEVICE_ID", "device-001")
CAPTURE_ENABLED = os.getenv("TELEO_CAPTURE_ENABLED", "true").lower() == "true"
AUTH_STATE_PATH = os.getenv(
    "TELEO_AUTH_STATE_PATH", str(ROOT / "auth" / "playwright_auth_state.json")
)

# Models (per spec: Opus 4.7 for heavy reasoning, Haiku 4.5 for enrichment).
CLAUDE_OPUS_MODEL = os.getenv("TELEO_OPUS_MODEL", "claude-opus-4-7")
CLAUDE_HAIKU_MODEL = os.getenv("TELEO_HAIKU_MODEL", "claude-haiku-4-5-20251001")
VOYAGE_EMBED_MODEL = os.getenv("TELEO_VOYAGE_MODEL", "voyage-3")

PAUSE_FLAG_PATH = str(ROOT / ".paused")

# Visible browser by default (the demo shows the agent working). Override with
# TELEO_HEADLESS=true for CI/headless test runs.
HEADLESS = os.getenv("TELEO_HEADLESS", "false").lower() == "true"


def has_anthropic() -> bool:
    return bool(ANTHROPIC_API_KEY and ANTHROPIC_API_KEY.startswith("sk-ant"))


def has_voyage() -> bool:
    return bool(VOYAGE_API_KEY and VOYAGE_API_KEY.startswith("pa-"))

"""Entry point: launch the Teleo Streamlit UI."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "ui" / "app.py"),
         "--server.port", "8501"]
    )

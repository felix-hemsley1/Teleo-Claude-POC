"""Entry point: start the Teleo background capture agent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capture.agent import CaptureAgent

if __name__ == "__main__":
    agent = CaptureAgent()
    agent.start()

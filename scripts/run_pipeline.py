"""Entry point: run the discovery pipeline (optionally a subset of stages)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.orchestrator import run_pipeline

if __name__ == "__main__":
    stages = sys.argv[1:] if len(sys.argv) > 1 else None
    run_pipeline(stages)

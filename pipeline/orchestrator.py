"""Pipeline orchestration: enrich -> sessionize -> discover -> generate."""
from pipeline.enrichment import enrich_pending_events
from pipeline.sessionization import sessionize_events
from pipeline.discovery import discover_workflows
from pipeline.generation import generate_workflow_scripts


def run_pipeline(stages: list[str] = None):
    """Run the full discovery pipeline or a subset of stages."""
    stages = stages or ["enrich", "sessionize", "discover", "generate"]

    if "enrich" in stages:
        print("Stage 1: Enriching events...")
        enrich_pending_events()

    if "sessionize" in stages:
        print("Stage 2: Sessionizing...")
        sessionize_events()

    if "discover" in stages:
        print("Stage 3: Discovering workflows...")
        discover_workflows()

    if "generate" in stages:
        print("Stage 4: Generating agent scripts...")
        generate_workflow_scripts()

    print("Pipeline complete.")

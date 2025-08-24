#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUEUE_DIR = REPO_ROOT / "queues"

def dequeue(queue_name: str) -> dict | None:
    f = QUEUE_DIR / f"{queue_name}.json"
    if not f.exists():
        return None
    items = json.loads(f.read_text())
    if not items:
        return None
    job = items.pop(0)
    f.write_text(json.dumps(items, indent=2))
    return job

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("queue_name")
    args = parser.parse_args()

    job = dequeue(args.queue_name)
    if not job:
        print("Queue empty")
        return

    topic = job["topic"]
    tone = job.get("tone", "neutral")
    account = job["account"]
    print(f"Running job: {topic} for {account} tone {tone}")

    # Use the new Python orchestrator
    cmd = ["python", str(REPO_ROOT / "scripts" / "run_pipeline.py"), topic, tone, account]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()
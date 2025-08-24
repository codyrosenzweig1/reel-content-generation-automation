#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
QUEUE_DIR = REPO_ROOT / "queues"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

def load_queue(name: str) -> List[dict]:
    f = QUEUE_DIR / f"{name}.json"
    if not f.exists():
        return []
    return json.loads(f.read_text())

def save_queue(name: str, items: List[dict]) -> None:
    f = QUEUE_DIR / f"{name}.json"
    f.write_text(json.dumps(items, indent=2))

def enqueue(name: str, items: List[dict]) -> None:
    q = load_queue(name)
    q.extend(items)
    save_queue(name, q)

def dequeue(name: str) -> dict | None:
    q = load_queue(name)
    if not q:
        return None
    item = q.pop(0)
    save_queue(name, q)
    return item

def generate_ideas(topic_seed: str, n: int) -> List[dict]:
    # Stub for now. Replace with your OpenAI call or your own generator.
    out = []
    now = datetime.utcnow().isoformat()
    for i in range(n):
        out.append({
            "topic": f"{topic_seed} idea {i+1}",
            "tone": "educational",
            "created_at": now
        })
    return out

def allocate(accounts: Dict[str, str], per_account: int, topic_seed: str) -> None:
    ideas = generate_ideas(topic_seed, per_account * len(accounts))
    idx = 0
    for account, queue_name in accounts.items():
        batch = ideas[idx: idx + per_account]
        idx += per_account
        # attach account at enqueue time so the runner has it
        for b in batch:
            b["account"] = account
        enqueue(queue_name, batch)
        print(f"Allocated {len(batch)} items to {queue_name}")

if __name__ == "__main__":
    # Example accounts map
    accounts = {
        "science_bytes": "queue_science",
        "econ_tips": "queue_econ",
    }
    allocate(accounts, per_account=3, topic_seed="useful facts")
#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import os
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # Fallback if package not available


def _load_env_file(path: Path) -> None:
    try:
        if not path.exists():
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = k.strip()
            # Strip optional surrounding quotes
            val = v.strip().strip('"').strip("'")
            # Do not override if already set in env
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
QUEUE_DIR = REPO_ROOT / "data" / "queues"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

PROMPTS_DIR = REPO_ROOT / "data" / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "idea_allocator_system.txt"
USER_PROMPT_PATH = PROMPTS_DIR / "idea_allocator_user.txt"

PROMPT_JSON_PATH = PROMPTS_DIR / "idea_generation_prompt.json"

# Load environment variables from common locations if not already set
# Priority: .env.local then .env at repo root
_load_env_file(REPO_ROOT / ".env.local")
_load_env_file(REPO_ROOT / ".env")

def _read_prompt_json(path: Path):
    try:
        import json as _json
        return _json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_prompt(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _why_stub() -> str:
    if OpenAI is None:
        return "openai package not available"
    if not os.environ.get("OPENAI_API_KEY"):
        return "OPENAI_API_KEY not set (check .env/.env.local)"
    return "unknown runtime condition"


def _stub_topics(account: str, seed: str, tone: str, style: str, n: int) -> list[dict]:
    """Produce varied topic-like phrases 6–12 words long based on account + seed."""
    now = datetime.utcnow().isoformat()
    # Normalise a short base for variety and easy visual separation per account
    base = seed.split(":")[0].strip()
    if not base:
        base = account
    # Light cleanup for nicer phrasing
    base = base.replace("tips and", "tips &").replace("clear ", "").replace("lesser-known", "less known")

    scaffolds = [
        "{base}: the simple version",
        "{base}: what most people miss",
        "{base}: step by step for beginners",
        "{base}: avoid these common mistakes",
        "{base}: myth versus reality",
        "{base}: everyday examples that make sense",
        "{base}: how to start today",
        "{base}: quick wins that actually work",
        "{base}: tiny changes with big results",
        "{base}: quick guide for busy people",
        "{base}: from confused to confident",
        "{base}: the two minute crash course"
    ]

    out = []
    i = 0
    while len(out) < n:
        text = scaffolds[i % len(scaffolds)].format(base=base)
        words = text.split()
        if len(words) > 12:
            text = " ".join(words[:12])
        out.append({
            "topic": text,
            "tone": tone,
            "style": style,
            "priority": 5,
            "created_at": now
        })
        i += 1
    return out


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



def _account_preset(account: str) -> dict:
    presets = {
        "Tech": {"tone": "curious", "seed": "emerging technology explained simply", "style": "Educational with a slightly humorous, engaging delivery"},
        "History": {"tone": "storytelling", "seed": "surprising history moments and lesser-known figures", "style": "Educational with a slightly humorous, engaging delivery"},
        "Finance/Business": {"tone": "practical", "seed": "personal finance tips and clear business concepts", "style": "Educational with a slightly humorous, engaging delivery"},
        "Physics": {"tone": "explainer", "seed": "intuitive physics insights and thought experiments", "style": "Educational with a slightly humorous, engaging delivery"},
        "Philosophy": {"tone": "reflective", "seed": "everyday philosophy questions and classic ideas", "style": "Educational with a slightly humorous, engaging delivery"},
    }
    return presets.get(account, {"tone": "educational", "seed": "useful facts", "style": "Educational with a slightly humorous, engaging delivery"})



def generate_ideas_llm(account: str, n: int) -> List[dict]:
    preset = _account_preset(account)
    tone = preset["tone"]
    seed = preset["seed"]
    style = preset["style"]

    # If OpenAI client is unavailable or no key, fall back to a richer stub
    if OpenAI is None or not os.environ.get("OPENAI_API_KEY"):
        reason = _why_stub()
        print(f"[idea_allocator] Using stub topics because {reason}.", flush=True)
        return _stub_topics(account, seed, tone, style, n)

    client = OpenAI()
    # Allow overriding model via env
    model = os.environ.get("OPENAI_MODEL_ID", "gpt-4o-mini")

    # Ask for compact JSON to minimise tokens
    schema = {
        "name": "topics_schema",
        "schema": {
            "type": "object",
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string"},
                            "tone": {"type": "string"},
                            "style": {"type": "string"}
                        },
                        "required": ["topic", "tone"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["topics"],
            "additionalProperties": False
        }
    }

    # Prefer consolidated JSON prompt if present
    prompt_json = _read_prompt_json(PROMPT_JSON_PATH)
    if prompt_json:
        system_msg = prompt_json.get("system_prompt") or _read_prompt(SYSTEM_PROMPT_PATH) or (
            "You generate short, specific, YouTube Shorts or Instagram Reel topics in Australian English. "
            "Both tone and style are provided and must be reflected in the topics. "
            "Keep each topic 6 to 12 words. No emojis. No lists with numbering. Use concise phrasing."
        )
        user_template = prompt_json.get("user_prompt_template") or _read_prompt(USER_PROMPT_PATH) or (
            "Create {n} distinct content topics for the account category '{account}'. "
            "Audience is general interest. Tone should be '{tone}'. Style should be '{style}'. Seed direction: {seed}. "
            "Return only diverse, self-contained topics suitable for 60–90 second reels."
        )
    else:
        system_msg = _read_prompt(SYSTEM_PROMPT_PATH) or (
            "You generate short, specific, YouTube Shorts or Instagram Reel topics in Australian English. "
            "Both tone and style are provided and must be reflected in the topics. "
            "Keep each topic 6 to 12 words. No emojis. No lists with numbering. Use concise phrasing."
        )
        user_template = _read_prompt(USER_PROMPT_PATH) or (
            "Create {n} distinct content topics for the account category '{account}'. "
            "Audience is general interest. Tone should be '{tone}'. Style should be '{style}'. Seed direction: {seed}. "
            "Return only diverse, self-contained topics suitable for 60–90 second reels."
        )

    try:
        user_msg = user_template.format(n=n, account=account, tone=tone, style=style, seed=seed)
    except Exception:
        # Fallback to raw template if formatting placeholders are missing
        user_msg = user_template

    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_schema", "json_schema": schema},
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.7,
        max_tokens=800,
    )

    try:
        data = resp.choices[0].message.parsed  # available with response_format json_schema
        topics = data.get("topics", [])
    except Exception:
        # Fallback to JSON parsing if parsed not present
        import json as _json
        content = resp.choices[0].message.content
        topics = _json.loads(content).get("topics", [])

    now = datetime.utcnow().isoformat()
    out: List[dict] = []
    for t in topics[:n]:
        out.append({
            "topic": t.get("topic", "Untitled Topic"),
            "tone": t.get("tone", tone),
            "style": t.get("style", style),
            "priority": 5,
            "created_at": now
        })
    # If model returned fewer than requested, top up deterministically
    while len(out) < n:
        out.append({"topic": f"{seed} #{len(out)+1}", "tone": tone, "style": style, "priority": 5, "created_at": now})
    return out



def allocate(accounts: Dict[str, str], per_account: int, topic_seed: str) -> None:
    # Ignore topic_seed for LLM path; keep arg for backward compatibility
    for account, queue_name in accounts.items():
        print(f"[idea_allocator] Generating {per_account} topics for account='{account}' -> queue='{queue_name}'", flush=True)
        ideas = generate_ideas_llm(account, per_account)
        if ideas:
            sample = ", ".join([i["topic"] for i in ideas[:3]])
            print(f"[idea_allocator] Preview for '{account}': {sample}", flush=True)
        # attach account
        for b in ideas:
            b["account"] = account
        enqueue(queue_name, ideas)
        print(f"Allocated {len(ideas)} items to {queue_name}")


if __name__ == "__main__":
    accounts = {
        "Tech": "queue_tech",
        "History": "queue_history",
        "Finance/Business": "queue_finbiz",
        "Physics": "queue_physics",
        "Philosophy": "queue_philosophy",
    }
    allocate(accounts, per_account=20, topic_seed="seed")
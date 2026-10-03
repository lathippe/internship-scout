"""Files the scout keeps in the repo. Everything is plain JSON so you can read and edit it."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BRIEF = os.path.join(ROOT, "brief.json")


def path(name: str) -> str:
    return os.path.join(DATA, name)


def load(p: str, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(p: str, obj) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, p)


def append_jsonl(p: str, obj) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(p: str) -> list:
    try:
        with open(p, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def now() -> datetime:
    return datetime.now(timezone.utc)


def today_iso() -> str:
    return now().date().isoformat()


def brief() -> dict:
    b = load(BRIEF, None)
    if b is None:
        raise SystemExit("brief.json is missing. Run the setup chat first (/scout-setup in Claude Code).")
    return b


def save_brief(b: dict) -> None:
    save(BRIEF, b)

"""Builds docs/index.html: one self-contained page with your data baked in."""
from __future__ import annotations

import json
import os

from . import store

TEMPLATE = os.path.join(os.path.dirname(__file__), "dashboard_template.html")
OUT = os.path.join(store.ROOT, "docs", "index.html")


def build() -> str:
    b = store.load(store.BRIEF, {})
    jobs = store.load(store.path("jobs.json"), {})
    keep = [j for j in jobs.values() if j.get("status") != "gone" or j.get("stages")]
    keep.sort(key=lambda j: -(j.get("score") or 0))
    data = {
        "generated": store.now().isoformat(),
        "brief": {k: b.get(k) for k in ("name", "headline", "who", "goal", "streams", "tracks", "firm_types", "dream_firms",
                                        "skip_firms", "weights", "hard_filters", "visa", "notes", "history", "urgent")},
        "jobs": keep[:400],
        "suggestions": [dict(s, n=i) for i, s in enumerate(store.load(store.path("suggestions.json"), []), 1) if s.get("state") == "open"],
        "runs": store.read_jsonl(store.path("runs.jsonl"))[-14:],
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read().replace("/*SCOUT_DATA*/null", payload)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  dashboard: {os.path.relpath(OUT, store.ROOT)} ({len(keep)} roles)")
    return OUT

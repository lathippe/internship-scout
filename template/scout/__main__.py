"""Internship scout.

  python -m scout run          full morning run: fetch, filter, score, read inbox, send, rebuild dashboard
  python -m scout dry-run      same without Claude or sending anything (rough scores, for testing)
  python -m scout dashboard    rebuild docs/index.html from data/
  python -m scout feedback "text" [--job ID]
  python -m scout status ID applied|test|interview|final|offer|rejected|withdrawn ["note"]
  python -m scout apply N      apply suggested change N to brief.json
  python -m scout dismiss N
"""
from __future__ import annotations

import hashlib
import re
import sys
from collections import Counter
from datetime import date, timedelta

from . import filters, llm, notify, sources, store
from .dashboard import build as build_dashboard

STAGE_ORDER = ["new", "saved", "applied", "test", "interview", "final", "offer"]
CLOSED = {"rejected", "withdrawn", "gone"}


def jid(fp: str) -> str:
    return hashlib.sha1(fp.encode()).hexdigest()[:8]


def total(job: dict, b: dict):
    """Final score from Claude's 4 ratings, your weights, and your track and firm preferences."""
    s = job.get("scored")
    if not s:
        return 0.0, []
    w = b.get("weights", {"fit": .35, "mentor": .35, "brand": .15, "pay": .15})
    tw = sum(w.values()) or 1
    base = sum(s.get(k, 5) * v for k, v in w.items()) / tw
    adj = []
    tm = b.get("tracks", {}).get(job.get("track"), 1.0)
    if tm < 1:
        adj.append(["Track: " + job.get("track", ""), -round((1 - tm) * 2, 1)])
    fm = b.get("firm_types", {}).get(job.get("firm_type"), 1.0)
    if fm < 1:
        adj.append(["Firm type", -round((1 - fm) * 1.5, 1)])
    if any(filters.norm(d) and filters.norm(d) in filters.norm(job["company"]) for d in b.get("dream_firms", [])):
        adj.append(["Dream firm", 0.5])
    return round(max(0, min(10, base + sum(a[1] for a in adj))), 1), adj


def rough(job: dict) -> dict:
    """Dry-run stand-in for Claude: keyword guesses, clearly not real scores."""
    t = (job["title"] + " " + job.get("category", "")).lower()
    track = next((k for k, ws in (("research", ("research",)), ("trading", ("trad",)), ("risk", ("risk",)),
                                  ("strats", ("strat",)), ("dev", ("develop", "engineer")), ("data", ("data",)))
                  if any(x in t for x in ws)), "other")
    return {"fit": 6.5 if track == "research" else 5, "mentor": 5, "brand": 6, "pay": 6, "track": track,
            "firm_type": "other", "stream": "summer", "cpt": "ok", "deadline": None,
            "pros": ["Dry run: not scored by Claude"], "cons": ["Dry run: not scored by Claude"], "dealbreaker": None}


def run(dry: bool = False) -> None:
    b = store.brief()
    use_llm = not dry and llm.available()
    if not dry and not use_llm:
        print("ANTHROPIC_API_KEY is not set, running with rough scores and no sending.")
        dry = True
    jobs = store.load(store.path("jobs.json"), {})
    state = store.load(store.path("state.json"), {})
    t0 = store.now().isoformat()
    log = {"date": t0}

    print("Fetching postings")
    raw = sources.fetch_all(b)
    log["read"] = len(raw)
    uniq = filters.dedupe(raw)
    log["after_duplicates"] = len(uniq)

    reasons, fresh = Counter(), []
    seen_now = set()
    for j in uniq:
        k = jid(j["fp"])
        seen_now.add(k)
        if k in jobs:
            jobs[k]["last_seen"] = t0
            continue
        why = filters.passes(j, b)
        if why:
            reasons[why] += 1
            continue
        fresh.append((k, j))
    log["filtered_out"] = dict(reasons)
    log["new"] = len(fresh)
    print(f"  {len(raw)} read, {len(uniq)} unique, {len(fresh)} new and passed filters")

    cap = int(b.get("max_scored_per_run", 40))
    for k, j in fresh[:cap]:
        if not j.get("description"):
            j["description"] = sources.page_text(j["url"])
        try:
            s = llm.score(b, j) if use_llm else rough(j)
        except Exception as e:
            print(f"  ! could not score {j['company']}: {e}")
            continue
        rec = {kk: j.get(kk) for kk in ("company", "title", "url", "locations", "source", "terms", "fp")}
        rec.update(id=k, also_on=sorted(set(j.get("also_on", []))), first_seen=t0, last_seen=t0, status="new",
                   stages=[], scored={x: s[x] for x in ("fit", "mentor", "brand", "pay")},
                   **{x: s[x] for x in ("track", "firm_type", "stream", "cpt", "deadline", "pros", "cons", "dealbreaker")})
        if s.get("dealbreaker"):
            rec["status"] = "gone"
        jobs[k] = rec
    log["scored"] = min(len(fresh), cap)

    for k, rec in jobs.items():  # postings that disappeared from every source are closed
        if rec["status"] == "new" and k not in seen_now and rec.get("last_seen", t0) < (store.now() - timedelta(days=3)).isoformat():
            rec["status"] = "gone"

    if not dry:
        inbox(b, jobs, state, use_llm)
        replies(b, state)

    for rec in jobs.values():
        rec["score"], rec["adj"] = total(rec, b)

    if use_llm:
        suggest(b, state, jobs)
    store.save(store.path("jobs.json"), jobs)
    store.append_jsonl(store.path("runs.jsonl"), log)

    deliver(b, jobs, state, log, dry)
    store.save(store.path("state.json"), state)
    build_dashboard()
    print("Done")


def inbox(b: dict, jobs: dict, state: dict, use_llm: bool) -> None:
    """Read recent mail for application events. Read-only; nothing is marked or moved."""
    if not use_llm:
        return
    done = set(state.get("mail_seen", []))
    try:
        mails = notify.recent_mail()
    except Exception as e:
        print(f"  ! inbox: {e}")
        return
    for m in mails:
        if m["id"] in done or notify.is_reply_to_digest(m) or notify.SUBJECT_TAG in m["subject"]:
            continue
        done.add(m["id"])
        if not re.search(r"(application|applying|assessment|interview|hirevue|codesignal|hackerrank|offer|unfortunately|next steps|candidate|thank you for)", m["subject"] + " " + m["body"][:2000], re.I):
            continue
        try:
            r = llm.read_email(b, m["from"], m["subject"], m["body"])
        except Exception as e:
            print(f"  ! email: {e}")
            continue
        if not r["relevant"] or not r["company"]:
            continue
        rec = match(jobs, r["company"], r.get("role") or "")
        if rec is None:
            k = jid(f"{filters.norm(r['company'])}|{filters.norm(r.get('role') or 'application')}|inbox")
            rec = jobs.setdefault(k, {"id": k, "company": r["company"], "title": r.get("role") or "Application",
                                      "url": "", "locations": [], "source": "Inbox", "first_seen": store.now().isoformat(),
                                      "status": "applied", "stages": [], "pros": [], "cons": [], "stream": "summer",
                                      "track": "other", "firm_type": "other", "cpt": "ok", "deadline": None})
        advance(rec, r["event"], m["date"][:10] or store.today_iso(), m["subject"])
        if r.get("action"):
            rec["action"] = {"text": r["action"], "due": r.get("due"), "from": m["subject"]}
    state["mail_seen"] = sorted(done)[-2000:]


def match(jobs: dict, company: str, role: str):
    c = filters.norm(company)
    cands = [r for r in jobs.values() if c and (c in filters.norm(r["company"]) or filters.norm(r["company"]) in c)]
    if not cands:
        return None
    rn = set(filters.norm(role).split())
    return max(cands, key=lambda r: (len(rn & set(filters.norm(r["title"]).split())), r["status"] != "new"))


def advance(rec: dict, event: str, when: str, note: str = "") -> None:
    rec.setdefault("stages", []).append({"event": event, "date": when, "note": note[:120]})
    if event in CLOSED or event in ("rejected", "withdrawn"):
        rec["status"] = event
        rec.pop("action", None)
    elif event in STAGE_ORDER and STAGE_ORDER.index(event) > STAGE_ORDER.index(rec.get("status", "new") if rec.get("status") in STAGE_ORDER else "new"):
        rec["status"] = event


def replies(b: dict, state: dict) -> None:
    """Your replies to the digest email and messages to the Telegram bot become feedback."""
    texts = []
    try:
        for m in notify.recent_mail(days=3):
            if notify.is_reply_to_digest(m) and m["id"] not in state.get("replies_seen", []):
                texts.append(notify.strip_quote(m["body"]))
                state.setdefault("replies_seen", []).append(m["id"])
    except Exception as e:
        print(f"  ! replies: {e}")
    try:
        tg, state["tg_offset"] = notify.telegram_replies(state.get("tg_offset", 0))
        texts += tg
    except Exception as e:
        print(f"  ! telegram: {e}")
    for t in texts:
        handle_reply(t)


def handle_reply(text: str) -> None:
    yes = re.findall(r"\byes\s+(\d+|all)\b", text, re.I)
    no = re.findall(r"\bno\s+(\d+)\b", text, re.I)
    sugs = store.load(store.path("suggestions.json"), [])
    for y in yes:
        for i, s in enumerate(sugs, 1):
            if s["state"] == "open" and (y.lower() == "all" or int(y) == i):
                apply_change(i)
    for n in no:
        dismiss(int(n))
    rest = re.sub(r"\b(yes\s+(\d+|all)|no\s+\d+)\b", "", text, flags=re.I).strip(" ,.\n")
    if len(rest) > 3:
        store.append_jsonl(store.path("feedback.jsonl"), {"date": store.today_iso(), "text": rest, "via": "reply"})


def suggest(b: dict, state: dict, jobs: dict) -> None:
    """Turn feedback that has not been looked at yet into suggested brief changes."""
    fb = store.read_jsonl(store.path("feedback.jsonl"))
    new = fb[state.get("feedback_done", 0):]
    if not new:
        return
    try:
        r = llm.propose(b, new)
    except Exception as e:
        print(f"  ! suggestions: {e}")
        return
    sugs = store.load(store.path("suggestions.json"), [])
    for c in r["changes"]:
        sugs.append({"date": store.today_iso(), "summary": c["summary"], "why": c["why"], "patch": c["patch"], "state": "open"})
    for u in r["status_updates"]:
        rec = match(jobs, u["company"], "")
        if rec:
            advance(rec, u["event"], store.today_iso(), "you said so")
    store.save(store.path("suggestions.json"), sugs)
    state["feedback_done"] = len(fb)


def apply_change(n: int) -> None:
    sugs = store.load(store.path("suggestions.json"), [])
    s = sugs[n - 1]
    b = store.brief()
    for p in s["patch"]:
        keys = p["path"].split(".")
        obj = b
        for k in keys[:-1]:
            obj = obj.setdefault(k, {})
        last = keys[-1]
        if p["op"] == "set":
            obj[last] = p["value"]
        elif p["op"] == "add":
            lst = obj.setdefault(last, [])
            if p["value"] not in lst:
                lst.append(p["value"])
        elif p["op"] == "remove" and p["value"] in obj.get(last, []):
            obj[last].remove(p["value"])
    b.setdefault("history", []).insert(0, {"date": store.today_iso(), "change": s["summary"], "why": s["why"]})
    store.save_brief(b)
    s["state"] = "applied"
    store.save(store.path("suggestions.json"), sugs)
    print(f"Applied: {s['summary']}")


def dismiss(n: int) -> None:
    sugs = store.load(store.path("suggestions.json"), [])
    if 0 < n <= len(sugs):
        sugs[n - 1]["state"] = "dismissed"
        store.save(store.path("suggestions.json"), sugs)


def days_to(d) -> int:
    try:
        return (date.fromisoformat(str(d)[:10]) - date.today()).days
    except (TypeError, ValueError):
        return 9999


def deliver(b: dict, jobs: dict, state: dict, log: dict, dry: bool) -> None:
    d = b.get("delivery", {})
    urg = b.get("urgent", {"min_score": 9, "deadline_hours": 72})
    pings = []
    for rec in jobs.values():
        if rec["status"] in CLOSED:
            continue
        key = rec["id"]
        a = rec.get("action")
        if a and f"a:{key}:{a['text']}" not in state.get("pinged", []):
            pings.append((f"a:{key}:{a['text']}", f"{rec['company']}: {a['text']}" + (f" by {a['due']}" if a.get("due") else ""), rec.get("url", "")))
        if rec["status"] == "new" and rec.get("score", 0) >= urg.get("min_score", 9) and f"s:{key}" not in state.get("pinged", []):
            pings.append((f"s:{key}", f"New {rec['score']}/10: {rec['company']}, {rec['title']}", rec["url"]))
        if rec["status"] in ("new", "saved") and rec.get("score", 0) >= 7 and 0 <= days_to(rec.get("deadline")) * 24 <= urg.get("deadline_hours", 72) and f"d:{key}" not in state.get("pinged", []):
            pings.append((f"d:{key}", f"Due {rec['deadline']}: {rec['company']}, {rec['title']} ({rec['score']}/10)", rec["url"]))
        if rec["status"] == "new" and rec.get("stream") == "campus" and rec.get("score", 0) >= 7 and f"c:{key}" not in state.get("pinged", []):
            pings.append((f"c:{key}", f"On-campus opening: {rec['company']}, {rec['title']}", rec["url"]))

    since = state.get("last_digest", "")
    new = sorted([r for r in jobs.values() if r["status"] == "new" and r.get("first_seen", "") > since and r.get("score", 0) >= b.get("min_score_digest", 7)],
                 key=lambda r: -r["score"])
    soon = sorted([r for r in jobs.values() if r["status"] in ("new", "saved") and 0 <= days_to(r.get("deadline")) <= 7], key=lambda r: r["deadline"])
    moves = [r for r in jobs.values() if r.get("stages") and r["stages"][-1]["date"] >= since[:10]]
    sugs = [(i, s) for i, s in enumerate(store.load(store.path("suggestions.json"), []), 1) if s["state"] == "open"]

    from .digest import render
    subject, html, text = render(b, log, new[:8], len(new), soon, moves, sugs, pings)
    if dry:
        store.save(store.path("last_digest_preview.json"), {"subject": subject, "text": text, "pings": [p[1] for p in pings]})
        print(f"  dry run: digest preview in data/last_digest_preview.json ({len(new)} new, {len(pings)} pings)")
        return
    if new or soon or moves or sugs or pings or d.get("daily_even_if_empty"):
        if notify.send_email(subject, html, text):
            state["last_digest"] = store.now().isoformat()
    ch = d.get("urgent_channel", "email")
    for key, msg, url in pings[:5]:
        if notify.ping(ch, msg, url):
            state.setdefault("pinged", []).append(key)


def main(argv: list) -> None:
    cmd = argv[0] if argv else "run"
    if cmd == "run":
        run()
    elif cmd == "dry-run":
        run(dry=True)
    elif cmd == "dashboard":
        build_dashboard()
    elif cmd == "feedback":
        text = argv[1]
        entry = {"date": store.today_iso(), "text": text, "via": "cli"}
        if "--job" in argv:
            entry["job"] = argv[argv.index("--job") + 1]
        store.append_jsonl(store.path("feedback.jsonl"), entry)
        print("Saved. The next run turns it into a suggested change.")
    elif cmd == "status":
        jobs = store.load(store.path("jobs.json"), {})
        advance(jobs[argv[1]], argv[2], store.today_iso(), argv[3] if len(argv) > 3 else "")
        store.save(store.path("jobs.json"), jobs)
        build_dashboard()
    elif cmd == "apply":
        apply_change(int(argv[1]))
        build_dashboard()
    elif cmd == "dismiss":
        dismiss(int(argv[1]))
        build_dashboard()
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

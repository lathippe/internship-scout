"""Hard filters and duplicate detection. Cheap rules run before any posting reaches Claude."""
from __future__ import annotations

import re

RELEVANT = re.compile(
    r"\b(quant|quantitative|research|risk|strats?|strategist|trading|trader|financ|portfolio|"
    r"model validation|data scien|econom|derivative|volatility|investment|markets?)\b", re.I)
INTERN = re.compile(r"\b(intern|internship|summer analyst|summer associate|co-?op|fellow|research assistant)\b", re.I)


def norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\b(inc|llc|lp|l\.p\.|ltd|group|capital|management|securities|financial|the)\b", " ", s)
    s = re.sub(r"\b(20\d\d|summer|fall|spring|winter|intern(ship)?|program)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def city(locs: list) -> str:
    joined = " ".join(locs or []).lower()
    for c, keys in (("nyc", ("new york", "nyc", "manhattan")), ("jersey", ("jersey city", "hoboken")),
                    ("remote", ("remote",))):
        if any(k in joined for k in keys):
            return c
    return norm(joined)[:20]


def fingerprint(j: dict) -> str:
    """Same company, same role, same city counts as one posting, whatever list it came from."""
    return f"{norm(j['company'])}|{norm(j['title'])}|{city(j['locations'])}"


def dedupe(jobs: list) -> list:
    best = {}
    rank = {"Greenhouse": 0, "Ashby": 0, "Lever": 0, "Simplify": 1, "NUFT": 2}
    for j in jobs:
        fp = fingerprint(j)
        j["fp"] = fp
        cur = best.get(fp)
        if cur is None or (rank.get(j["source"], 3), -len(j.get("description", ""))) < (rank.get(cur["source"], 3), -len(cur.get("description", ""))):
            if cur:
                j.setdefault("also_on", []).extend([cur["source"]] + cur.get("also_on", []))
            best[fp] = j
        else:
            cur.setdefault("also_on", []).append(j["source"])
    return list(best.values())


def passes(j: dict, b: dict):
    """Return None if the posting passes, else a short reason. Reasons are counted in the run log."""
    title, company = j.get("title", ""), j.get("company", "")
    text = f"{title} {company} {j.get('category', '')}"
    hard = b.get("hard_filters", {})

    if any(norm(s) and norm(s) in norm(company) for s in b.get("skip_firms", [])):
        return "firm you skip"
    words = [w.lower() for w in hard.get("exclude_words", [])]
    blob = (title + " " + j.get("description", "")[:3000]).lower()
    if any(w and w in blob for w in words):
        return "excluded word"

    if not INTERN.search(title) and j["source"] not in ("Simplify", "NUFT"):
        return "not an internship"
    if not (RELEVANT.search(text) or j.get("category") in ("Quant", "Quantitative Finance")):
        return "not a finance role"

    locs = " ".join(j.get("locations") or []).lower()
    want = [l.lower() for l in hard.get("locations", ["new york", "nyc", "jersey city"])]
    if locs and not any(w in locs for w in want):
        return "location"

    terms = [t.lower() for t in j.get("terms") or []]
    want_terms = [t.lower() for t in hard.get("terms", ["Summer 2027"])]
    if terms and not any(t in want_terms for t in terms) and "n/a" not in terms:
        return "wrong term"
    if not terms:
        m = re.search(r"\b(summer|fall|spring|winter)\s*(20\d\d)\b", title, re.I)
        if m and f"{m.group(1)} {m.group(2)}".lower() not in want_terms:
            return "wrong term"

    degrees = j.get("degrees") or []
    level = hard.get("degree", "Master's")
    if degrees and level not in degrees:
        return "degree level"
    if re.search(r"\b(phd|ph\.d|doctoral)\b", title, re.I) and level != "PhD":
        return "degree level"
    if re.search(r"\b(undergrad|undergraduate|sophomore|freshman|junior)\b", title, re.I) and level != "Bachelor's":
        return "degree level"

    if hard.get("needs_sponsorship_later") and j.get("sponsorship") == "U.S. Citizenship is Required":
        return "citizens only"
    if re.search(r"(u\.?s\.? citizens? only|must be a u\.?s\.? citizen|security clearance)", blob):
        return "citizens only"
    return None

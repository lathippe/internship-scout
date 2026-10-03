"""Where postings come from. Every source returns the same normalized dict:

{source, company, title, url, locations[], terms[], degrees[], sponsorship, posted, description, category}
"""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request

UA = {"User-Agent": "internship-scout/1.0 (+https://github.com)"}

SIMPLIFY = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"
NUFT = "https://raw.githubusercontent.com/northwesternfintech/2027QuantInternships/main/README.md"

# Public job boards checked by hand on 3 Oct 2026. Edit brief.json -> "boards" to add more.
DEFAULT_BOARDS = {
    "greenhouse": {
        "point72": "Point72", "wehrtyou": "Hudson River Trading", "jumptrading": "Jump Trading",
        "drweng": "DRW", "janestreet": "Jane Street", "imc": "IMC", "virtu": "Virtu Financial",
        "towerresearchcapital": "Tower Research Capital", "squarepointcapital": "Squarepoint",
        "schonfeld": "Schonfeld", "gcmgrosvenor": "GCM Grosvenor", "clearstreet": "Clear Street",
        "oldmissioncapital": "Old Mission", "flowtraders": "Flow Traders", "sofi": "SoFi",
        "galaxydigitalservices": "Galaxy", "generalatlantic": "General Atlantic",
    },
    "ashby": {"ramp": "Ramp", "plaid": "Plaid"},
    "lever": {"wealthfront": "Wealthfront"},
}


def get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def text_of(html_str: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", html_str or "")
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(html.unescape(s))
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def simplify() -> list:
    out = []
    for x in json.loads(get(SIMPLIFY, 90)):
        if not (x.get("active") and x.get("is_visible", True)):
            continue
        out.append({
            "source": "Simplify", "company": x.get("company_name", ""), "title": x.get("title", ""),
            "url": x.get("url", ""), "locations": x.get("locations") or [], "terms": x.get("terms") or [],
            "degrees": x.get("degrees") or [], "sponsorship": x.get("sponsorship") or "",
            "posted": x.get("date_posted"), "category": x.get("category") or "", "description": "",
        })
    return out


ROLE_NAMES = {"QR": "Quantitative Research Intern", "QT": "Quantitative Trading Intern",
              "QD": "Quantitative Developer Intern", "SWE": "Software Engineering Intern",
              "HW": "Hardware Intern", "Risk": "Risk Intern"}


def nuft() -> list:
    """The Northwestern quant list is a README: one '## Firm' block per firm with a role table."""
    md = get(NUFT).decode("utf-8", "replace")
    out = []
    for block in re.split(r"\n## ", md)[1:]:
        firm = block.split("\n", 1)[0].strip()
        loc = re.search(r"\*\*Locations\*\*:\s*(.+)", block)
        locs = [l.strip() for l in (loc.group(1) if loc else "").split(",") if l.strip()]
        for row in re.findall(r"^\|([^|\n]+)\|(.+)\|\s*$", block, re.M):
            role, links = row[0].strip(), row[1]
            if role in ("Role", "-------"):
                continue
            for mark, label, url in re.findall(r"\[(✅|🔒)\s*([^\]]*)\]\(([^)]+)\)", links):
                if mark != "✅":
                    continue
                title = ROLE_NAMES.get(role, role + " Intern") + (f" ({label.strip()})" if label.strip() else "")
                out.append({"source": "NUFT", "company": firm, "title": title, "url": url, "locations": locs,
                            "terms": ["Summer 2027"], "degrees": [], "sponsorship": "", "posted": None,
                            "category": "Quant", "description": ""})
    return out


def greenhouse(slug: str, company: str) -> list:
    d = json.loads(get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"))
    return [{"source": "Greenhouse", "company": company, "title": j.get("title", ""), "url": j.get("absolute_url", ""),
             "locations": [(j.get("location") or {}).get("name", "")], "terms": [], "degrees": [], "sponsorship": "",
             "posted": j.get("updated_at"), "category": "", "description": text_of(j.get("content", ""))}
            for j in d.get("jobs", [])]


def ashby(slug: str, company: str) -> list:
    d = json.loads(get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}"))
    return [{"source": "Ashby", "company": company, "title": j.get("title", ""), "url": j.get("jobUrl", ""),
             "locations": [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations") or []],
             "terms": [], "degrees": [], "sponsorship": "", "posted": j.get("publishedAt"), "category": "",
             "description": j.get("descriptionPlain") or text_of(j.get("descriptionHtml", ""))}
            for j in d.get("jobs", [])]


def lever(slug: str, company: str) -> list:
    d = json.loads(get(f"https://api.lever.co/v0/postings/{slug}?mode=json"))
    return [{"source": "Lever", "company": company, "title": j.get("text", ""), "url": j.get("hostedUrl", ""),
             "locations": [(j.get("categories") or {}).get("location", "")], "terms": [], "degrees": [],
             "sponsorship": "", "posted": j.get("createdAt"), "category": "",
             "description": j.get("descriptionPlain", "") + "\n" + text_of(j.get("additional", ""))}
            for j in d]


def fetch_all(brief: dict, log=print) -> list:
    boards = brief.get("boards") or DEFAULT_BOARDS
    jobs, errors = [], []
    for name, fn in (("Simplify", simplify), ("NUFT", nuft)):
        try:
            got = fn()
            jobs += got
            log(f"  {name}: {len(got)}")
        except Exception as e:  # one broken source must not stop the run
            errors.append(f"{name}: {e}")
    for kind, fn in (("greenhouse", greenhouse), ("ashby", ashby), ("lever", lever)):
        n = 0
        for slug, company in (boards.get(kind) or {}).items():
            try:
                got = fn(slug, company)
                jobs += got
                n += len(got)
            except Exception as e:
                errors.append(f"{kind}/{slug}: {e}")
        log(f"  {kind}: {n}")
    for e in errors:
        log(f"  ! {e}")
    return jobs


def page_text(url: str) -> str:
    """Full text of a posting page, for sources that only give a link."""
    try:
        return text_of(get(url, 25).decode("utf-8", "replace"))[:40000]
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return ""

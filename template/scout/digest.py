"""The morning email. Short on purpose: what's new, what's due, what moved, what to confirm."""
from __future__ import annotations

import html as h

INK, MUTED, ACCENT, GOOD, CRIT, LINE = "#17151f", "#6c6981", "#57068c", "#1b6e45", "#a8201a", "#e2e1ea"


def _e(s) -> str:
    return h.escape(str(s or ""))


def render(b, log, new, n_new, soon, moves, sugs, pings):
    name = b.get("name", "")
    subject = f"{n_new} new match{'es' if n_new != 1 else ''}" + (f", {len(soon)} due this week" if soon else "")
    T, H = [], []

    def sec(title):
        T.append(f"\n{title.upper()}")
        H.append(f'<h2 style="font:600 17px Arial,sans-serif;color:{INK};margin:26px 0 8px">{_e(title)}</h2>')

    H.append(f'<div style="max-width:620px;margin:0 auto;font:15px/1.5 Arial,sans-serif;color:{INK}">')
    H.append(f'<p style="color:{MUTED};margin:0 0 4px">Good morning{", " + _e(name) if name else ""}. Read {log.get("read", 0)} postings, {log.get("new", 0)} new passed your filters.</p>')

    if pings:
        sec("Needs you")
        for _, msg, url in pings:
            T.append(f"- {msg} {url}")
            H.append(f'<p style="margin:6px 0"><b style="color:{CRIT}">●</b> {_e(msg)}' + (f' <a href="{_e(url)}" style="color:{ACCENT}">Open</a>' if url else "") + "</p>")

    if new:
        sec("New matches")
        for r in new:
            T.append(f"- {r['score']}/10 {r['company']}, {r['title']}\n  + {'; '.join(r.get('pros', [])[:2])}\n  - {'; '.join(r.get('cons', [])[:2])}\n  {r['url']}")
            H.append(
                f'<table role="presentation" style="width:100%;border-top:1px solid {LINE};padding:10px 0"><tr>'
                f'<td style="width:48px;vertical-align:top;font:700 22px Arial,sans-serif">{r["score"]}</td>'
                f'<td style="vertical-align:top"><a href="{_e(r["url"])}" style="color:{INK};font-weight:700;text-decoration:none">{_e(r["company"])}</a><br>'
                f'<span style="color:{MUTED}">{_e(r["title"])}</span><br>'
                + "".join(f'<span style="color:{GOOD};font-size:13px">+ {_e(p)}</span>&nbsp;&nbsp; ' for p in r.get("pros", [])[:2])
                + "".join(f'<span style="color:{CRIT};font-size:13px">− {_e(c)}</span>&nbsp;&nbsp; ' for c in r.get("cons", [])[:1])
                + (f'<br><span style="font-size:13px;color:{MUTED}">Due {_e(r["deadline"])}</span>' if r.get("deadline") else "")
                + "</td></tr></table>")
        if n_new > len(new):
            T.append(f"  and {n_new - len(new)} more on the dashboard")
            H.append(f'<p style="color:{MUTED}">and {n_new - len(new)} more on the dashboard</p>')

    if soon:
        sec("Due in the next 7 days")
        for r in soon:
            T.append(f"- {r['deadline']} {r['company']}, {r['title']} ({r['score']}/10)")
            H.append(f'<p style="margin:4px 0"><b>{_e(r["deadline"])}</b> {_e(r["company"])}, {_e(r["title"])} <span style="color:{MUTED}">{r["score"]}/10</span></p>')

    if moves:
        sec("Applications")
        for r in moves:
            st = r["stages"][-1]
            T.append(f"- {r['company']}: {st['event']} ({st['date']})")
            H.append(f'<p style="margin:4px 0">{_e(r["company"])}: <b>{_e(st["event"])}</b> <span style="color:{MUTED}">{_e(st["date"])}</span></p>')

    if sugs:
        sec("Suggested changes to your brief")
        for i, s in sugs:
            T.append(f"{i}. {s['summary']} ({s['why']})")
            H.append(f'<p style="margin:6px 0"><b>{i}.</b> {_e(s["summary"])}<br><span style="color:{MUTED};font-size:13px">{_e(s["why"])}</span></p>')
        T.append("Reply 'yes 1' to apply, 'no 1' to drop, or 'yes all'.")
        H.append(f'<p style="color:{MUTED};font-size:13px">Reply <b>yes 1</b> to apply, <b>no 1</b> to drop, or <b>yes all</b>.</p>')

    url = b.get("delivery", {}).get("dashboard_url")
    foot = "Reply to this email in your own words to tune the scout, e.g. 'no crypto' or 'more risk roles'."
    T.append("\n" + foot + (f"\nDashboard: {url}" if url else ""))
    H.append(f'<p style="color:{MUTED};font-size:13px;border-top:1px solid {LINE};padding-top:12px;margin-top:26px">{_e(foot)}'
             + (f'<br><a href="{_e(url)}" style="color:{ACCENT}">Open your dashboard</a>' if url else "") + "</p></div>")
    return subject, "".join(H), "\n".join(T)

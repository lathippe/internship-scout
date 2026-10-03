---
name: scout-dashboard
description: Open or change the internship scout dashboard. Rebuilds docs/index.html from the latest data and opens it, or publishes it as a private page. Also the place for any change to how the dashboard looks or works. Use on "/scout-dashboard", "show my dashboard", "open the scout", "change the dashboard".
---

# Dashboard

## Open it

1. Read `~/.internship-scout.json`, `git -C <path> pull -q`.
2. `cd <path> && python3 -m scout dashboard` (needs only Python 3.9+, no packages).
3. Open `docs/index.html` (macOS `open`, Linux `xdg-open`). If the session can publish private pages (an Artifact tool is available), offer that too so it opens on the phone.
4. If `brief.json` has `delivery.dashboard_url`, the same page is also there after every run.

Then give a 3-line summary: due in the next 7 days, interview stages that moved, open suggested changes.

## How feedback flows back

The page saves Good fit / Not for me, reasons, notes, and "I applied" in the browser. The bar at the bottom copies them as one "Scout feedback" block. The user pastes it as a reply to the morning email (the next run reads it) or into Claude with `/scout-feedback` (applied right away).

## Changing the dashboard

The page is `template`-built from `scout/dashboard_template.html` with the data injected at `/*SCOUT_DATA*/null`. Edit the template, never `docs/index.html`, then rebuild. Keep these rules; they are the reason the page works:

- **Little text, more hovers.** No repeated explanations on every row. Details live in tooltips (`data-tip`): the score breakdown, exact dates, why a brief line changed, what a CPT tag means.
- **Pros and cons on every role.** One of each in the row, all of them when the row opens.
- **Feedback on every role.** Good fit / Not for me with reason chips and a free note, plus "I applied". Feedback must end up in the scout (copy bar, email reply, or `/scout-feedback`), never stay only in the page.
- **Interview stages visible.** Every application shows its stages (Applied, Online test, First round, Final round, Offer) with dates, in the row and in the Interviews panel. Rejections stay visible, without drama.
- **The brief leads.** The top of the page says in one headline what she is looking for, with the brief lines next to it and a mark on lines that changed from feedback.
- **Color means something.** Score shade = match strength. Red only for due in 3 days or failed. Green only for good signs. No decorative color, no colored side stripes, no small-caps labels above headings.
- **Both themes, phone width.** Keep the light and dark tokens; check at 400 px wide.

Run `node --check` on the extracted script after edits if Node is available, rebuild, open, and look at it once before committing.

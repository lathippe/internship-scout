---
name: scout-feedback
description: Tune the internship scout from the user's words. Turns feedback ("no crypto", "mentorship matters more", a pasted "Scout feedback" block from the dashboard) into concrete brief changes they confirm, records application events (applied, test, interview, rejected, offer), and applies or dismisses suggested changes. Use on "/scout-feedback", "tell the scout", "I applied to", "I got rejected", "stop sending me", "more like", "apply suggestion 2".
---

# Feedback

1. Read `~/.internship-scout.json` for the repo path. `git -C <path> pull -q`. Read `brief.json`, `data/jobs.json`, `data/suggestions.json`.
2. Sort what they said into three kinds. One message can contain all three.

### Application events
"I applied to Two Sigma", "HRT sent a test", "Jump rejected me", a dashboard line with "I applied".
Find the job in `jobs.json` by id in brackets, or by company and title. Run, from the repo:
`python3 -m scout status <id> applied|test|interview|final|offer|rejected|withdrawn "short note"`
If the job isn't there, add it to jobs.json with the same fields other records have (id = 8 hex chars, source "You").
Confirm in one line per event: "Two Sigma: applied, 3 Oct".

### Preferences
"No crypto", "more risk roles", "mentorship matters more than brand", "skip Citadel", reasons on the dashboard like "Too much trading".
Turn them into the smallest edit to brief.json. Allowed fields: `weights.*`, `tracks.*`, `firm_types.*`, `hard_filters.exclude_words|locations|terms`, `skip_firms`, `dream_firms`, `streams`, `notes`.
Show the change before writing it, in plain words, with the before and after:

> Score trading roles lower: Trading 0.4 → 0.2
> Why: you marked 2 trading roles "Not for me", "too much mental math"

Ask once to confirm (AskUserQuestion: Apply / Change it / Skip). On Apply, edit brief.json and insert at the top of `history`: `{"date": today, "change": "<summary>", "why": "<their words>"}`.
A single thumbs-down is weak evidence. If only one role points that way, suggest a small step (0.1 to 0.2) or a note, not a hard filter.

### Suggested changes waiting
If `suggestions.json` has open items (the morning run made them from email replies), list them numbered and offer to apply or dismiss: `python3 -m scout apply N` / `python3 -m scout dismiss N`.

3. Rescore: if weights, tracks, or firm types changed, the next run rescores automatically. To see it now, run `python3 -m scout dashboard`.
4. Commit and push: `git add -A && git commit -m "Feedback: <summary>" && git push`.
5. End with one line on what changes in tomorrow's email.

---
name: scout-check
description: Full read of one internship posting against the user's scout brief. Score, pros and cons, gaps, what to stress in the CV, visa (CPT) check, and who to ask for a referral. Use on "/scout-check <link>", "is this a good fit", "look at this posting", or when the user pastes a job link or description.
---

# Check one posting

1. Read `~/.internship-scout.json` for the repo path, `git -C <path> pull -q`, then read `<path>/brief.json`. If there is no brief, offer `/scout-setup` first, but still review the posting against what the user tells you.
2. Get the posting: WebFetch the link, or use the pasted text. If the page needs a login, ask them to paste the text.
3. Check `<path>/data/jobs.json` for the same company and title; if the scout already scored it, show that score and say so.

## Answer format

Keep it scannable. No preamble.

**Company, Title** · Location · Deadline (or "rolling")

**Score X.X of 10.** One line why. Rate fit, mentorship, brand, pay 0 to 10 like the scout does and combine with the brief's `weights`; show the four numbers in one line.

**Pros** (2 to 4, each under 8 words, specific to them)
**Cons** (1 to 3, same)

**Visa:** CPT fits / ask the school first / no CPT needed, with one reason. Flag "US citizens only", "no sponsorship now or in the future", or clearance requirements loudly.

**Gaps:** what the posting asks for that the background doesn't show, and how to close each one in a week (a project, a course module, a line in the CV).

**In your CV and cover letter, stress:** 2 to 3 points from their `background` mapped to the posting's words.

**Referral:** who to look for on LinkedIn (school alumni at the firm, people on the named team), plus a 3-sentence message they can adapt.

**Verdict:** apply now / apply this week / skip, in one line.

## After

- If they say they applied, append to `data/feedback.jsonl` a line `{"date": today, "text": "I applied to <Company>, <Title>", "via": "claude"}` and run `python3 -m scout status <id> applied` if the job has an id. Commit and push.
- If their reaction reveals a preference ("I don't want trading"), offer to add it to the brief via `/scout-feedback`.

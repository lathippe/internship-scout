# Internship Scout

A Claude Code plugin that runs your internship search every morning and learns what you want.

- **Setup chat.** 10 questions about your goal, visa, tracks, firms, and priorities become your brief.
- **Daily search.** Reads about 6,000 postings from the Simplify Summer 2027 list, the Northwestern quant list, and 20 firm job boards. Removes duplicates, drops what breaks your rules, and has Claude score the rest on research fit, mentorship, brand, and pay.
- **Morning email.** New matches with score, pros and cons, deadlines this week, application updates, and suggested changes to your brief.
- **Urgent pings.** WhatsApp, Telegram, push, or email, only for a 9/10 role, a deadline under 72 hours, an on-campus opening, or an interview slot to pick.
- **Interview tracking.** Reads your inbox (read-only) for confirmations, tests, interviews, and rejections, and moves each application through its stages.
- **Learns from you.** Reply to the email in your own words or use `/scout-feedback`. Every change to the brief is shown first and logged.
- **Dashboard.** One page with your brief, the next 7 days, deadlines, every role with pros and cons, interview stages, and a feedback bar.

It runs on GitHub Actions in your own private repo, so your laptop can be off. Everything it knows is plain JSON you can read.

## Install

You need [Claude Code](https://claude.com/claude-code), a GitHub account, and a Gmail address.

```
/plugin marketplace add OWNER/internship-scout
/plugin install internship-scout@internship-scout
/scout-setup
```

The setup chat takes about 15 minutes and does the rest: creates your private repo, connects your keys (you type secrets into GitHub directly, never into the chat), and runs the first search.

## Use

| Command | What it does |
|---|---|
| `/scout-setup` | First setup, or change delivery later |
| `/scout-check <link>` | Full read of one posting: score, pros, cons, gaps, CV points, referral message |
| `/scout-feedback <words>` | "No crypto", "I applied to Two Sigma", "apply suggestion 2" |
| `/scout-dashboard` | Rebuild and open the dashboard |

## Cost

- GitHub Actions: free for this (about 10 minutes a day).
- Anthropic API: about $5 to $15 a month with the default model at low effort. Set a monthly limit in the Anthropic console. Switch to `claude-sonnet-5-5` in `brief.json` to spend less.
- WhatsApp test number, Telegram, ntfy: free.

## Privacy

- Your brief, matches, and feedback live in your private repo.
- The inbox reader is read-only and only sends Claude messages that look like application emails.
- Secrets are GitHub Actions secrets. The plugin never asks you to paste them into a chat.

## Files in your repo

| Path | What |
|---|---|
| `brief.json` | What you're looking for. Safe to edit by hand. |
| `data/jobs.json` | Every role the scout scored, with stages |
| `data/feedback.jsonl` | Everything you told it |
| `data/suggestions.json` | Brief changes waiting for your yes |
| `docs/index.html` | The dashboard |
| `.github/workflows/scout.yml` | The schedule |

Run locally without Claude or sending anything: `python3 -m scout dry-run`.

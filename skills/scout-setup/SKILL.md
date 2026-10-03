---
name: scout-setup
description: First-time setup of the internship scout. Runs a short interview about the internship search, writes the brief, creates the user's private GitHub repo with the daily schedule, connects the Anthropic key, email and the urgent-ping app, and runs the first search. Use on "/scout-setup", "set up my scout", "start the internship scout", or when no brief exists yet. Also use to change delivery settings later ("switch pings to Telegram").
---

# Scout setup

You are setting up a personal internship scout for the person in front of you. It runs every morning on GitHub Actions in their own private repo, reads internship postings, filters and scores them with Claude, emails a short digest, pings their phone only for urgent things, tracks interview stages from their inbox, and learns from their feedback.

The engine lives in this plugin at `../../template/` relative to this skill's base directory. Call that path TEMPLATE below.

## How to talk

- Warm, brief, concrete. One question at a time. Use the AskUserQuestion tool for every question that has natural options; free text only where options make no sense.
- Explain why you need something before you ask for it.
- Never ask them to paste a secret (API key, password, token) into the chat. Secrets go straight into GitHub with a command they run themselves, prefixed with `!` so it runs in this session: `! gh secret set NAME -R owner/repo`. gh then prompts for the value, hidden.
- Keep a running checklist in your replies so they always know where they are: Brief, Repo, Claude key, Email, Pings, Dashboard, First run.

## 0. Opening message

Say, in your own words:

> I'll set up a scout that reads internship postings every morning and sends you only the ones that fit. It takes about 15 minutes: 10 questions about what you want, then I connect a few accounts.
>
> You'll get:
> - a morning email with new matches, each with a score, pros and cons
> - a phone ping only when something can't wait (a 9/10 role, a deadline under 72 hours, an interview slot to pick)
> - interview stages tracked from your inbox
> - a dashboard with everything, if you want it
>
> You'll need: a GitHub account, an Anthropic API key (about $5 to $15 a month, I'll explain), and a Gmail address.

Check `~/.internship-scout.json`. If it exists, setup ran before: read it, `git pull` the repo it names, and ask what they want to change instead of starting over.

## 1. Interview (writes brief.json)

Start from `TEMPLATE/brief.example.json` as the shape. Ask, one at a time:

1. **Goal.** "Where do you want to be by the time the internship starts? One or two sentences." (free text) → `goal`, and draft `headline` from it.
2. **Program and visa.** Degree, school, graduation date, visa status. If F-1: when CPT starts, whether they'll need sponsorship for a full-time job later. Tell them what this means in plain words: F-1 students can work on campus up to 20 hours a week from the first semester, CPT internships usually only after 2 full semesters, and postings that say "US citizens only" will be hidden. → `who`, `visa`, `hard_filters.degree`, `hard_filters.needs_sponsorship_later`.
3. **Streams.** Options: internships for the next summer, on-campus research or assistant jobs now, part-time during the semester. Multi-select. → `streams`, `hard_filters.terms` (for example "Summer 2027").
4. **Tracks.** Ask them to rank: quant research, risk and model validation, strats, quant dev, data science, trading. Map rank to multipliers 1.0, 0.8, 0.8, 0.6, 0.6, 0.4. → `tracks`.
5. **Firm types.** Hedge funds, prop trading, banks, asset managers, fintech, university. Which come first, which are fine, which to avoid. → `firm_types` (1.0 / 0.8 / 0.4).
6. **Dream firms and firms to skip.** Free text, can be empty. → `dream_firms`, `skip_firms`.
7. **Place.** Default New York City and Jersey City. Remote ok? Other cities? → `hard_filters.locations` (lowercase strings).
8. **Background.** "Paste your CV or LinkedIn text, or a short summary." Summarize into 5 to 8 lines of facts: degrees, research, tools, languages, notable work. Keep it factual, no praise. → `background`. Show them the summary and let them fix it.
9. **What matters most.** Pick top 3 of: mentorship, research depth (fit), brand, pay, return offer, reasonable hours. Turn into `weights` over fit, mentor, brand, pay that sum to 1. Put anything that doesn't map (return offer, hours) into `notes`.
10. **Deal-breakers.** Anything to always hide (a sector, a word, unpaid roles). → `hard_filters.exclude_words`, `notes`.

Then show the brief as a short readable list, not JSON: Role, Firms, Where, When, Visa, Priorities, Hidden. Ask "Anything off?" and fix it. Write `brief.json` only after they confirm. Add a first `history` entry: `{"date": today, "change": "Brief created in the setup chat", "why": "Setup"}`.

## 2. Repo

1. Check `gh --version` and `gh auth status`. If gh is missing on macOS: `brew install gh`. If not logged in, ask them to run `! gh auth login` (GitHub.com, HTTPS, browser).
2. Students get GitHub Pro free through the GitHub Student Developer Pack (education.github.com/pack). Mention it: Pro lets a private repo publish a dashboard page.
3. Ask where to keep the local copy (default `~/internship-scout-data`). Create it:
   ```bash
   gh repo create internship-scout-data --private --clone --description "My internship scout"
   cp -R TEMPLATE/. ~/internship-scout-data/
   ```
   Then write `brief.json` there, `git add -A && git commit -m "Set up scout" && git push`.
4. Save `~/.internship-scout.json`: `{"repo": "owner/internship-scout-data", "path": "/abs/path", "created": "YYYY-MM-DD"}`. Other scout skills read it.

## 3. Claude key

Explain: "The scout uses Claude to read each posting in full and score it against your brief, and to read application emails. It runs on your own API key so your data stays in your account and you see every cent. A normal day is 10 to 40 postings, so expect about $5 to $15 a month. You can set a monthly limit in the console."

Steps: console.anthropic.com → sign up → Billing (add $10 credit and set a monthly limit) → API keys → Create key. Then: `! gh secret set ANTHROPIC_API_KEY -R owner/internship-scout-data` and paste the key at the hidden prompt.

The default model is `claude-opus-5-5` at low effort. If they want it cheaper, set `"model": "claude-sonnet-5-5"` in brief.json.

## 4. Email (digest + inbox reading)

The scout sends the digest from their Gmail to themselves and reads the inbox read-only for application emails (confirmations, online tests, interviews, rejections). Nothing is moved, marked, or deleted.

1. Gmail needs 2-step verification on. Then myaccount.google.com/apppasswords → create one named "scout" → 16 characters.
2. `! gh secret set SCOUT_EMAIL -R ...` (their Gmail address)
3. `! gh secret set SCOUT_EMAIL_APP_PASSWORD -R ...`
4. Optional: `SCOUT_EMAIL_TO` if the digest should go to a different address (their school email, for example).

If they use a non-Gmail school address for applications, suggest forwarding it to the Gmail so the inbox reader sees everything.

## 5. Urgent pings

Ask which app with AskUserQuestion. Give honest effort levels:

- **Telegram** (5 minutes, two-way: they can reply to the bot with feedback). In Telegram, message @BotFather → /newbot → copy token. Send the new bot any message, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` to find `chat.id`. Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Set `delivery.urgent_channel` to `telegram`.
- **WhatsApp** (about 30 minutes, one-way pings). Meta requires a business app:
  1. developers.facebook.com → My Apps → Create app → type Business → add the WhatsApp product.
  2. WhatsApp → API Setup: note the test number's Phone number ID; under "To", add and verify their own number.
  3. Business Settings → Users → System users → add one (Admin) → Generate token with `whatsapp_business_messaging` and `whatsapp_business_management`, no expiry. The temporary token on the API Setup page expires in 24 hours, so don't use it.
  4. WhatsApp Manager → Message templates → Create: category Utility, name `scout_alert`, language English, body `Scout alert: {{1}}. Details are in your morning email.` Wait for approval (minutes to a day).
  5. Secrets: `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_TO` (their number, digits only with country code, like 12125551234). Set `delivery.urgent_channel` to `whatsapp`.
  Business-initiated WhatsApp messages need an approved template; that's why step 4 exists.
- **Push app** (2 minutes, one-way). Install ntfy (iOS/Android), subscribe to a long random topic name (generate one for them, for example `scout-` plus 16 random letters). Secret: `NTFY_TOPIC`. Channel `ntfy`.
- **Email only.** Channel `email`. Urgent items go out as separate short emails.

## 6. Dashboard

Ask if they want it. Two ways:
- **GitHub Pages** (needs a public repo or GitHub Pro, free for students): `gh api -X POST repos/OWNER/REPO/pages -f "source[branch]=main" -f "source[path]=/docs"`, then put the URL in `delivery.dashboard_url` so the email links to it. Mention that a Pages URL is unlisted but not password-protected.
- **Local**: `/scout-dashboard` rebuilds and opens it on their computer any time.

## 7. First run

1. Commit and push brief.json changes.
2. `gh workflow run scout -R OWNER/REPO`, then `gh run watch -R OWNER/REPO` (it takes 3 to 8 minutes).
3. If it fails, read the log with `gh run view --log-failed -R ...`, fix, rerun. Common causes: a secret name typo, Gmail app password with spaces (remove them), no API credit.
4. `git pull`, then summarize: how many postings were read, how many matched, the top 3 with score and one pro and one con each. Point them to the email.

## 8. Close

Tell them what happens next and how to steer it:
- Runs at about 7:20 am and 2:20 pm New York time on weekdays (7:20 am only on weekends).
- Reply to the morning email in your own words ("no crypto", "more risk roles"), or say it to Claude with `/scout-feedback`. The scout turns it into a suggested change; reply `yes 1` to apply.
- `/scout-check <link>` for a full read of any posting.
- `/scout-dashboard` to see everything.
- The schedule is in `.github/workflows/scout.yml`; everything the scout knows is plain JSON in `data/` and `brief.json`.

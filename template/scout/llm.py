"""Every Claude call the scout makes. Three jobs: score a posting, read an email, turn feedback into a brief change."""
from __future__ import annotations

import json
import os

try:
    import anthropic
except ImportError:  # local dry runs work without the SDK
    anthropic = None

DEFAULT_MODEL = "claude-opus-5-5"


def _client():
    if anthropic is None:
        raise RuntimeError("Install the SDK: pip install -r requirements.txt")
    return anthropic.Anthropic()


def available() -> bool:
    return anthropic is not None and bool(os.environ.get("ANTHROPIC_API_KEY"))


def ask_json(brief: dict, system: str, prompt: str, schema: dict, max_tokens: int = 4000) -> dict:
    """One request with a JSON schema on the output. Falls back to a second model if the first one declines."""
    client = _client()
    params = dict(
        model=brief.get("model", DEFAULT_MODEL),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": brief.get("effort", "low"),
                       "format": {"type": "json_schema", "schema": schema}},
    )
    try:
        resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params)
    except anthropic.BadRequestError:
        resp = client.messages.create(**params)
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Answer was cut off; raise max_tokens")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


SCORE_SCHEMA = _obj({
    "fit": {"type": "number", "description": "0-10, how well the work matches her goal and background"},
    "mentor": {"type": "number", "description": "0-10, evidence of mentorship, structured program, small class"},
    "brand": {"type": "number", "description": "0-10, how much the name helps a quant research career"},
    "pay": {"type": "number", "description": "0-10, pay versus other quant internships; 5 if unknown"},
    "track": {"type": "string", "enum": ["research", "risk", "strats", "dev", "data", "trading", "other"]},
    "firm_type": {"type": "string", "enum": ["hf", "prop", "bank", "am", "fin", "campus", "other"]},
    "stream": {"type": "string", "enum": ["summer", "campus", "fall", "other"]},
    "cpt": {"type": "string", "enum": ["ok", "check", "none"],
            "description": "ok = clearly financial engineering work; check = may not count, ask the school; none = on-campus, no CPT needed"},
    "deadline": {"type": ["string", "null"], "description": "YYYY-MM-DD if the posting states one"},
    "pros": {"type": "array", "items": {"type": "string"}, "description": "2-3 items, max 7 words each, concrete"},
    "cons": {"type": "array", "items": {"type": "string"}, "description": "1-3 items, max 7 words each, concrete"},
    "dealbreaker": {"type": ["string", "null"], "description": "set only if the posting breaks a hard rule in the brief"},
})

SCORE_SYSTEM = """You read internship postings for one student and rate them against her brief.
Be specific and honest. Pros and cons are short phrases a person can scan in a second, written to her ("your causal inference work"), never generic ("great opportunity").
Only use facts in the posting or the brief. If something is unknown, say so in a con, do not guess."""


def score(brief: dict, job: dict) -> dict:
    prompt = (f"<brief>\n{json.dumps(_brief_for_llm(brief), ensure_ascii=False, indent=1)}\n</brief>\n\n"
              f"<posting>\nCompany: {job['company']}\nTitle: {job['title']}\nLocations: {', '.join(job.get('locations') or [])}\n"
              f"Terms: {', '.join(job.get('terms') or [])}\nURL: {job['url']}\n\n{job.get('description') or '(no description available)'}\n</posting>")
    return ask_json(brief, SCORE_SYSTEM, prompt, SCORE_SCHEMA, 2000)


EMAIL_SCHEMA = _obj({
    "relevant": {"type": "boolean", "description": "true only for messages about her own job applications"},
    "company": {"type": ["string", "null"]},
    "role": {"type": ["string", "null"]},
    "event": {"type": "string", "enum": ["applied", "test", "interview", "final", "offer", "rejected", "other"]},
    "action": {"type": ["string", "null"], "description": "what she must do, max 8 words, or null"},
    "due": {"type": ["string", "null"], "description": "YYYY-MM-DD for the action, if stated"},
})


def read_email(brief: dict, sender: str, subject: str, body: str) -> dict:
    prompt = f"From: {sender}\nSubject: {subject}\n\n{body[:20000]}"
    return ask_json(brief, "You sort a student's email. Decide if this message is about one of her job applications and what stage it signals.", prompt, EMAIL_SCHEMA, 800)


CHANGE_SCHEMA = _obj({
    "changes": {"type": "array", "items": _obj({
        "summary": {"type": "string", "description": "one line, plain English, e.g. 'Score trading roles lower'"},
        "why": {"type": "string", "description": "her words or the pattern behind it"},
        "patch": {"type": "array", "items": _obj({
            "op": {"type": "string", "enum": ["set", "add", "remove"]},
            "path": {"type": "string", "description": "dot path in the brief, e.g. weights.mentor or hard_filters.exclude_words"},
            "value": {"type": ["string", "number", "boolean", "null"]},
        })},
    })},
    "status_updates": {"type": "array", "items": _obj({
        "company": {"type": "string"}, "event": {"type": "string", "enum": ["applied", "test", "interview", "final", "offer", "rejected", "withdrawn"]},
    })},
})

CHANGE_SYSTEM = """You maintain a student's internship search brief. You get the brief and her recent feedback.
Propose the smallest changes to the brief that reflect what she said. Do not invent preferences.
Allowed paths: weights.fit|mentor|brand|pay (0-1), tracks.<track> (0-1 multiplier), firm_types.<type> (0-1), hard_filters.exclude_words (list), hard_filters.locations (list), hard_filters.terms (list), skip_firms (list), dream_firms (list), streams (list), notes (list of free-text preferences Claude reads when scoring).
If she reports an application event (applied, rejected, interview), put it in status_updates instead."""


def propose(brief: dict, feedback: list) -> dict:
    prompt = (f"<brief>\n{json.dumps(_brief_for_llm(brief), ensure_ascii=False, indent=1)}\n</brief>\n\n"
              f"<feedback>\n{json.dumps(feedback, ensure_ascii=False, indent=1)}\n</feedback>")
    return ask_json(brief, CHANGE_SYSTEM, prompt, CHANGE_SCHEMA, 3000)


def _brief_for_llm(b: dict) -> dict:
    keep = ("goal", "background", "streams", "tracks", "firm_types", "dream_firms", "skip_firms", "weights",
            "hard_filters", "visa", "notes")
    return {k: b[k] for k in keep if k in b}

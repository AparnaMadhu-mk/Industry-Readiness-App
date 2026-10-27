"""Optional AI review. Uses the Anthropic API if ANTHROPIC_API_KEY is set.

If the key is missing or the call fails, we return None and the app falls back
to rule-based scoring with a visible notice (as promised in the project plan).
"""
import json
import os
import re

import requests

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

RUBRIC = """You are a strict but constructive career coach reviewing a CV for a fresher / early-career candidate.
Target role: {role}.
Score each dimension 0-100 using ONLY evidence from the CV text. Ignore name, gender, age, photo and institution prestige.
Dimensions:
- recruiter_appeal: clarity, relevance of skills, strength of achievements, how well experience is presented
- professional_standards: writing quality, consistency, professionalism, documentation of projects
- portfolio: depth and quality of projects described
- internship: readiness for an internship/entry role in the target role
Return ONLY valid JSON, no prose, in this schema:
{{"scores": {{"recruiter_appeal": int, "professional_standards": int, "portfolio": int, "internship": int}},
"strengths": [str, str, str],
"gaps": [str, str, str],
"rewrites": [{{"original": str, "improved": str}}],
"summary": str}}
Give at most 3 rewrites; 'original' must be copied from the CV. Keep each string under 200 characters."""


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON")
    return json.loads(m.group(0))


def _validate(d):
    scores = d["scores"]
    clean = {}
    for k in ("recruiter_appeal", "professional_standards", "portfolio", "internship"):
        v = int(scores[k])
        clean[k] = max(0, min(100, v))
    return {
        "scores": clean,
        "strengths": [str(x)[:220] for x in d.get("strengths", [])][:4],
        "gaps": [str(x)[:220] for x in d.get("gaps", [])][:4],
        "rewrites": [
            {"original": str(r.get("original", ""))[:220], "improved": str(r.get("improved", ""))[:260]}
            for r in d.get("rewrites", [])
            if isinstance(r, dict)
        ][:3],
        "summary": str(d.get("summary", ""))[:400],
    }


def review_cv(cv_text, role_label):
    """Return validated AI review dict or None if unavailable."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    body = {
        "model": MODEL,
        "max_tokens": 1200,
        "temperature": 0.1,
        "system": RUBRIC.format(role=role_label),
        "messages": [{"role": "user", "content": "CV TEXT:\n" + cv_text[:9000]}],
    }
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    for _ in range(2):  # one retry
        try:
            r = requests.post(API_URL, headers=headers, json=body, timeout=40)
            if r.status_code != 200:
                continue
            text = "".join(b.get("text", "") for b in r.json().get("content", []))
            return _validate(_extract_json(text))
        except (requests.RequestException, ValueError, KeyError, TypeError):
            continue
    return None

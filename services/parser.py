"""Structure parser: sections, contact details, bullets, metrics, dates, verbs."""
import json
import os
import re

import config

with open(os.path.join(config.BASE_DIR, "data", "skills.json"), encoding="utf-8") as fh:
    SKILLS = json.load(fh)

SECTION_ALIASES = {
    "summary": ["summary", "professional summary", "profile", "objective", "career objective", "about me", "about"],
    "education": ["education", "academic background", "academics", "qualifications", "educational qualification"],
    "skills": ["skills", "technical skills", "core competencies", "key skills", "technologies", "tech stack", "skill set"],
    "experience": ["experience", "work experience", "professional experience", "employment", "internships", "internship", "work history", "internship experience"],
    "projects": ["projects", "academic projects", "personal projects", "project work", "key projects", "portfolio"],
    "certifications": ["certifications", "certificates", "courses", "licenses", "training", "achievements", "awards", "certification"],
}
STANDARD_SECTIONS = ["summary", "education", "skills", "experience", "projects", "certifications"]

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{8,}\d)")
LINKEDIN_RE = re.compile(r"linkedin\.com/(in|pub)/[\w\-%]+", re.I)
GITHUB_RE = re.compile(r"github\.com/([\w\-]+)", re.I)
METRIC_RE = re.compile(
    r"(\d+(\.\d+)?\s?%|\$\s?\d[\d,]*|₹\s?\d[\d,]*|\b\d{2,}[,\d]*\+?\s?(users|customers|requests|records|students|projects|clients|downloads|stars|members|participants|hours|lines|rows|models|apis|endpoints)\b|\b\d+x\b|\b(reduced|increased|improved|boosted|cut|grew|saved)\b[^.\n]{0,40}\d)",
    re.I,
)
DATE_RE = re.compile(
    r"\b(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}|\d{1,2}/\d{4}|\b(?:19|20)\d{2}\b|present|current)\b",
    re.I,
)
BULLET_RE = re.compile(r"^\s*([•●▪■◦\-\*–·►➢✓]|\d+[.)])\s+")
# Characters that frequently signal a "fancy" template that ATS parsers choke on
FANCY_CHARS_RE = re.compile(r"[★☆✔✆✉☎❖◆♦♥]")


def _heading_key(line):
    clean = re.sub(r"[^a-z& ]", "", line.lower()).strip()
    if not clean or len(clean) > 40:
        return None
    for key, aliases in SECTION_ALIASES.items():
        if clean in aliases:
            return key
    return None


def split_sections(text):
    sections, current = {}, "header"
    sections[current] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        key = _heading_key(line)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v) for k, v in sections.items()}


def parse_cv(extracted, profile=None):
    """Turn raw extracted text into a structured dict used by rules + scoring."""
    text = extracted["text"]
    lower = text.lower()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    sections = split_sections(text)
    found_sections = [s for s in STANDARD_SECTIONS if s in sections and sections[s].strip()]

    emails = EMAIL_RE.findall(text)
    phones = [p for p in PHONE_RE.findall(text) if len(re.sub(r"\D", "", p)) >= 10]
    all_links = extracted.get("links", [])
    linkedin = next((l for l in all_links if LINKEDIN_RE.search(l)), None) or (
        LINKEDIN_RE.search(text).group(0) if LINKEDIN_RE.search(text) else None
    )
    gh_match = next((GITHUB_RE.search(l) for l in all_links if GITHUB_RE.search(l)), None) or GITHUB_RE.search(text)
    github_user = gh_match.group(1) if gh_match else None

    bullets = [BULLET_RE.sub("", l) for l in lines if BULLET_RE.match(l)]
    if len(bullets) < 3:  # many CVs use line-per-achievement without bullet glyphs
        bullets = [l for l in lines if 40 <= len(l) <= 260 and l[0].isalpha()]
    metric_bullets = [b for b in bullets if METRIC_RE.search(b)]
    verbs = SKILLS["action_verbs"]
    verb_bullets = [b for b in bullets if b.split()[0].lower().strip(",.") in verbs]
    weak = [p for p in SKILLS["weak_phrases"] if p in lower]

    words = re.findall(r"[A-Za-z][A-Za-z'+#.-]*", text)
    word_count = len(words)
    avg_bullet_len = (sum(len(b.split()) for b in bullets) / len(bullets)) if bullets else 0
    long_bullets = [b for b in bullets if len(b.split()) > 35]

    return {
        "text": text,
        "lower": lower,
        "lines": lines,
        "sections": sections,
        "found_sections": found_sections,
        "missing_sections": [s for s in STANDARD_SECTIONS if s not in found_sections],
        "emails": emails,
        "phones": phones,
        "linkedin": linkedin,
        "github_user": github_user,
        "links": all_links,
        "bullets": bullets,
        "metric_bullets": metric_bullets,
        "verb_bullets": verb_bullets,
        "weak_phrases": weak,
        "long_bullets": long_bullets,
        "avg_bullet_len": avg_bullet_len,
        "word_count": word_count,
        "pages": extracted.get("pages", 1),
        "has_tables": extracted.get("has_tables", False),
        "has_images": extracted.get("has_images", False),
        "used_ocr": extracted.get("used_ocr", False),
        "dates": DATE_RE.findall(text),
        "fancy_chars": FANCY_CHARS_RE.findall(text),
        "bullet_styles": set(m.group(1) for l in lines if (m := BULLET_RE.match(l))),
    }


def skill_hits(lower_text, role):
    """Return (matched, total) skills from the role keyword list."""
    core = SKILLS.get(role, SKILLS["general"])["core"]
    matched = []
    for kw in core:
        pattern = r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])"
        if re.search(pattern, lower_text):
            matched.append(kw)
    return matched, core


def keyword_present(lower_text, keywords):
    """Keywords must start at a word boundary (so 'git' doesn't match 'digital');
    stems such as 'collaborat' still match 'collaborated'."""
    return [k for k in keywords if re.search(r"(?<![a-z0-9])" + re.escape(k), lower_text)]

"""Deterministic, repeatable rule-based checks.

Each dimension is a list of criteria. A criterion has:
  name, max points, earned points, evidence (what we found), fix (what to do),
  assessed (False = excluded from scoring and shown as "not assessed").
"""
import re

from services.parser import SKILLS, keyword_present, skill_hits

COMMON_TYPOS = {
    "teh": "the", "recieve": "receive", "occured": "occurred", "seperate": "separate",
    "definately": "definitely", "managment": "management", "enviroment": "environment",
    "experiance": "experience", "responsibile": "responsible", "knowlege": "knowledge",
    "sucessful": "successful", "developement": "development", "langauge": "language",
    "programing": "programming", "databse": "database", "adress": "address",
    "acheived": "achieved", "comunication": "communication", "projet": "project",
}
UNPROFESSIONAL_EMAIL_RE = re.compile(r"(cute|sexy|hot|baby|princess|cool|boss|king|queen|lover|crazy|\d{4,})", re.I)
PERSONAL_DATA_RE = re.compile(
    r"(date of birth|\bdob\b|marital status|father'?s name|mother'?s name|religion|nationality|passport|aadhaar|aadhar|\bage\s*[:\-]|gender\s*[:\-])",
    re.I,
)


def crit(name, max_pts, earned, evidence, fix, assessed=True):
    earned = max(0.0, min(float(max_pts), float(earned)))
    return {
        "name": name,
        "max": max_pts,
        "earned": round(earned, 1),
        "evidence": evidence,
        "fix": fix,
        "assessed": assessed,
    }


def _ratio_points(ratio, max_pts):
    return max_pts * max(0.0, min(1.0, ratio))


# --------------------------------------------------------------------------
# Recruiter Appeal (100)
# --------------------------------------------------------------------------
def recruiter_appeal(cv, role):
    c = []

    # 1. ATS compatibility (25)
    pts, notes = 25, []
    if cv["has_tables"]:
        pts -= 7
        notes.append("tables detected")
    if cv["has_images"]:
        pts -= 5
        notes.append("images/graphics detected")
    if cv["fancy_chars"]:
        pts -= 3
        notes.append("decorative symbols")
    if cv["used_ocr"]:
        pts -= 8
        notes.append("text only readable via OCR")
    missing_core = [s for s in ("education", "skills", "experience") if s not in cv["found_sections"]]
    if "experience" in missing_core and "projects" in cv["found_sections"]:
        missing_core.remove("experience")
    pts -= 4 * len(missing_core)
    if missing_core:
        notes.append("missing standard headings: " + ", ".join(missing_core))
    if not cv["emails"]:
        pts -= 3
        notes.append("no parsable email")
    c.append(crit(
        "ATS compatibility", 25, pts,
        "Parsed sections: " + (", ".join(cv["found_sections"]) or "none")
        + ("; issues: " + "; ".join(notes) if notes else "; no layout problems found"),
        "Use a single-column layout, standard headings (Education, Skills, Experience, Projects) and avoid tables, text boxes and images.",
    ))

    # 2. Clarity & structure (20)
    pts, notes = 20, []
    wc = cv["word_count"]
    if wc < 150:
        pts -= 8
        notes.append(f"very short ({wc} words)")
    elif wc > 900:
        pts -= 6
        notes.append(f"very long ({wc} words)")
    if cv["pages"] > 2:
        pts -= 5
        notes.append(f"{cv['pages']} pages (aim for 1-2)")
    if len(cv["bullets"]) < 4:
        pts -= 5
        notes.append("few bullet points")
    if cv["long_bullets"]:
        pts -= min(4, len(cv["long_bullets"]))
        notes.append(f"{len(cv['long_bullets'])} bullet(s) over 35 words")
    if len(cv["found_sections"]) < 4:
        pts -= 4
        notes.append("fewer than 4 clear sections")
    c.append(crit(
        "Clarity & structure", 20, pts,
        f"{wc} words, ~{cv['pages']} page(s), {len(cv['bullets'])} bullets"
        + ("; " + "; ".join(notes) if notes else "; well structured"),
        "Keep it to one page for freshers, use 3-5 concise bullets per project/role, each under ~25 words.",
    ))

    # 3. Relevance of skills (20)
    matched, core = skill_hits(cv["lower"], role)
    ratio = len(matched) / max(1, min(len(core), 12))  # reaching 12 role keywords = full marks
    c.append(crit(
        "Relevance of skills", 20, _ratio_points(ratio, 20),
        f"{len(matched)} of {len(core)} target-role keywords found"
        + (": " + ", ".join(matched[:10]) if matched else ""),
        "Add the technologies you actually know that employers for this role look for, e.g. "
        + ", ".join([k for k in core if k not in matched][:6]) + ".",
    ))

    # 4. Achievements with numbers (20)
    n_b = max(1, len(cv["bullets"]))
    metric_ratio = len(cv["metric_bullets"]) / n_b
    verb_ratio = len(cv["verb_bullets"]) / n_b
    pts = _ratio_points(min(1.0, metric_ratio / 0.35), 12) + _ratio_points(min(1.0, verb_ratio / 0.6), 8)
    if cv["weak_phrases"]:
        pts -= min(4, 2 * len(cv["weak_phrases"]))
    ev = f"{len(cv['metric_bullets'])}/{len(cv['bullets'])} bullets contain numbers; {len(cv['verb_bullets'])} start with action verbs"
    if cv["weak_phrases"]:
        ev += "; weak phrases: " + ", ".join(cv["weak_phrases"])
    c.append(crit(
        "Achievements with numbers", 20, pts, ev,
        "Rewrite duties as results, e.g. 'Built a Flask API serving 500+ requests/day, cutting response time by 35%'.",
    ))

    # 5. Summary & presentation (15)
    summary = cv["sections"].get("summary", "")
    pts = 0
    if summary:
        sw = len(summary.split())
        pts = 15 if 25 <= sw <= 80 else 9 if sw >= 10 else 5
        ev = f"Summary present ({sw} words)"
    else:
        pts = 3
        ev = "No summary/objective section found"
    c.append(crit(
        "Summary & presentation", 15, pts, ev,
        "Add a 2-3 line summary: your target role, strongest skills and one proof point (project or internship).",
    ))
    return c


# --------------------------------------------------------------------------
# Professional Standards (100)
# --------------------------------------------------------------------------
def professional_standards(cv, role):
    c = []

    # 1. Formatting consistency (25)
    pts, notes = 25, []
    if len(cv["bullet_styles"]) > 2:
        pts -= 8
        notes.append(f"{len(cv['bullet_styles'])} different bullet styles")
    date_formats = set()
    for d in cv["dates"]:
        d = d.lower()
        if re.match(r"^[a-z]+\.?\s+\d{4}$", d):
            date_formats.add("Month YYYY")
        elif re.match(r"^\d{1,2}/\d{4}$", d):
            date_formats.add("MM/YYYY")
    if len(date_formats) > 1:
        pts -= 7
        notes.append("mixed date formats")
    if not cv["dates"]:
        pts -= 6
        notes.append("no dates found")
    if re.search(r"[ \t]{4,}\S", cv["text"]) and cv["has_tables"]:
        pts -= 3
        notes.append("irregular spacing")
    c.append(crit(
        "Formatting consistency", 25, pts,
        "Consistent formatting" if not notes else "; ".join(notes),
        "Pick one bullet style, one date format (e.g. 'Jun 2025 - Aug 2025') and one font family throughout.",
    ))

    # 2. Language quality (25)
    pts, notes = 25, []
    typos = [w for w in COMMON_TYPOS if re.search(r"\b" + w + r"\b", cv["lower"])]
    if typos:
        pts -= min(15, 5 * len(typos))
        notes.append("possible typos: " + ", ".join(typos))
    repeated = re.findall(r"\b(\w{3,})\s+\1\b", cv["lower"])
    if repeated:
        pts -= min(6, 3 * len(repeated))
        notes.append("repeated words: " + ", ".join(sorted(set(repeated))[:3]))
    lower_starts = [b for b in cv["bullets"] if b and b[0].islower()]
    if len(lower_starts) > 2:
        pts -= 4
        notes.append("bullets not starting with a capital letter")
    first_person = len(re.findall(r"\b(i am|i have|my|i was|i worked)\b", cv["lower"]))
    if first_person > 3:
        pts -= 4
        notes.append("uses first-person pronouns")
    c.append(crit(
        "Language quality", 25, pts,
        "No obvious spelling or grammar problems" if not notes else "; ".join(notes),
        "Proofread with a spell-checker, use past tense for finished work and drop 'I/my' from bullets.",
    ))

    # 3. Contact details & links (20)
    pts, have, lack = 0, [], []
    for label, ok, p in (
        ("email", bool(cv["emails"]), 6),
        ("phone", bool(cv["phones"]), 4),
        ("LinkedIn", bool(cv["linkedin"]), 5),
        ("GitHub", bool(cv["github_user"]), 5),
    ):
        if ok:
            pts += p
            have.append(label)
        else:
            lack.append(label)
    c.append(crit(
        "Contact details & links", 20, pts,
        "Found: " + (", ".join(have) or "none") + ("; missing: " + ", ".join(lack) if lack else ""),
        "Add " + ", ".join(lack) + " to the header with clickable links." if lack else "Keep links current.",
    ))

    # 4. Documentation quality (20)
    proj = cv["sections"].get("projects", "")
    proj_lines = [l for l in proj.splitlines() if l.strip()]
    pts, notes = 0, []
    if proj_lines:
        avg = sum(len(l.split()) for l in proj_lines) / len(proj_lines)
        pts += 8 if len(proj_lines) >= 6 else 4
        pts += 6 if avg >= 8 else 2
        notes.append(f"{len(proj_lines)} project lines, avg {avg:.0f} words")
    else:
        notes.append("no projects section")
    if any(("readme" in l.lower() or "documentation" in l.lower() or "docs" in l.lower()) for l in cv["lines"]):
        pts += 6
        notes.append("mentions documentation/README")
    c.append(crit(
        "Documentation quality", 20, pts, "; ".join(notes),
        "Describe each project in 3-4 lines: problem, your role, tech stack, outcome. Mention README/docs for your repos.",
    ))

    # 5. Professionalism (10)
    pts, notes = 10, []
    if cv["emails"]:
        local = cv["emails"][0].split("@")[0]
        if UNPROFESSIONAL_EMAIL_RE.search(local):
            pts -= 4
            notes.append(f"email '{cv['emails'][0]}' looks informal")
    pd = PERSONAL_DATA_RE.findall(cv["text"])
    if pd:
        pts -= 4
        notes.append("unnecessary personal data (e.g. DOB, marital status)")
    if cv["fancy_chars"] or len(re.findall(r"[!]{2,}|[?]{2,}", cv["text"])):
        pts -= 2
        notes.append("decorative or excessive punctuation")
    c.append(crit(
        "Professionalism", 10, pts, "; ".join(notes) or "Professional tone and content",
        "Use a name-based email and remove DOB, marital status, religion and photo.",
    ))
    return c


# --------------------------------------------------------------------------
# Portfolio & Projects (100)
# --------------------------------------------------------------------------
def portfolio(cv, role, links):
    c = []
    proj = cv["sections"].get("projects", "")
    proj_lines = [l for l in proj.splitlines() if l.strip()]
    # approximate project count: lines that look like titles (short, not bullets)
    titles = [l for l in proj_lines if len(l.split()) <= 12 and not re.match(r"^\s*[•\-\*●▪]", l)]
    n_projects = max(len(titles), 0)
    if n_projects == 0 and proj_lines:
        n_projects = max(1, len(proj_lines) // 3)

    # 1. Number & relevance (25)
    pts = 25 if n_projects >= 3 else 17 if n_projects == 2 else 9 if n_projects == 1 else 0
    c.append(crit(
        "Number & relevance of projects", 25, pts,
        f"About {n_projects} project(s) listed",
        "Show 3 solid projects relevant to your target role instead of many small tutorials.",
    ))

    # 2. Depth (30)
    pts = 0
    ptext = proj.lower()
    for label, kws in (
        ("tech stack", SKILLS.get(role, SKILLS["general"])["core"]),
        ("outcome", ["result", "improv", "reduc", "increas", "users", "deployed", "achiev", "%"]),
        ("role/ownership", ["built", "developed", "designed", "implemented", "created", "led", "my role", "responsible"]),
        ("problem", ["problem", "solve", "challenge", "goal", "aim", "to help", "that allows", "which allows", "enables", "automate"]),
    ):
        if any(k in ptext for k in kws):
            pts += 7.5
    c.append(crit(
        "Depth of project descriptions", 30, pts if proj else 0,
        "Checked for stack, outcome, role and problem statement in the Projects section"
        if proj else "No Projects section found",
        "For every project state: the problem, your role, the tech stack and a measurable outcome.",
    ))

    # 3. Public code & README (25) - from GitHub check
    gh = links.get("github")
    if gh and gh.get("assessed"):
        pts = 0
        pts += min(10, gh["public_repos"] * 2)
        pts += min(8, gh["repos_with_description"] * 2)
        pts += 7 if gh.get("recent_activity") else 0
        c.append(crit(
            "Public code with README & activity", 25, pts,
            f"GitHub '{gh['username']}': {gh['public_repos']} public repos, "
            f"{gh['repos_with_description']} with descriptions, recent activity: {'yes' if gh.get('recent_activity') else 'no'}",
            "Pin your 3-6 best repos, give each a README (what, how to run, screenshots) and commit regularly.",
        ))
    else:
        c.append(crit(
            "Public code with README & activity", 25, 0,
            (gh or {}).get("note", "No GitHub profile provided - not assessed"),
            "Add your GitHub profile link so recruiters can see your code.",
            assessed=False,
        ))

    # 4. Variety (20)
    matched, _ = skill_hits(proj.lower() + " " + cv["sections"].get("skills", "").lower(), role)
    c.append(crit(
        "Variety of skills shown", 20, _ratio_points(len(matched) / 8, 20),
        f"{len(matched)} distinct role-relevant skills evidenced in projects/skills",
        "Show different layers (frontend, backend, database, data, testing) across your projects.",
    ))
    return c


# --------------------------------------------------------------------------
# Internship Readiness (100)
# --------------------------------------------------------------------------
def internship(cv, role, profile):
    c = []
    matched, core = skill_hits(cv["lower"], role)
    c.append(crit(
        "Core skills for chosen role", 30, _ratio_points(len(matched) / 10, 30),
        f"{len(matched)} core skills found ({', '.join(matched[:8]) or 'none'})",
        "Prioritise learning the missing core skills: " + ", ".join([k for k in core if k not in matched][:5]) + ".",
    ))

    # count distinct KINDS of experience (internship, freelance, hackathon, ...) so wording variants don't double count
    exp_kinds = {
        "internship/training": r"\b(intern|interns|internship|internships|trainee|apprentice)\b",
        "freelance/part-time": r"\b(freelanc\w*|part-time|contract)\b",
        "hackathon": r"\bhackathons?\b",
        "open source": r"\bopen[- ]source\b|\bcontributor\b",
        "research/volunteer": r"\b(research assistant|volunteer\w*)\b",
    }
    exp_hits = [k for k, rx in exp_kinds.items() if re.search(rx, cv["lower"])]
    exp_section = cv["sections"].get("experience", "")
    pts = min(25, 12 * len(exp_hits) + (5 if len(exp_section.split()) > 40 else 0))
    c.append(crit(
        "Practical experience", 25, pts,
        "Found: " + (", ".join(exp_hits) or "no internship/freelance/hackathon/open-source evidence"),
        "Do a small internship, freelance gig, hackathon or open-source contribution and list it with results.",
    ))

    edu = cv["sections"].get("education", "")
    cert = cv["sections"].get("certifications", "")
    pts = (8 if edu.strip() else 0) + (7 if len(cert.split()) >= 4 else 0)
    c.append(crit(
        "Education & certifications", 15, pts,
        f"Education {'present' if edu.strip() else 'missing'}; certifications {'present' if len(cert.split()) >= 4 else 'missing'}",
        "Add degree, year and CGPA, plus 1-2 relevant certifications (e.g. cloud, SQL, Python).",
    ))

    team = keyword_present(cv["lower"], SKILLS["teamwork_keywords"])
    c.append(crit(
        "Teamwork & communication evidence", 15, min(15, 4 * len(team)),
        "Signals: " + (", ".join(team[:6]) or "none found"),
        "Mention team projects, clubs, hackathons or presentations and your specific role in them.",
    ))

    target = (profile.get("role") or "").strip()
    pts = 0
    if target:
        pts += 7
    if cv["sections"].get("summary") and any(w in cv["sections"]["summary"].lower() for w in
                                              [target.lower(), "developer", "analyst", "engineer", "scientist", "intern"] if w):
        pts += 8
    c.append(crit(
        "Career focus", 15, pts,
        "Target role selected" + ("; summary names a role" if pts >= 15 else "; summary doesn't name a target role"),
        "Name your target role in the summary and tailor the skills order to it.",
    ))
    return c


# --------------------------------------------------------------------------
# Deployment Maturity (100)
# --------------------------------------------------------------------------
def deployment(cv, role, links):
    c = []
    # 1. Live deployed projects (35) - link checker
    live = links.get("live", [])
    if live:
        ok = [l for l in live if l.get("ok")]
        pts = min(35, 18 * len(ok)) if ok else 0
        c.append(crit(
            "Live, working deployed projects", 35, pts,
            f"{len(ok)} of {len(live)} supplied live link(s) responded successfully",
            "Deploy at least 2 projects (Render, Vercel, Netlify) and make sure the links work.",
        ))
    else:
        c.append(crit(
            "Live, working deployed projects", 35, 0,
            "No deployed-project URLs supplied - not assessed",
            "Add live URLs of deployed projects so they can be verified.",
            assessed=False,
        ))

    # 2. Version control (25)
    vc_kw = keyword_present(cv["lower"], ["git", "github", "gitlab", "bitbucket", "version control", "pull request", "branch"])
    pts = min(15, 7 * len(vc_kw))
    gh = links.get("github")
    if gh and gh.get("assessed"):
        pts += 10 if gh.get("recent_activity") else 4
    elif cv["github_user"]:
        pts += 6  # GitHub profile linked on the CV, but not verified by the API
    c.append(crit(
        "Version control practice", 25, pts,
        "CV mentions: " + (", ".join(vc_kw) or "no Git/GitHub keywords"),
        "Use Git for every project, work on branches, open pull requests and commit regularly.",
    ))

    # 3. Testing & CI/CD (20)
    t = keyword_present(cv["lower"], SKILLS["testing_keywords"])
    c.append(crit(
        "Testing & CI/CD evidence", 20, min(20, 7 * len(t)),
        "Found: " + (", ".join(t) or "no testing or CI/CD evidence"),
        "Add unit tests (pytest/jest) and a GitHub Actions workflow to one project and mention it.",
    ))

    # 4. Cloud / containers / hosting (20)
    d = keyword_present(cv["lower"], SKILLS["deploy_keywords"])
    c.append(crit(
        "Cloud, containers & hosting", 20, min(20, 6 * len(d)),
        "Found: " + (", ".join(d[:8]) or "none"),
        "Learn Docker basics and deploy a project to a cloud host; list the services you used.",
    ))
    return c


def run_all(cv, role, profile, links):
    return {
        "recruiter_appeal": recruiter_appeal(cv, role),
        "professional_standards": professional_standards(cv, role),
        "portfolio": portfolio(cv, role, links),
        "internship": internship(cv, role, profile),
        "deployment": deployment(cv, role, links),
    }

import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("ANTHROPIC_API_KEY", None)  # tests must run without the AI service

STRONG_CV = """Aparna Nair
aparna.nair@gmail.com | +91 98765 43210 | linkedin.com/in/aparna-nair | github.com/aparna-nair

Summary
Aspiring web developer with hands-on Flask and React experience, focused on building fast, accessible web applications.

Skills
Python, JavaScript, HTML, CSS, React, Flask, SQL, Git, Docker, REST API, pytest

Experience
Web Development Intern, TechNova - Jun 2025 - Aug 2025
- Built a Flask REST API serving 500+ requests per day, reducing response time by 35%
- Developed responsive React dashboards used by 40 team members
- Implemented unit tests with pytest, raising coverage to 85%
- Deployed the service to Render using Docker and GitHub Actions

Projects
Expense Tracker
- Built a Flask and SQL app used by 60 classmates, cutting manual tracking time by 50%
- Documented setup in a README and deployed on Render
Portfolio Website
- Designed a responsive portfolio with HTML, CSS and JavaScript, improving load speed by 40%
Chat Application
- Implemented real-time chat with Node and WebSockets for 100+ users

Education
B.Tech Computer Science, 2022 - 2026

Certifications
AWS Cloud Practitioner, Python for Everybody, SQL Fundamentals
"""

WEAK_CV = """john
coolboy2001@mail.com
Objective
I am a hard working person looking for job.
Experiance
Responsible for coding. Worked on a project with a team. I have knowlege of computers and the the internet.
Date of Birth: 12/05/2001
Marital status: single
"""


def make_docx(text):
    import docx

    d = docx.Document()
    for line in text.splitlines():
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def make_pdf(text):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in text.splitlines():
        c.drawString(40, y, line[:110])
        y -= 14
        if y < 40:
            c.showPage()
            y = 800
    c.save()
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import config

    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "test.db"))
    import app as app_module
    from services import db, links

    db.init_db()
    # keep tests offline and deterministic
    monkeypatch.setattr(links, "check_github", lambda v: {"assessed": False, "note": "offline test"})
    monkeypatch.setattr(links, "check_link", lambda u: {"url": u, "ok": True, "status": 200, "note": ""})
    app_module.app.config["TESTING"] = True
    app_module._hits.clear()
    return app_module.app.test_client()

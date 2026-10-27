# Industry Readiness App

Upload a CV, add profile/portfolio links, and get an **Industry Readiness Score** (0-100) with five dimension scores, strengths, gaps, prioritised recommendations and a downloadable PDF report. Built with **Flask** (backend + templates) and plain HTML/CSS/JS (frontend).

> The score is an indicative assessment, not a guarantee of recruitment success.

## Features

| Requirement from the brief | Where it lives |
|---|---|
| CV upload (PDF/DOCX), validation, text extraction, OCR fallback | `services/extractor.py` |
| Structure parsing (sections, contacts, bullets, metrics) | `services/parser.py` |
| Transparent rule-based criteria for all 5 dimensions | `services/rules.py` |
| AI review (optional, with rule-based fallback) | `services/ai.py` |
| GitHub + live-link checks ("not assessed" if unavailable) | `services/links.py` |
| Weighted overall score, gaps, recommendations | `services/scoring.py`, `config.py` |
| Results dashboard, radar chart, ATS summary | `templates/results.html`, `static/js/results.js` |
| PDF report | `services/report.py` |
| Optional 20-question assessment test (adds 15% weight) | `services/assessment.py`, `data/questions.json` |
| Error handling, consent, 30-day retention, delete endpoint, rate limit | `app.py`, `services/db.py` |

Dimensions and weights (no test / with test): Recruiter Appeal 30/25, Professional Standards 20/17, Portfolio 20/17, Internship 15/13, Deployment 15/13, Assessment -/15. Change them in `config.py`.

## Run it in VS Code

1. Install **Python 3.10+** and **VS Code** (with the *Python* extension). Install **Git**.
2. Open the folder: `File > Open Folder > industry-readiness-app`.
3. Open the terminal in VS Code (`Ctrl + ~`) and create a virtual environment:

   ```bash
   python -m venv venv
   # Windows (PowerShell):
   venv\Scripts\Activate.ps1
   # macOS / Linux:
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. In VS Code press `Ctrl+Shift+P` > **Python: Select Interpreter** > choose the `venv` one.
5. (Optional) copy `.env.example` to `.env` and add `ANTHROPIC_API_KEY` for AI feedback. Without it everything still works with rule-based scoring.
6. Start the app:

   ```bash
   python app.py
   ```
   Open http://127.0.0.1:5000. Try the files in `samples/`.
7. Run the tests: `pytest`

## Git workflow

```bash
git init
git add .
git commit -m "Initial Industry Readiness App"
git branch -M main
# create an empty repo on GitHub, then:
git remote add origin https://github.com/<your-username>/industry-readiness-app.git
git push -u origin main
```

Daily routine (shows regular commit history to your trainer):

```bash
git checkout -b feature/<name>      # e.g. feature/assessment-test
git add . && git commit -m "Add <what you did>"
git push -u origin feature/<name>   # open a Pull Request, then merge
```

## Deploy (free) on Render

1. Push to GitHub. On https://render.com create a **Web Service** from the repo.
2. Build command: `pip install -r requirements.txt` - Start command: `gunicorn app:app`.
3. Add environment variables `SECRET_KEY` and (optional) `ANTHROPIC_API_KEY`, and `FLASK_DEBUG=0`.
4. Put the public URL in this README.

SQLite is fine for a demo; for production use PostgreSQL via `DATABASE_PATH` replacement.

## OCR for scanned PDFs (optional)

Install the Tesseract program, then `pip install pytesseract pdf2image` (also needs Poppler). If not installed, scanned PDFs show a friendly "no selectable text" message.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/analyze` | multipart: `cv`, `role`, `consent`, optional `name`, `github`, `portfolio`, `live_urls` -> `{id}` |
| GET | `/api/results/<id>` | scores, gaps, recommendations (JSON) |
| GET | `/api/report/<id>` | PDF report |
| DELETE | `/api/results/<id>` | delete your data |
| GET | `/api/assessment/<role>` | random 20-question test (answers hidden) |

## Project structure

```
app.py              Flask routes, pipeline, error handlers
config.py           weights, bands, limits (edit to tune scoring)
services/           extractor, parser, rules, ai, links, scoring, assessment, report, db
templates/          Jinja pages (upload wizard, results, test, methodology)
static/             css + js (gauge, radar chart, wizard, timer)
data/               skills taxonomy + question bank (JSON)
tests/              pytest suite (core logic + API + error handling)
samples/            sample CVs to try
```

## Privacy

Consent is required; the CV file is read in memory and never saved; only results are stored (30 days) and can be deleted anytime; names/emails are not logged; the link checker blocks private/local addresses; basic per-IP rate limiting is on.

## Known limitations

- Rule-based checks are heuristics (e.g. typo detection uses a small word list); the AI review adds judgement when an API key is set.
- Scoring weights should be validated against human reviewers and tuned (as in the project plan).
- Role keyword lists cover 3 roles (web, data, general); add more in `data/skills.json`.

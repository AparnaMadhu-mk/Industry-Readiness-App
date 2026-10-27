"""Central configuration: weights, score bands, limits.

Everything about HOW the score is calculated lives here so the methodology
stays transparent and easy to tune after review with the trainer.
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ---- App / upload limits -------------------------------------------------
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {"pdf", "docx"}
MIN_TEXT_CHARS = 100  # fewer characters than this = unreadable document
RESULT_RETENTION_DAYS = 30
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "readiness.db"))

# ---- Scoring weights -----------------------------------------------------
DIMENSIONS = [
    "recruiter_appeal",
    "professional_standards",
    "portfolio",
    "internship",
    "deployment",
]

DIMENSION_LABELS = {
    "recruiter_appeal": "Recruiter Appeal",
    "professional_standards": "Professional Standards",
    "portfolio": "Portfolio & Projects",
    "internship": "Internship Readiness",
    "deployment": "Deployment Maturity",
    "assessment": "Assessment Test",
}

DIMENSION_ICONS = {
    "recruiter_appeal": "🎯",
    "professional_standards": "🏅",
    "portfolio": "🗂️",
    "internship": "🚀",
    "deployment": "☁️",
    "assessment": "📝",
}

# Weights when no assessment test has been taken (sum = 100)
WEIGHTS_NO_TEST = {
    "recruiter_appeal": 30,
    "professional_standards": 20,
    "portfolio": 20,
    "internship": 15,
    "deployment": 15,
}

# Weights when the assessment test is included (sum = 100)
WEIGHTS_WITH_TEST = {
    "recruiter_appeal": 25,
    "professional_standards": 17,
    "portfolio": 17,
    "internship": 13,
    "deployment": 13,
    "assessment": 15,
}

# Final score blend: deterministic rules vs AI judgement
RULES_SHARE = 0.60
AI_SHARE = 0.40

GAP_THRESHOLD = 0.60  # a criterion below 60% of its points is a gap
STRENGTH_THRESHOLD = 0.80  # at or above 80% is a strength

BANDS = [
    (0, 39, "Early stage", "#ef4444"),
    (40, 59, "Developing", "#f59e0b"),
    (60, 79, "Nearly ready", "#3b82f6"),
    (80, 100, "Industry ready", "#10b981"),
]

ROLES = {
    "web": "Web Developer",
    "data": "Data Analyst / Data Scientist",
    "general": "General / Other IT Role",
}

DISCLAIMER = (
    "This score is an indicative assessment designed to guide improvement. "
    "It is not a hiring prediction or a guarantee of recruitment success."
)

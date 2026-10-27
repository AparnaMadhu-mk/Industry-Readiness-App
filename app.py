"""Industry Readiness App - Flask entry point.

Run:  python app.py   ->  http://127.0.0.1:5000
"""
import hashlib
import logging
import os
import time
from collections import defaultdict, deque

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_file, url_for)

import config
from services import ai, assessment, db, extractor, links, parser, report, scoring
from services.errors import AnalysisError, AppError

try:  # optional .env support for ANTHROPIC_API_KEY etc.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_BYTES + 512 * 1024  # form overhead

# Never log personal details - only generic events.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("readiness")

db.init_db()

# ---- very small in-memory rate limiter (per IP) --------------------------
_hits = defaultdict(deque)
RATE_LIMIT, RATE_WINDOW = 15, 3600  # 15 analyses per hour per IP


def rate_limited(ip):
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return True
    q.append(now)
    return False


@app.context_processor
def inject_globals():
    return {"ROLES": config.ROLES, "DISCLAIMER": config.DISCLAIMER, "config": config}


# --------------------------------------------------------------------------
# Core analysis pipeline
# --------------------------------------------------------------------------
def run_pipeline(file_storage, form):
    """validate -> extract -> parse -> link checks -> AI -> score -> save."""
    data, kind = extractor.validate_upload(file_storage)
    extracted = extractor.extract_text(data, kind)

    role = form.get("role", "general")
    if role not in config.ROLES:
        role = "general"
    profile = {
        "name": (form.get("name") or "").strip()[:80],
        "role": config.ROLES[role],
        "github": (form.get("github") or "").strip()[:200],
        "portfolio": (form.get("portfolio") or "").strip()[:200],
        "live_urls": (form.get("live_urls") or "").strip()[:600],
        "education": (form.get("education") or "").strip()[:60],
        "experience_years": (form.get("experience_years") or "").strip()[:10],
    }

    cache_key = hashlib.sha256(
        data + b"|" + "|".join([role, profile["github"], profile["portfolio"], profile["live_urls"]]).encode()
    ).hexdigest()
    cached = db.find_by_hash(cache_key, role)
    if cached:
        return cached

    cv = parser.parse_cv(extracted, profile)
    link_data = links.gather(profile, cv)
    ai_review = ai.review_cv(cv["text"], config.ROLES[role])
    try:
        result = scoring.analyse(cv, role, profile, link_data, ai_review)
    except Exception as exc:  # analysis failure - friendly message, detail in server log only
        log.exception("analysis failed")
        raise AnalysisError("Something went wrong while analysing your CV.", "Please try again in a moment.") from exc

    candidate = profile["name"] or "Anonymous"
    # The uploaded file itself is never stored - only these results.
    return db.save_result(result, role, candidate, cache_key)


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html", error=None, form={})


@app.post("/analyze")
def analyze():
    if rate_limited(request.remote_addr or "unknown"):
        return render_template("index.html", error={"message": "Too many requests.", "hint": "Please wait a while before trying again."}, form=request.form), 429
    if not request.form.get("consent"):
        return render_template("index.html", error={"message": "Please tick the consent box to continue.", "hint": "We need your permission to process your CV."}, form=request.form), 400
    try:
        rid = run_pipeline(request.files.get("cv"), request.form)
    except AppError as e:
        return render_template("index.html", error={"message": e.message, "hint": e.hint}, form=request.form), e.status_code
    return redirect(url_for("results", rid=rid))


@app.get("/results/<rid>")
def results(rid):
    result = db.get_result(rid)
    if not result:
        abort(404)
    return render_template("results.html", r=result, rid=rid)


@app.post("/results/<rid>/delete")
def delete_page(rid):
    db.delete_result(rid)
    return render_template("deleted.html")


@app.get("/report/<rid>")
def report_pdf(rid):
    result = db.get_result(rid)
    if not result:
        abort(404)
    pdf = report.build_pdf(result)
    return send_file(pdf, mimetype="application/pdf", as_attachment=True,
                     download_name="industry-readiness-report.pdf")


@app.get("/methodology")
def methodology():
    return render_template("methodology.html", weights_no=config.WEIGHTS_NO_TEST,
                           weights_with=config.WEIGHTS_WITH_TEST, bands=config.BANDS)


# ---- Assessment test ------------------------------------------------------
@app.get("/assessment/<rid>")
def assessment_start(rid):
    result = db.get_result(rid)
    if not result:
        abort(404)
    role = result["_meta"]["role"]
    qs = [assessment.public_view(q) for q in assessment.build_test(role)]
    return render_template("assessment.html", rid=rid, questions=qs, minutes=assessment.TEST_MINUTES,
                           role_label=config.ROLES.get(role, role))


@app.post("/assessment/<rid>/submit")
def assessment_submit(rid):
    result = db.get_result(rid)
    if not result:
        abort(404)
    answers = {k[2:]: v for k, v in request.form.items() if k.startswith("q_")}
    ids = request.form.get("question_ids", "").split(",")
    for qid in ids:  # unanswered = wrong, but still counted in the total
        if qid and qid not in answers:
            answers[qid] = -1
    if not answers:
        return redirect(url_for("assessment_start", rid=rid))
    test = assessment.score_test(answers)
    result["assessment"] = test
    dim_scores = {d: v["score"] for d, v in result["dimensions"].items()}
    overall, eff = scoring.compute_overall(dim_scores, test["score"])
    result["overall"], result["weights"], result["band"] = overall, eff, scoring.band_for(overall)
    result["dimensions"]["assessment"] = {
        "label": config.DIMENSION_LABELS["assessment"], "icon": config.DIMENSION_ICONS["assessment"],
        "score": test["score"], "rule_score": test["score"], "ai_score": None, "assessed": True,
        "band": scoring.band_for(test["score"]),
        "criteria": [{"name": f"{s}", "max": v["total"], "earned": v["correct"], "assessed": True,
                      "evidence": f"{v['correct']} of {v['total']} correct", "fix": "Review the explanations below."}
                     for s, v in test["by_skill"].items()],
    }
    meta = result.pop("_meta", None)
    db.update_result(rid, result)
    return redirect(url_for("assessment_result", rid=rid))


@app.get("/assessment/<rid>/result")
def assessment_result(rid):
    result = db.get_result(rid)
    if not result or "assessment" not in result:
        abort(404)
    return render_template("assessment_result.html", r=result, rid=rid, t=result["assessment"])


# --------------------------------------------------------------------------
# JSON API (matches the endpoints in the project plan)
# --------------------------------------------------------------------------
@app.post("/api/analyze")
def api_analyze():
    if rate_limited(request.remote_addr or "unknown"):
        return jsonify(error="Too many requests. Please wait and try again."), 429
    if request.form.get("consent") not in ("on", "true", "1", "yes"):
        return jsonify(error="Consent is required to process your CV."), 400
    try:
        rid = run_pipeline(request.files.get("cv"), request.form)
    except AppError as e:
        return jsonify(error=e.message, hint=e.hint), e.status_code
    return jsonify(id=rid, results_url=url_for("api_results", rid=rid)), 201


@app.get("/api/results/<rid>")
def api_results(rid):
    result = db.get_result(rid)
    if not result:
        return jsonify(error="Result not found or expired."), 404
    return jsonify(result)


@app.get("/api/report/<rid>")
def api_report(rid):
    return report_pdf(rid)


@app.delete("/api/results/<rid>")
def api_delete(rid):
    if db.delete_result(rid):
        return jsonify(deleted=True)
    return jsonify(error="Result not found."), 404


@app.get("/api/assessment/<role>")
def api_assessment(role):
    return jsonify([assessment.public_view(q) for q in assessment.build_test(role)])


# --------------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------------
def _wants_json():
    return request.path.startswith("/api/")


@app.errorhandler(404)
def not_found(_):
    if _wants_json():
        return jsonify(error="Not found"), 404
    return render_template("error.html", title="Page not found",
                           message="That page or result doesn't exist - results are deleted after 30 days."), 404


@app.errorhandler(413)
def too_large(_):
    msg = f"File is larger than the {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."
    if _wants_json():
        return jsonify(error=msg), 413
    return render_template("index.html", error={"message": msg, "hint": "Compress the file and try again."}, form={}), 413


@app.errorhandler(500)
def server_error(_):
    log.exception("unexpected server error")
    if _wants_json():
        return jsonify(error="Something went wrong on our side. Please try again."), 500
    return render_template("error.html", title="Something went wrong",
                           message="An unexpected error occurred. Please try again in a moment."), 500


if __name__ == "__main__":
    db.purge_expired()
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=int(os.environ.get("PORT", 5000)))

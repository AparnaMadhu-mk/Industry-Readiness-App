"""Scoring engine: criteria -> dimension scores -> weighted overall score."""
import config
from services import rules as rules_mod


def band_for(score):
    for lo, hi, label, color in config.BANDS:
        if lo <= score <= hi:
            return {"label": label, "color": color}
    return {"label": config.BANDS[-1][2], "color": config.BANDS[-1][3]}


def dimension_rule_score(criteria):
    """Score 0-100 from assessed criteria only (unassessed ones are excluded)."""
    assessed = [c for c in criteria if c["assessed"]]
    total = sum(c["max"] for c in assessed)
    if total == 0:
        return None
    return round(100 * sum(c["earned"] for c in assessed) / total, 1)


def compute_overall(dim_scores, assessment_score=None):
    """Weighted average. Dimensions with no score (None) are excluded and the
    remaining weights are rescaled so missing data is never counted as zero."""
    weights = dict(config.WEIGHTS_WITH_TEST if assessment_score is not None else config.WEIGHTS_NO_TEST)
    scores = dict(dim_scores)
    if assessment_score is not None:
        scores["assessment"] = assessment_score
    usable = {k: w for k, w in weights.items() if scores.get(k) is not None}
    total_w = sum(usable.values())
    if total_w == 0:
        return 0.0, {}
    effective = {k: round(100 * w / total_w, 1) for k, w in usable.items()}
    overall = sum(scores[k] * usable[k] for k in usable) / total_w
    return round(overall, 1), effective


def build_gaps_and_recs(all_criteria, ai_review):
    gaps, strengths = [], []
    weights = config.WEIGHTS_NO_TEST
    for dim, crits in all_criteria.items():
        for c in crits:
            if not c["assessed"]:
                continue
            ratio = c["earned"] / c["max"]
            item = {
                "dimension": dim,
                "dimension_label": config.DIMENSION_LABELS[dim],
                "criterion": c["name"],
                "evidence": c["evidence"],
                "fix": c["fix"],
                "ratio": round(ratio, 2),
                "impact": round(weights.get(dim, 10) / 100 * (c["max"] - c["earned"]), 2),
            }
            if ratio < config.GAP_THRESHOLD:
                gaps.append(item)
            elif ratio >= config.STRENGTH_THRESHOLD:
                strengths.append(item)
    gaps.sort(key=lambda g: g["impact"], reverse=True)
    strengths.sort(key=lambda s: s["ratio"], reverse=True)

    recs = []
    for i, g in enumerate(gaps[:5], 1):
        recs.append({
            "priority": i,
            "title": f"Improve: {g['criterion']}",
            "dimension": g["dimension_label"],
            "why": g["evidence"],
            "fix": g["fix"],
        })
    # attach AI rewrites to recommendations where available
    if ai_review and ai_review.get("rewrites"):
        for r in ai_review["rewrites"]:
            if r["original"] and r["improved"]:
                recs.append({
                    "priority": len(recs) + 1,
                    "title": "Rewrite a weak bullet",
                    "dimension": "Recruiter Appeal",
                    "why": f"Original: \"{r['original']}\"",
                    "fix": f"Try: \"{r['improved']}\"",
                })
    return gaps, strengths, recs


def analyse(cv, role, profile, link_data, ai_review, assessment_score=None):
    """Run rules, blend AI, compute overall. Returns the full result dict."""
    criteria = rules_mod.run_all(cv, role, profile, link_data)

    dims = {}
    for dim in config.DIMENSIONS:
        rule_score = dimension_rule_score(criteria[dim])
        ai_score = ai_review["scores"].get(dim) if ai_review else None
        if rule_score is None:
            final = None
        elif ai_score is not None and dim in ("recruiter_appeal", "professional_standards", "portfolio", "internship"):
            final = round(config.RULES_SHARE * rule_score + config.AI_SHARE * ai_score, 1)
        else:
            final = rule_score
        dims[dim] = {
            "label": config.DIMENSION_LABELS[dim],
            "icon": config.DIMENSION_ICONS[dim],
            "score": final,
            "rule_score": rule_score,
            "ai_score": ai_score,
            "assessed": final is not None,
            "criteria": criteria[dim],
            "band": band_for(final) if final is not None else None,
        }

    overall, effective_weights = compute_overall({d: dims[d]["score"] for d in dims}, assessment_score)
    gaps, strengths, recs = build_gaps_and_recs(criteria, ai_review)

    return {
        "overall": overall,
        "band": band_for(overall),
        "dimensions": dims,
        "weights": effective_weights,
        "gaps": gaps,
        "strengths": strengths,
        "recommendations": recs,
        "ai_used": ai_review is not None,
        "ai_review": ai_review,
        "ats": {
            "found_sections": cv["found_sections"],
            "missing_sections": cv["missing_sections"],
            "warnings": [w for w in [
                "Tables detected - some ATS systems can't read them" if cv["has_tables"] else None,
                "Images/graphics detected - text inside images is invisible to ATS" if cv["has_images"] else None,
                "Decorative symbols found - replace with simple bullets" if cv["fancy_chars"] else None,
                "Text was recovered with OCR - use a text-based PDF" if cv["used_ocr"] else None,
                f"CV is about {cv['pages']} pages - aim for 1-2" if cv["pages"] > 2 else None,
            ] if w],
            "word_count": cv["word_count"],
            "pages": cv["pages"],
        },
        "links": link_data,
        "disclaimer": config.DISCLAIMER,
    }

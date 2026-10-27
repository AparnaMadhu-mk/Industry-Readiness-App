"""Optional assessment test: 20 MCQs drawn at random from a ~60-question bank."""
import json
import os
import random
from collections import defaultdict

import config

with open(os.path.join(config.BASE_DIR, "data", "questions.json"), encoding="utf-8") as fh:
    BANK = json.load(fh)

MIX = {"technical": 8, "analytical": 6, "project": 6}
TEST_MINUTES = 20


def build_test(role, rng=None):
    rng = rng or random.Random()
    role = role if role in config.ROLES else "general"
    picked = []
    for cat, n in MIX.items():
        pool = [q for q in BANK if q["cat"] == cat and q["role"] in (role, "all")]
        picked += rng.sample(pool, min(n, len(pool)))
    rng.shuffle(picked)
    return picked


def public_view(q):
    """Question without the answer, safe to send to the browser."""
    return {k: q[k] for k in ("id", "cat", "skill", "q", "options")}


def score_test(answers):
    """answers: {question_id: chosen_index}. Returns percentage + breakdown."""
    by_id = {q["id"]: q for q in BANK}
    total = correct = 0
    skill = defaultdict(lambda: [0, 0])
    cat = defaultdict(lambda: [0, 0])
    review = []
    for qid, chosen in answers.items():
        q = by_id.get(qid)
        if not q:
            continue
        total += 1
        try:
            chosen = int(chosen)
        except (TypeError, ValueError):
            chosen = -1
        ok = chosen == q["answer"]
        correct += ok
        skill[q["skill"]][1] += 1
        cat[q["cat"]][1] += 1
        if ok:
            skill[q["skill"]][0] += 1
            cat[q["cat"]][0] += 1
        review.append({
            "q": q["q"], "options": q["options"], "chosen": chosen,
            "answer": q["answer"], "correct": ok, "explain": q["explain"], "skill": q["skill"],
        })
    pct = round(100 * correct / total, 1) if total else 0.0
    return {
        "score": pct,
        "correct": correct,
        "total": total,
        "by_category": {k: {"correct": v[0], "total": v[1]} for k, v in cat.items()},
        "by_skill": {k: {"correct": v[0], "total": v[1]} for k, v in skill.items()},
        "review": review,
    }

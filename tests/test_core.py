import io

import pytest

import config
from services import assessment, extractor, parser, scoring
from services.errors import (FileTooLargeError, UnreadableDocumentError,
                             UnsupportedFormatError)
from tests.conftest import STRONG_CV, WEAK_CV, make_docx, make_pdf


class FakeUpload:
    def __init__(self, name, data):
        self.filename, self._data = name, data

    def read(self):
        return self._data


# ---------------- extraction & validation ----------------
def test_pdf_and_docx_extract():
    for kind, data in (("pdf", make_pdf(STRONG_CV)), ("docx", make_docx(STRONG_CV))):
        out = extractor.extract_text(data, kind)
        assert "Flask" in out["text"]


def test_rejects_unsupported_extension():
    with pytest.raises(UnsupportedFormatError):
        extractor.validate_upload(FakeUpload("cv.png", b"\x89PNG..."))


def test_rejects_fake_pdf():
    with pytest.raises(UnsupportedFormatError):
        extractor.validate_upload(FakeUpload("cv.pdf", b"this is not a pdf"))


def test_rejects_empty_and_large():
    with pytest.raises(UnreadableDocumentError):
        extractor.validate_upload(FakeUpload("cv.pdf", b""))
    with pytest.raises(FileTooLargeError):
        extractor.validate_upload(FakeUpload("cv.pdf", b"%PDF-" + b"0" * (config.MAX_UPLOAD_BYTES + 1)))


def test_corrupt_pdf_gives_friendly_error():
    with pytest.raises(UnreadableDocumentError):
        extractor.extract_text(b"%PDF-1.4 garbage", "pdf")


def test_image_only_document_is_unreadable():
    with pytest.raises(UnreadableDocumentError):
        extractor.extract_text(make_pdf("   "), "pdf")


# ---------------- parsing ----------------
def test_parser_finds_sections_and_contacts():
    cv = parser.parse_cv({"text": STRONG_CV, "links": [], "pages": 1})
    assert {"summary", "skills", "experience", "projects", "education"} <= set(cv["found_sections"])
    assert cv["emails"] and cv["linkedin"] and cv["github_user"] == "aparna-nair"
    assert len(cv["metric_bullets"]) >= 4


# ---------------- scoring ----------------
def analyse(text, role="web", links=None):
    cv = parser.parse_cv({"text": text, "links": [], "pages": 1})
    links = links or {"github": {"assessed": False, "note": "n/a"}, "live": []}
    return scoring.analyse(cv, role, {"role": role}, links, None)


def test_strong_cv_scores_higher_than_weak():
    strong, weak = analyse(STRONG_CV), analyse(WEAK_CV)
    assert strong["overall"] > weak["overall"] + 25
    assert weak["overall"] < 40
    assert strong["recommendations"] and weak["recommendations"]


def test_scores_are_deterministic():
    assert analyse(STRONG_CV)["overall"] == analyse(STRONG_CV)["overall"]


def test_weak_cv_flags_problems():
    r = analyse(WEAK_CV)
    names = " ".join(c["name"] for g in r["gaps"] for c in [g] if False) or ""
    texts = " ".join(c["evidence"] for d in r["dimensions"].values() for c in d["criteria"])
    assert "typos" in texts and "personal data" in texts


def test_unassessed_criteria_are_excluded_not_zero():
    r = analyse(STRONG_CV)
    port = r["dimensions"]["portfolio"]
    gh = next(c for c in port["criteria"] if "Public code" in c["name"])
    assert gh["assessed"] is False
    # score is computed from the other criteria only (out of 75 points)
    assessed_max = sum(c["max"] for c in port["criteria"] if c["assessed"])
    assert assessed_max == 75


def test_weights_sum_to_100_and_rescale():
    assert sum(config.WEIGHTS_NO_TEST.values()) == 100
    assert sum(config.WEIGHTS_WITH_TEST.values()) == 100
    overall, eff = scoring.compute_overall(
        {"recruiter_appeal": 80, "professional_standards": 60, "portfolio": None, "internship": 70, "deployment": None})
    assert abs(sum(eff.values()) - 100) < 0.5
    assert 60 < overall < 80


def test_band_boundaries():
    assert scoring.band_for(39)["label"] == "Early stage"
    assert scoring.band_for(40)["label"] == "Developing"
    assert scoring.band_for(79)["label"] == "Nearly ready"
    assert scoring.band_for(80)["label"] == "Industry ready"


def test_assessment_scoring():
    qs = assessment.build_test("web")
    assert len(qs) == 20
    answers = {q["id"]: q["answer"] for q in qs}
    assert assessment.score_test(answers)["score"] == 100
    assert assessment.score_test({q["id"]: -1 for q in qs})["score"] == 0


def test_keyword_matching_uses_word_boundaries():
    from services.parser import keyword_present

    assert keyword_present("digital marketing and legit work", ["git"]) == []
    assert keyword_present("used git and github daily", ["git"]) == ["git"]
    assert keyword_present("collaborated with a team", ["collaborat"]) == ["collaborat"]


def test_strong_cv_experience_not_flagged_as_gap():
    r = analyse(STRONG_CV)
    gap_names = [g["criterion"] for g in r["gaps"]]
    assert "Practical experience" not in gap_names

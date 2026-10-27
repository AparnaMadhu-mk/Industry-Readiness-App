import io

from tests.conftest import STRONG_CV, make_docx, make_pdf


def post_cv(client, data, name="cv.pdf", consent=True, path="/analyze", **extra):
    form = {"cv": (io.BytesIO(data), name), "role": "web", "name": "Aparna"}
    if consent:
        form["consent"] = "on"
    form.update(extra)
    return client.post(path, data=form, content_type="multipart/form-data")


def test_home_and_methodology_pages(client):
    assert client.get("/").status_code == 200
    assert b"How your score is calculated" in client.get("/methodology").data


def test_full_flow_pdf(client):
    r = post_cv(client, make_pdf(STRONG_CV))
    assert r.status_code == 302
    rid = r.headers["Location"].rsplit("/", 1)[-1]
    page = client.get(f"/results/{rid}")
    assert page.status_code == 200 and b"Top recommendations" in page.data
    pdf = client.get(f"/report/{rid}")
    assert pdf.status_code == 200 and pdf.data[:5] == b"%PDF-"
    data = client.get(f"/api/results/{rid}").get_json()
    assert set(data["dimensions"]) >= {"recruiter_appeal", "professional_standards"}
    assert 0 <= data["overall"] <= 100


def test_full_flow_docx_and_delete(client):
    r = post_cv(client, make_docx(STRONG_CV), name="cv.docx")
    rid = r.headers["Location"].rsplit("/", 1)[-1]
    assert client.delete(f"/api/results/{rid}").get_json()["deleted"] is True
    assert client.get(f"/api/results/{rid}").status_code == 404


def test_api_analyze_json(client):
    r = post_cv(client, make_pdf(STRONG_CV), path="/api/analyze")
    assert r.status_code == 201 and "id" in r.get_json()


def test_consent_required(client):
    assert post_cv(client, make_pdf(STRONG_CV), consent=False).status_code == 400
    assert post_cv(client, make_pdf(STRONG_CV), consent=False, path="/api/analyze").status_code == 400


def test_unsupported_empty_and_corrupt_files_show_friendly_errors(client):
    r = post_cv(client, b"hello", name="cv.txt")
    assert r.status_code == 400 and b"Unsupported file type" in r.data
    r = post_cv(client, b"", name="cv.pdf")
    assert r.status_code == 422 and b"empty" in r.data
    r = post_cv(client, b"%PDF-1.4 broken", name="cv.pdf")
    assert r.status_code == 422 and b"couldn" in r.data
    r = post_cv(client, make_pdf("  "), name="cv.pdf")
    assert r.status_code == 422 and b"no selectable text" in r.data


def test_missing_file(client):
    r = client.post("/analyze", data={"role": "web", "consent": "on"}, content_type="multipart/form-data")
    assert r.status_code == 400 and b"No file selected" in r.data


def test_assessment_flow_updates_overall(client):
    r = post_cv(client, make_pdf(STRONG_CV))
    rid = r.headers["Location"].rsplit("/", 1)[-1]
    before = client.get(f"/api/results/{rid}").get_json()["overall"]
    page = client.get(f"/assessment/{rid}")
    assert page.status_code == 200 and b"Submit test" in page.data
    # answer everything wrong (index 3 is wrong for nearly all questions) to prove the score changes
    ids = client.get("/api/assessment/web").get_json()
    form = {"question_ids": ",".join(q["id"] for q in ids)}
    form.update({f"q_{q['id']}": "0" for q in ids})
    sub = client.post(f"/assessment/{rid}/submit", data=form)
    assert sub.status_code == 302
    res = client.get(f"/assessment/{rid}/result")
    assert res.status_code == 200 and b"Review" in res.data
    after = client.get(f"/api/results/{rid}").get_json()
    assert "assessment" in after["weights"] and after["overall"] != before


def test_404_pages(client):
    assert client.get("/results/doesnotexist").status_code == 404
    assert client.get("/api/results/doesnotexist").status_code == 404


def test_rate_limit(client):
    import app as app_module

    app_module._hits.clear()
    codes = [post_cv(client, make_pdf(STRONG_CV)).status_code for _ in range(17)]
    assert 429 in codes
    app_module._hits.clear()

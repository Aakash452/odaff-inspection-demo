import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SQLITE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import pytest  # noqa: E402

from app import app  # noqa: E402
from scripts.sample_payload import sample_payload  # noqa: E402


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_full_submission_saves_rows_and_pdf(client):
    res = client.post("/api/inspections", json=sample_payload())
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["number"].startswith("CF-2026-")
    pdf_res = client.get(body["pdf_url"])
    assert pdf_res.status_code == 200
    assert pdf_res.data[:4] == b"%PDF"

    import db
    insp = db.get_inspection(body["id"])
    assert len(insp["samples"]) == 3
    assert insp["checklist"]["L2"] == "No"
    assert [v["ItemCode"] for v in insp["violations"]] == ["L2", "F2"]
    assert insp["StopSaleUnits"] == 36


def test_no_answer_without_violation_is_rejected(client):
    p = sample_payload()
    p["violations"] = [v for v in p["violations"] if v["item_code"] != "F2"]
    res = client.post("/api/inspections", json=p)
    assert res.status_code == 422
    assert "checklist.F2" in res.get_json()["errors"]


def test_conditional_item_ignored_when_not_applicable(client):
    p = sample_payload()
    p["checklist"]["L5"] = "garbage"  # L5 only applies to medicated-feed inspections
    assert client.post("/api/inspections", json=p).status_code == 201


def test_conditional_item_required_when_applicable(client):
    p = sample_payload()
    p["inspection_type"] = "Medicated feed"
    res = client.post("/api/inspections", json=p)
    assert res.status_code == 422
    assert "checklist.L5" in res.get_json()["errors"]


def test_stop_sale_requires_order_and_units(client):
    p = sample_payload()
    p["stop_sale_order_number"] = ""
    p["stop_sale_units"] = "0"
    errors = client.post("/api/inspections", json=p).get_json()["errors"]
    assert {"stop_sale_order_number", "stop_sale_units"} <= errors.keys()


def test_refused_signature_needs_remark(client):
    p = sample_payload()
    p.update(rep_refused_to_sign=True, firm_rep_signature=None, remarks="")
    errors = client.post("/api/inspections", json=p).get_json()["errors"]
    assert "remarks" in errors and "firm_rep_signature" not in errors


def test_bad_row_fields_are_keyed_by_path(client):
    p = sample_payload()
    p["samples"][1]["crude_protein_pct"] = "140"
    p["zip"] = "7304"
    errors = client.post("/api/inspections", json=p).get_json()["errors"]
    assert "samples[1].crude_protein_pct" in errors and "zip" in errors


def test_html_in_input_is_escaped_in_pdf():
    import pdf
    import db
    from forms import feed_inspection as F
    from validation import validate
    p = sample_payload()
    p["remarks"] = "<script>alert(1)</script>"
    clean, errors = validate(p)
    assert not errors
    iid, _ = db.save_inspection(clean, F.FORM_CODE, F.NUMBER_PREFIX, p)
    html = pdf.render_html(db.get_inspection(iid))
    assert "<script>" not in html and "&lt;script&gt;" in html

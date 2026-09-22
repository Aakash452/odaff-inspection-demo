"""
Inspections demo - Flask app.

GET  /                              the CF-101 inspection form
POST /api/inspections               validate -> save to SQL -> build + store PDF
GET  /api/inspections               recent inspections (JSON)
GET  /inspections/<id>/pdf          stored PDF for an inspection
"""
import io
import logging

from flask import Flask, abort, jsonify, render_template, request, send_file

import db
import pdf
from forms import feed_inspection as F
from validation import validate

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # signatures are small; reject oversized bodies
log = logging.getLogger("inspections")
db.init_db()


@app.get("/")
def feed_form():
    return render_template("feed_inspection_form.html", form=F)


@app.post("/api/inspections")
def create_inspection():
    payload = request.get_json(silent=True)
    clean, errors = validate(payload)
    if errors:
        return jsonify({"ok": False, "errors": errors}), 422

    try:
        inspection_id, number = db.save_inspection(clean, F.FORM_CODE, F.NUMBER_PREFIX, payload)
    except Exception:
        log.exception("Saving inspection failed")
        return jsonify({"ok": False, "errors": {"_form": "The inspection could not be saved. Your entries are kept on this device; try again."}}), 500

    try:
        _, _, digest = pdf.build_pdf(inspection_id)
    except Exception:
        # The data is safe in SQL; the PDF can be regenerated later from the stored record.
        log.exception("PDF build failed for inspection %s", inspection_id)
        return jsonify({"ok": True, "id": inspection_id, "number": number, "pdf_url": None,
                        "warning": "Saved, but the PDF could not be created yet."}), 201

    return jsonify({"ok": True, "id": inspection_id, "number": number,
                    "pdf_url": f"/inspections/{inspection_id}/pdf", "sha256": digest}), 201


@app.get("/api/inspections")
def recent_inspections():
    rows = db.list_inspections()
    for r in rows:
        r["InspectionDate"] = str(r["InspectionDate"])
    return jsonify(rows)


@app.get("/inspections/<int:inspection_id>/pdf")
def inspection_pdf(inspection_id):
    doc = db.get_latest_document(inspection_id)
    if doc is None:
        abort(404)
    return send_file(io.BytesIO(doc["Content"]), mimetype="application/pdf",
                     download_name=doc["FileName"], as_attachment=False)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

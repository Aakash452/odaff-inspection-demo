"""
Saved inspection data -> Jinja template -> HTML -> PDF (WeasyPrint).

The PDF is built from what is in the database, not from what the browser
sent, so the document always matches the stored record. Each PDF is saved
to InspectionDocuments with a SHA-256 hash of its bytes.
"""
import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

import db
from forms import feed_inspection as F

BASE = Path(__file__).parent
env = Environment(
    loader=FileSystemLoader(BASE / "templates"),
    autoescape=select_autoescape(["html"]),  # inspector text is escaped, never trusted as HTML
    trim_blocks=True,
    lstrip_blocks=True,
)


def _png_data_url(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode() if raw else None


def _fmt_date(value):
    if not value:
        return ""
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%m/%d/%Y")


def _fmt_time(value):
    if not value:
        return ""
    return datetime.strptime(str(value)[:5], "%H:%M").strftime("%I:%M %p").lstrip("0")


env.filters["usdate"] = _fmt_date
env.filters["ustime"] = _fmt_time


def render_html(insp):
    applicable = [item for item in F.CHECKLIST if item["code"] in insp["checklist"]]
    return env.get_template("pdf/feed_inspection.html").render(
        form=F,
        insp=insp,
        checklist=applicable,
        inspector_sig=_png_data_url(insp["InspectorSignature"]),
        rep_sig=_png_data_url(insp["FirmRepSignature"]),
        generated_at=datetime.now(timezone.utc).strftime("%m/%d/%Y %H:%M UTC"),
    )


def build_pdf(inspection_id, store=True):
    insp = db.get_inspection(inspection_id)
    if insp is None:
        raise LookupError(f"Inspection {inspection_id} not found")
    html = render_html(insp)
    pdf_bytes = HTML(string=html, base_url=str(BASE / "static")).write_pdf()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    file_name = f"{insp['InspectionNumber']}.pdf"
    if store:
        db.save_document(inspection_id, file_name, pdf_bytes, digest)
    return file_name, pdf_bytes, digest

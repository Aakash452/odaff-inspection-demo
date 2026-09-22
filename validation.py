"""
Server-side validation for CF-101.

The browser validates for speed; the server validates because the browser
can be bypassed. Both apply the same rules, and errors are keyed by the
field path the form uses (e.g. "samples[0].product_name") so the page can
point the inspector to the exact input.
"""
import base64
import re
from datetime import date, datetime

from forms import feed_inspection as F

REQUIRED = {
    "firm_name": "Firm name",
    "license_number": "License number",
    "street_address": "Street address",
    "city": "City",
    "county": "County",
    "zip": "ZIP code",
    "inspection_date": "Inspection date",
    "time_in": "Time in",
    "inspection_type": "Inspection type",
    "firm_type": "Firm type",
    "inspector_name": "Inspector name",
    "inspector_badge": "Inspector badge number",
}

ZIP_RE = re.compile(r"^\d{5}$")
PHONE_RE = re.compile(r"^\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$")
LICENSE_RE = re.compile(r"^[A-Z0-9-]{4,30}$")
PNG_PREFIX = "data:image/png;base64,"


def _s(value):
    return value.strip() if isinstance(value, str) else ""


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _parse_time(value):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return None


def _decode_signature(data_url):
    if not isinstance(data_url, str) or not data_url.startswith(PNG_PREFIX):
        return None
    try:
        raw = base64.b64decode(data_url[len(PNG_PREFIX):], validate=True)
    except ValueError:
        return None
    return raw if raw.startswith(b"\x89PNG") and len(raw) < 500_000 else None


def validate(payload, today=None):
    """Return (clean, errors). `clean` is ready for db.save_inspection."""
    today = today or date.today()
    errors = {}
    clean = {}

    if not isinstance(payload, dict):
        return None, {"_form": "Request body must be a JSON object."}

    # Part 1: establishment and visit
    for key, label in REQUIRED.items():
        clean[key] = _s(payload.get(key))
        if not clean[key]:
            errors[key] = f"{label} is required."

    for key in ("contact_name", "contact_phone", "time_out", "remarks", "firm_rep_name",
                "stop_sale_order_number"):
        clean[key] = _s(payload.get(key)) or None

    clean["license_number"] = clean["license_number"].upper()
    if clean["license_number"] and not LICENSE_RE.match(clean["license_number"]):
        errors["license_number"] = "Use letters, numbers and dashes only (4-30 characters)."
    if clean["zip"] and not ZIP_RE.match(clean["zip"]):
        errors["zip"] = "Enter a 5-digit ZIP code."
    if clean["county"] and clean["county"] not in F.OKLAHOMA_COUNTIES:
        errors["county"] = "Choose an Oklahoma county from the list."
    if clean["contact_phone"] and not PHONE_RE.match(clean["contact_phone"]):
        errors["contact_phone"] = "Enter a 10-digit phone number, e.g. 405-555-0142."
    if clean["inspection_type"] and clean["inspection_type"] not in F.INSPECTION_TYPES:
        errors["inspection_type"] = "Choose an inspection type from the list."
    if clean["firm_type"] and clean["firm_type"] not in F.FIRM_TYPES:
        errors["firm_type"] = "Choose a firm type from the list."

    d = _parse_date(clean["inspection_date"])
    if clean["inspection_date"] and not d:
        errors["inspection_date"] = "Enter the date as YYYY-MM-DD."
    elif d and d > today:
        errors["inspection_date"] = "Inspection date cannot be in the future."

    t_in = _parse_time(clean["time_in"])
    t_out = _parse_time(clean["time_out"]) if clean["time_out"] else None
    if clean["time_in"] and not t_in:
        errors["time_in"] = "Enter time as HH:MM."
    if clean["time_out"] and not t_out:
        errors["time_out"] = "Enter time as HH:MM."
    elif t_in and t_out and t_out < t_in:
        errors["time_out"] = "Time out must be after time in."

    # Part 2: samples (repeating rows)
    clean["samples"] = []
    for i, row in enumerate(payload.get("samples") or []):
        row = row if isinstance(row, dict) else {}
        p = f"samples[{i}]"
        s = {k: _s(row.get(k)) or None for k in
             ("product_name", "guarantor", "lot_number", "sample_type", "package_size")}
        if not s["product_name"]:
            errors[f"{p}.product_name"] = "Product name is required."
        if not s["guarantor"]:
            errors[f"{p}.guarantor"] = "Guarantor is required."
        if s["sample_type"] not in F.SAMPLE_TYPES:
            errors[f"{p}.sample_type"] = "Choose Official or Investigational."

        units = row.get("units_on_hand")
        s["units_on_hand"] = None
        if units not in (None, ""):
            try:
                s["units_on_hand"] = int(units)
                if s["units_on_hand"] < 0:
                    raise ValueError
            except (TypeError, ValueError):
                errors[f"{p}.units_on_hand"] = "Units on hand must be a whole number, 0 or more."

        cp = row.get("crude_protein_pct")
        s["crude_protein_pct"] = None
        if cp not in (None, ""):
            try:
                s["crude_protein_pct"] = round(float(cp), 2)
                if not 0 <= s["crude_protein_pct"] <= 100:
                    raise ValueError
            except (TypeError, ValueError):
                errors[f"{p}.crude_protein_pct"] = "Crude protein must be between 0 and 100."
        clean["samples"].append(s)

    # Part 3: checklist - answer every item that applies, drop the rest
    answers = payload.get("checklist") or {}
    clean["checklist"] = {}
    for item in F.CHECKLIST:
        if not F.item_applies(item, clean):
            continue
        resp = answers.get(item["code"])
        if resp not in F.CHECKLIST_RESPONSES:
            errors[f"checklist.{item['code']}"] = "Answer Yes, No or N/A."
        else:
            clean["checklist"][item["code"]] = resp

    # Part 4: violations and stop-sale
    clean["violations"] = []
    for i, row in enumerate(payload.get("violations") or []):
        row = row if isinstance(row, dict) else {}
        p = f"violations[{i}]"
        v = {
            "item_code": _s(row.get("item_code")) or None,
            "description": _s(row.get("description")),
            "corrective_action": _s(row.get("corrective_action")),
            "correct_by": _s(row.get("correct_by")) or None,
        }
        if not v["description"]:
            errors[f"{p}.description"] = "Describe the violation."
        if not v["corrective_action"]:
            errors[f"{p}.corrective_action"] = "State the corrective action required."
        if v["correct_by"]:
            cb = _parse_date(v["correct_by"])
            if not cb:
                errors[f"{p}.correct_by"] = "Enter the date as YYYY-MM-DD."
            elif d and cb < d:
                errors[f"{p}.correct_by"] = "Correct-by date must be on or after the inspection date."
        clean["violations"].append(v)

    # Cross-field rule: every "No" on the checklist needs a violation entry.
    cited = {v["item_code"] for v in clean["violations"]}
    for code, resp in clean["checklist"].items():
        if resp == "No" and code not in cited:
            errors[f"checklist.{code}"] = f"Item {code} is marked No. Add a violation for it in Part 4."

    clean["stop_sale_issued"] = bool(payload.get("stop_sale_issued"))
    clean["stop_sale_units"] = None
    if clean["stop_sale_issued"]:
        if not clean["stop_sale_order_number"]:
            errors["stop_sale_order_number"] = "Stop-sale order number is required."
        try:
            clean["stop_sale_units"] = int(payload.get("stop_sale_units"))
            if clean["stop_sale_units"] <= 0:
                raise ValueError
        except (TypeError, ValueError):
            errors["stop_sale_units"] = "Enter the number of units placed under stop-sale."
    else:
        clean["stop_sale_order_number"] = None

    # Part 5: signatures
    clean["rep_refused_to_sign"] = bool(payload.get("rep_refused_to_sign"))
    clean["inspector_signature"] = _decode_signature(payload.get("inspector_signature"))
    clean["firm_rep_signature"] = _decode_signature(payload.get("firm_rep_signature"))
    if not clean["inspector_signature"]:
        errors["inspector_signature"] = "Inspector signature is required."
    if clean["rep_refused_to_sign"]:
        clean["firm_rep_signature"] = None
        if not clean["remarks"]:
            errors["remarks"] = "Note in remarks that the representative refused to sign."
    elif not clean["firm_rep_signature"]:
        errors["firm_rep_signature"] = "Firm representative signature is required, or check 'Refused to sign'."

    return (None if errors else clean), errors

"""A realistic sample submission used by tests and scripts/generate_sample.py."""
import base64
import io
import math

from PIL import Image, ImageDraw


def fake_signature(seed=1.0):
    img = Image.new("RGBA", (600, 150), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    pts = [(40 + x, 85 + 28 * math.sin(x / (18 + seed * 4)) * math.cos(x / 55 + seed)) for x in range(0, 460, 3)]
    d.line(pts, fill=(31, 42, 34, 255), width=4, joint="curve")
    d.line([(60, 118), (300 + 60 * seed, 112)], fill=(31, 42, 34, 255), width=3)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def sample_payload():
    return {
        "firm_name": "Red Dirt Feed & Supply LLC",
        "license_number": "CF-2210-OK",
        "street_address": "1408 S Industrial Blvd",
        "city": "Guthrie",
        "zip": "73044",
        "county": "Logan",
        "contact_name": "Dana Whitfield",
        "contact_phone": "405-555-0142",
        "inspection_date": "2026-09-21",
        "time_in": "09:15",
        "time_out": "10:40",
        "inspection_type": "Routine",
        "firm_type": "Manufacturer",
        "samples": [
            {"product_name": "Range Cube 20% All-Natural", "guarantor": "Red Dirt Feed & Supply LLC",
             "lot_number": "RC20-2609-A", "sample_type": "Official", "package_size": "50 lb bag",
             "units_on_hand": "84", "crude_protein_pct": "20.00"},
            {"product_name": "Show Lamb Grower Pellet", "guarantor": "Prairie Mills Inc.",
             "lot_number": "SLG-4471", "sample_type": "Official", "package_size": "50 lb bag",
             "units_on_hand": "36", "crude_protein_pct": "16.50"},
            {"product_name": "Layer Crumble 16%", "guarantor": "Cimarron Poultry Nutrition",
             "lot_number": "", "sample_type": "Investigational", "package_size": "40 lb bag",
             "units_on_hand": "22", "crude_protein_pct": "16.00"},
        ],
        "checklist": {"L1": "Yes", "L2": "No", "L3": "Yes", "L4": "Yes", "F1": "Yes", "F2": "No", "F3": "Yes"},
        "violations": [
            {"item_code": "L2", "description": "Item L2 not met: Show Lamb Grower Pellet bags on the sales floor carry no guaranteed analysis panel.",
             "corrective_action": "Relabel all remaining units with the registered label or return them to the guarantor. Provide photos of relabeled product.",
             "correct_by": "2026-10-05"},
            {"item_code": "F2", "description": "Item F2 not met: Six torn, water-damaged bags of Layer Crumble stacked with saleable product.",
             "corrective_action": "Segregate and mark damaged product as not for sale; dispose of or return per firm procedure.",
             "correct_by": "2026-09-23"},
        ],
        "stop_sale_issued": True,
        "stop_sale_order_number": "SS-26-0917",
        "stop_sale_units": "36",
        "remarks": "Stop-sale placed on 36 bags of Show Lamb Grower Pellet (lot SLG-4471) pending relabel. Manager was cooperative and began segregating damaged Layer Crumble during the visit. Follow-up inspection to be scheduled after 10/05.",
        "inspector_name": "J. Alvarez",
        "inspector_badge": "CPS-0412",
        "firm_rep_name": "Dana Whitfield",
        "rep_refused_to_sign": False,
        "inspector_signature": fake_signature(1.0),
        "firm_rep_signature": fake_signature(2.3),
    }

"""
Form definition: Commercial Feed Inspection Report (demo form code CF-101).

One Python module per converted PDF. The same definition drives:
  * the HTML form (templates/feed_inspection_form.html loops over it),
  * server-side validation (validation.py),
  * the PDF output (templates/pdf/feed_inspection.html).

Defining a form once and reusing it in three places is what keeps
~70 conversions consistent and fast.
"""

FORM_CODE = "CF-101"
FORM_TITLE = "Commercial Feed Inspection Report"
NUMBER_PREFIX = "CF"

OKLAHOMA_COUNTIES = [
    "Adair", "Alfalfa", "Atoka", "Beaver", "Beckham", "Blaine", "Bryan", "Caddo",
    "Canadian", "Carter", "Cherokee", "Choctaw", "Cimarron", "Cleveland", "Coal",
    "Comanche", "Cotton", "Craig", "Creek", "Custer", "Delaware", "Dewey", "Ellis",
    "Garfield", "Garvin", "Grady", "Grant", "Greer", "Harmon", "Harper", "Haskell",
    "Hughes", "Jackson", "Jefferson", "Johnston", "Kay", "Kingfisher", "Kiowa",
    "Latimer", "Le Flore", "Lincoln", "Logan", "Love", "McClain", "McCurtain",
    "McIntosh", "Major", "Marshall", "Mayes", "Murray", "Muskogee", "Noble",
    "Nowata", "Okfuskee", "Oklahoma", "Okmulgee", "Osage", "Ottawa", "Pawnee",
    "Payne", "Pittsburg", "Pontotoc", "Pottawatomie", "Pushmataha", "Roger Mills",
    "Rogers", "Seminole", "Sequoyah", "Stephens", "Texas", "Tillman", "Tulsa",
    "Wagoner", "Washington", "Washita", "Woods", "Woodward",
]

INSPECTION_TYPES = ["Routine", "Complaint", "Follow-up", "Medicated feed", "Stop-sale release"]
FIRM_TYPES = ["Manufacturer", "Distributor", "Retailer", "Pet food retailer"]
SAMPLE_TYPES = ["Official", "Investigational"]
CHECKLIST_RESPONSES = ["Yes", "No", "N/A"]

# Each checklist item becomes one row in the form and one row in
# InspectionChecklist. `show_when` hides items that do not apply.
CHECKLIST = [
    {"code": "L1", "text": "All products offered for sale are registered with the Department"},
    {"code": "L2", "text": "Labels show the guaranteed analysis"},
    {"code": "L3", "text": "Labels show an ingredient statement"},
    {"code": "L4", "text": "Labels show net weight and guarantor name and address"},
    {"code": "L5", "text": "Medicated feeds carry directions for use and warnings",
     "show_when": {"field": "inspection_type", "in": ["Medicated feed"]}},
    {"code": "F1", "text": "Storage area is clean, dry and free of pests"},
    {"code": "F2", "text": "Damaged or adulterated product is segregated from product for sale"},
    {"code": "F3", "text": "Manufacturing and distribution records are kept for one year",
     "show_when": {"field": "firm_type", "in": ["Manufacturer", "Distributor"]}},
]

CHECKLIST_BY_CODE = {item["code"]: item for item in CHECKLIST}


def item_applies(item, data):
    """True when a checklist item is shown for this submission."""
    rule = item.get("show_when")
    if not rule:
        return True
    return data.get(rule["field"]) in rule["in"]

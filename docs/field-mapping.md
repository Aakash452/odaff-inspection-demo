# Converting a fillable PDF: field mapping for CF-101

Each of the ~70 PDFs goes through the same five steps. This sheet is the
record for one form; it doubles as the review checklist with the program
owner before any code is written.

## Steps per form

1. **Inventory.** Pull every AcroForm field from the existing PDF
   (`pypdf`: `PdfReader(path).get_fields()`) so nothing on the paper form is missed.
2. **Map.** Fill in the table below: PDF field, HTML input, validation, SQL column.
3. **Confirm rules with the program owner.** Which fields are required, which
   sections only apply sometimes, which answers force a follow-up.
4. **Build.** Add a definition module in `forms/`, the HTML template, a small
   form script, and a PDF template that extends `pdf/_report_base.html`.
5. **Verify.** Submit a sample through the API, compare the generated PDF
   side by side with the original, and add tests for each business rule.

## CF-101 map

| Part | PDF field (legacy) | HTML input | Type / validation | SQL column |
|---|---|---|---|---|
| 1 | FirmName | `firm_name` | text, required, 150 | Inspections.FirmName |
| 1 | LicNo | `license_number` | text, required, `[A-Z0-9-]{4,30}` | Inspections.LicenseNumber |
| 1 | Address | `street_address` | text, required | Inspections.StreetAddress |
| 1 | City / Zip | `city`, `zip` | text; ZIP 5 digits | Inspections.City, .Zip |
| 1 | County | `county` | select, 77 Oklahoma counties | Inspections.County |
| 1 | Contact / Phone | `contact_name`, `contact_phone` | optional; 10-digit phone | Inspections.ContactName, .ContactPhone |
| 1 | Date, TimeIn, TimeOut | `inspection_date`, `time_in`, `time_out` | date not in future; out after in | Inspections.InspectionDate, .TimeIn, .TimeOut |
| 1 | InspType checkboxes | `inspection_type` | select, one value | Inspections.InspectionType |
| 1 | FirmType checkboxes | `firm_type` | select, one value | Inspections.FirmType |
| 2 | Sample rows 1-6 (fixed on PDF) | `samples[]` repeater | unlimited rows; product and guarantor required; protein 0-100 | InspectionSamples.* |
| 3 | Item L1-F3 Yes/No/NA | `checklist.<code>` radios | required when shown; L5 only for medicated feed; F3 only for manufacturer/distributor | InspectionChecklist (one row per item) |
| 4 | Violation rows 1-4 (fixed on PDF) | `violations[]` repeater | description and action required; "No" on any item must have a violation | InspectionViolations.* |
| 4 | StopSale checkbox, order no., units | `stop_sale_*` | order and units required when checked | Inspections.StopSale* |
| 5 | Remarks | `remarks` | required when rep refuses to sign | Inspections.Remarks |
| 5 | Inspector name / badge | `inspector_name`, `inspector_badge` | required | Inspections.InspectorName, .InspectorBadge |
| 5 | Signatures | canvas pads | PNG; inspector required; rep required unless refused | Inspections.InspectorSignature, .FirmRepSignature |
| - | (generated) | - | - | InspectionDocuments (PDF bytes + SHA-256) |

Improvements over the paper form: sample and violation rows are no longer
capped by the page, conditional items only appear when they apply, and a
"No" answer cannot be saved without the matching violation.

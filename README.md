# Inspections demo: fillable PDF → HTML form → SQL → PDF

A working sample of the core task in the ODAFF Consumer Protection Services
Inspections role: take a fillable PDF inspection document, rebuild it as an
interactive HTML form, save the inspector's entries to SQL, and compile them
back into a PDF with a Jinja template.

Built by **Bhagyesh Parmar** · [bhagyeshparmar.me](https://bhagyeshparmar.me) · GitHub [Aakash452](https://github.com/Aakash452)

> The sample form, **CF-101 Commercial Feed Inspection Report**, is modeled on
> the kind of content a feed inspection covers. It is not the Department's
> actual form, and the generated PDF is marked as a demonstration document.

![Flow](docs/flow.png)

| Desktop | Phone | Validation |
|---|---|---|
| ![Form](docs/form-desktop.png) | ![Mobile](docs/form-mobile.png) | ![Errors](docs/form-errors.png) |

Sample output: [`sample_output/CF-2026-000001.pdf`](sample_output/CF-2026-000001.pdf)

## What it does

1. **HTML form** (`templates/feed_inspection_form.html`) mirrors the paper form's
   Parts 1-5 and is sized for tablets: 16px text, 44px touch targets, works on a phone.
2. **JavaScript** (`static/js/`) handles repeating rows for samples and
   violations, conditional checklist items, finger/stylus signature pads,
   inline validation with an error summary, and draft autosave so a dropped
   connection in the field does not lose work. Marking a checklist item **No**
   adds a matching violation to Part 4 automatically.
3. **API** (`app.py`, Flask) re-validates everything on the server
   (`validation.py`) and saves the header, samples, checklist and violations
   in **one transaction** (`db.py`).
4. **SQL** (`sql/schema.mssql.sql`) is T-SQL for SQL Server: identity keys,
   foreign keys with cascade, CHECK constraints (including `ISJSON` on the raw
   payload), indexes for the lookups supervisors run, and a summary view.
5. **PDF** (`pdf.py`, `templates/pdf/`) renders the *stored* record through a
   Jinja template and WeasyPrint, then saves the PDF bytes and a SHA-256 hash
   to `InspectionDocuments`.

## Run it

```bash
pip install -r requirements.txt
python app.py                       # http://localhost:5000  (SQLite, zero setup)
python -m pytest -q                 # 8 tests: happy path + every business rule
python scripts/generate_sample.py   # writes sample_output/CF-2026-000001.pdf
```

Against SQL Server:

```bash
docker compose up --build
docker compose exec db /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "YourStrong!Passw0rd" -C -i /schema/schema.mssql.sql
```

`DB_DIALECT=mssql` switches `db.py` to pyodbc; queries are the same
parameterized SQL, with `OUTPUT INSERTED` / `TOP` in place of SQLite's
`RETURNING` / `LIMIT`.

## Built to scale to ~70 forms

The expensive part of this project is repetition, so the code is split into
what every form shares and what each form owns:

| Shared (written once) | Per form (small) |
|---|---|
| `static/js/form-core.js`: repeaters, conditionals, signatures, validation, drafts | `forms/<form>.py`: fields, options, checklist items, show-when rules |
| `templates/pdf/_report_base.html`: masthead, fonts, page numbers, footer | `templates/<form>_form.html` |
| `db.py` transaction + insert helpers, `InspectionDocuments` | `static/js/<form>.js`: that form's business rules |
| `pdf.py` render/store pipeline | `templates/pdf/<form>.html` (extends the base) |

`docs/field-mapping.md` shows the per-form checklist: inventory the PDF's
fields, map each to an input and a column, confirm rules with the program
owner, build, and verify against the original.

## Project layout

```
app.py                  Flask routes
validation.py           server-side rules, errors keyed by field path
db.py                   SQL Server / SQLite data access, one transaction per save
pdf.py                  Jinja + WeasyPrint, stores PDF + SHA-256
forms/feed_inspection.py   form definition shared by HTML, validation and PDF
templates/              HTML form and PDF templates
static/                 CSS, JS, Public Sans font
sql/                    T-SQL schema (+ SQLite mirror for local runs)
tests/                  pytest suite
docs/                   field mapping, screenshots
Dockerfile, docker-compose.yml
```

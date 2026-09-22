"""
Data access for inspections.

DB_DIALECT=mssql    -> Microsoft SQL Server through pyodbc (production target)
DB_DIALECT=postgres -> Postgres through psycopg2 (serverless target, e.g. Vercel)
DB_DIALECT=sqlite   -> local file, zero setup (default for the demo)

Every query is written with `?` placeholders; `_exec` rewrites them to `%s`
for postgres. A whole inspection - header, samples, checklist, violations -
is saved in one transaction, so a failed insert never leaves half a record
behind.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DIALECT = os.getenv("DB_DIALECT", "sqlite").lower()
SQLITE_PATH = os.getenv("SQLITE_PATH", str(Path(__file__).parent / "inspections.db"))
MSSQL_CONN = os.getenv(
    "MSSQL_CONN",
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;DATABASE=Inspections;"
    "UID=sa;PWD=YourStrong!Passw0rd;TrustServerCertificate=yes",
)
DATABASE_URL = os.getenv("DATABASE_URL")

# Postgres folds unquoted identifiers to lowercase, so `SELECT *` comes back with
# lowercase keys. The rest of the app (templates included) reads exact PascalCase
# keys, so _rows() remaps through this table instead of quoting every identifier.
_CANON_COLUMNS = {
    "inspectionid": "InspectionID", "inspectionnumber": "InspectionNumber", "formcode": "FormCode",
    "firmname": "FirmName", "licensenumber": "LicenseNumber", "streetaddress": "StreetAddress",
    "city": "City", "county": "County", "zip": "Zip", "contactname": "ContactName",
    "contactphone": "ContactPhone", "inspectiondate": "InspectionDate", "timein": "TimeIn",
    "timeout": "TimeOut", "inspectiontype": "InspectionType", "firmtype": "FirmType",
    "stopsaleissued": "StopSaleIssued", "stopsaleordernumber": "StopSaleOrderNumber",
    "stopsaleunits": "StopSaleUnits", "remarks": "Remarks", "inspectorname": "InspectorName",
    "inspectorbadge": "InspectorBadge", "firmrepname": "FirmRepName",
    "reprefusedtosign": "RepRefusedToSign", "inspectorsignature": "InspectorSignature",
    "firmrepsignature": "FirmRepSignature", "status": "Status", "rawpayload": "RawPayload",
    "createdat": "CreatedAt", "sampleid": "SampleID", "linenumber": "LineNumber",
    "productname": "ProductName", "guarantor": "Guarantor", "lotnumber": "LotNumber",
    "sampletype": "SampleType", "packagesize": "PackageSize", "unitsonhand": "UnitsOnHand",
    "crudeproteinpct": "CrudeProteinPct", "itemcode": "ItemCode", "response": "Response",
    "violationid": "ViolationID", "description": "Description", "correctiveaction": "CorrectiveAction",
    "correctby": "CorrectBy", "documentid": "DocumentID", "filename": "FileName",
    "contenttype": "ContentType", "content": "Content", "sizebytes": "SizeBytes", "sha256": "Sha256",
}


def _connect():
    if DIALECT == "mssql":
        import pyodbc  # imported lazily so the SQLite demo needs no ODBC driver
        return pyodbc.connect(MSSQL_CONN, autocommit=False)
    if DIALECT == "postgres":
        import psycopg2  # imported lazily so the SQLite demo needs no postgres driver
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _exec(cur, sql, params=()):
    if DIALECT == "postgres":
        sql = sql.replace("?", "%s")
    cur.execute(sql, params)


@contextmanager
def transaction():
    conn = _connect()
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables for SQLite and Postgres. For SQL Server run sql/schema.mssql.sql."""
    if DIALECT not in ("sqlite", "postgres"):
        return
    ddl_file = "schema.postgres.sql" if DIALECT == "postgres" else "schema.sqlite.sql"
    ddl = (Path(__file__).parent / "sql" / ddl_file).read_text()
    conn = _connect()
    if DIALECT == "postgres":
        conn.cursor().execute(ddl)
        conn.commit()
    else:
        conn.executescript(ddl)
    conn.close()


def _insert_returning_id(cur, table, id_col, row):
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    if DIALECT == "mssql":
        sql = f"INSERT INTO dbo.{table} ({cols}) OUTPUT INSERTED.{id_col} VALUES ({marks})"
    else:
        sql = f"INSERT INTO {table} ({cols}) VALUES ({marks}) RETURNING {id_col}"
    _exec(cur, sql, list(row.values()))
    return int(cur.fetchone()[0])


def _t(name):
    return f"dbo.{name}" if DIALECT == "mssql" else name


def save_inspection(clean, form_code, number_prefix, raw_payload):
    """Insert one inspection and its child rows. Returns (inspection_id, inspection_number)."""
    header = {
        "FormCode": form_code,
        "FirmName": clean["firm_name"],
        "LicenseNumber": clean["license_number"],
        "StreetAddress": clean["street_address"],
        "City": clean["city"],
        "County": clean["county"],
        "Zip": clean["zip"],
        "ContactName": clean["contact_name"],
        "ContactPhone": clean["contact_phone"],
        "InspectionDate": clean["inspection_date"],
        "TimeIn": clean["time_in"],
        "TimeOut": clean["time_out"],
        "InspectionType": clean["inspection_type"],
        "FirmType": clean["firm_type"],
        "StopSaleIssued": int(clean["stop_sale_issued"]),
        "StopSaleOrderNumber": clean["stop_sale_order_number"],
        "StopSaleUnits": clean["stop_sale_units"],
        "Remarks": clean["remarks"],
        "InspectorName": clean["inspector_name"],
        "InspectorBadge": clean["inspector_badge"],
        "FirmRepName": clean["firm_rep_name"],
        "RepRefusedToSign": int(clean["rep_refused_to_sign"]),
        "InspectorSignature": clean["inspector_signature"],
        "FirmRepSignature": clean["firm_rep_signature"],
        "RawPayload": json.dumps(raw_payload),
    }
    with transaction() as cur:
        new_id = _insert_returning_id(cur, "Inspections", "InspectionID", header)
        number = f"{number_prefix}-{clean['inspection_date'][:4]}-{new_id:06d}"
        _exec(cur, f"UPDATE {_t('Inspections')} SET InspectionNumber = ? WHERE InspectionID = ?",
                    (number, new_id))

        for line, s in enumerate(clean["samples"], start=1):
            _exec(cur,
                f"INSERT INTO {_t('InspectionSamples')} (InspectionID, LineNumber, ProductName, "
                "Guarantor, LotNumber, SampleType, PackageSize, UnitsOnHand, CrudeProteinPct) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (new_id, line, s["product_name"], s["guarantor"], s["lot_number"],
                 s["sample_type"], s["package_size"], s["units_on_hand"], s["crude_protein_pct"]),
            )
        for code, resp in clean["checklist"].items():
            _exec(cur,
                f"INSERT INTO {_t('InspectionChecklist')} (InspectionID, ItemCode, Response) VALUES (?, ?, ?)",
                (new_id, code, resp),
            )
        for line, v in enumerate(clean["violations"], start=1):
            _exec(cur,
                f"INSERT INTO {_t('InspectionViolations')} (InspectionID, LineNumber, ItemCode, "
                "Description, CorrectiveAction, CorrectBy) VALUES (?, ?, ?, ?, ?, ?)",
                (new_id, line, v["item_code"], v["description"], v["corrective_action"], v["correct_by"]),
            )
    return new_id, number


def _rows(cur):
    cols = [c[0] for c in cur.description]
    if DIALECT == "postgres":
        cols = [_CANON_COLUMNS.get(c, c) for c in cols]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_inspection(inspection_id):
    """Load an inspection with all child rows, shaped for the PDF template."""
    with transaction() as cur:
        _exec(cur, f"SELECT * FROM {_t('Inspections')} WHERE InspectionID = ?", (inspection_id,))
        found = _rows(cur)
        if not found:
            return None
        insp = found[0]
        _exec(cur, f"SELECT * FROM {_t('InspectionSamples')} WHERE InspectionID = ? ORDER BY LineNumber",
                    (inspection_id,))
        insp["samples"] = _rows(cur)
        _exec(cur, f"SELECT ItemCode, Response FROM {_t('InspectionChecklist')} WHERE InspectionID = ?",
                    (inspection_id,))
        insp["checklist"] = {r["ItemCode"]: r["Response"] for r in _rows(cur)}
        _exec(cur, f"SELECT * FROM {_t('InspectionViolations')} WHERE InspectionID = ? ORDER BY LineNumber",
                    (inspection_id,))
        insp["violations"] = _rows(cur)
    return insp


def save_document(inspection_id, file_name, content, sha256):
    with transaction() as cur:
        return _insert_returning_id(cur, "InspectionDocuments", "DocumentID", {
            "InspectionID": inspection_id,
            "FileName": file_name,
            "ContentType": "application/pdf",
            "Content": content,
            "SizeBytes": len(content),
            "Sha256": sha256,
        })


def get_latest_document(inspection_id):
    top = "TOP 1 " if DIALECT == "mssql" else ""
    limit = "" if DIALECT == "mssql" else " LIMIT 1"
    with transaction() as cur:
        _exec(cur,
            f"SELECT {top}FileName, Content, Sha256 FROM {_t('InspectionDocuments')} "
            f"WHERE InspectionID = ? ORDER BY DocumentID DESC{limit}",
            (inspection_id,),
        )
        rows = _rows(cur)
    return rows[0] if rows else None


def list_inspections(limit=50):
    top = f"TOP {int(limit)} " if DIALECT == "mssql" else ""
    tail = "" if DIALECT == "mssql" else f" LIMIT {int(limit)}"
    with transaction() as cur:
        _exec(cur,
            f"SELECT {top}InspectionID, InspectionNumber, FirmName, County, InspectionDate, "
            f"InspectionType, InspectorName FROM {_t('Inspections')} ORDER BY InspectionID DESC{tail}"
        )
        return _rows(cur)

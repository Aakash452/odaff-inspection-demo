-- PostgreSQL mirror of schema.mssql.sql for serverless deployments (e.g. Vercel + Neon/Vercel Postgres).
-- Column names and constraints match the SQL Server schema 1:1. Identifiers are left
-- unquoted (Postgres folds them to lowercase); db.py remaps result keys back to the
-- canonical PascalCase used by the rest of the app.
CREATE TABLE IF NOT EXISTS Inspections (
    InspectionID        SERIAL PRIMARY KEY,
    InspectionNumber    TEXT UNIQUE,
    FormCode            TEXT NOT NULL,
    FirmName            TEXT NOT NULL,
    LicenseNumber       TEXT NOT NULL,
    StreetAddress       TEXT NOT NULL,
    City                TEXT NOT NULL,
    County              TEXT NOT NULL,
    Zip                 TEXT NOT NULL,
    ContactName         TEXT,
    ContactPhone        TEXT,
    InspectionDate      TEXT NOT NULL,
    TimeIn              TEXT NOT NULL,
    TimeOut             TEXT,
    InspectionType      TEXT NOT NULL,
    FirmType            TEXT NOT NULL,
    StopSaleIssued      INTEGER NOT NULL DEFAULT 0,
    StopSaleOrderNumber TEXT,
    StopSaleUnits       INTEGER,
    Remarks             TEXT,
    InspectorName       TEXT NOT NULL,
    InspectorBadge      TEXT NOT NULL,
    FirmRepName         TEXT,
    RepRefusedToSign    INTEGER NOT NULL DEFAULT 0,
    InspectorSignature  BYTEA,
    FirmRepSignature    BYTEA,
    Status              TEXT NOT NULL DEFAULT 'Submitted',
    RawPayload          TEXT NOT NULL CHECK (RawPayload::json IS NOT NULL),
    CreatedAt           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (StopSaleIssued = 0 OR (StopSaleOrderNumber IS NOT NULL AND StopSaleUnits > 0))
);
CREATE TABLE IF NOT EXISTS InspectionSamples (
    SampleID        SERIAL PRIMARY KEY,
    InspectionID    INTEGER NOT NULL REFERENCES Inspections(InspectionID) ON DELETE CASCADE,
    LineNumber      INTEGER NOT NULL,
    ProductName     TEXT NOT NULL,
    Guarantor       TEXT NOT NULL,
    LotNumber       TEXT,
    SampleType      TEXT NOT NULL,
    PackageSize     TEXT,
    UnitsOnHand     INTEGER,
    CrudeProteinPct REAL,
    UNIQUE (InspectionID, LineNumber)
);
CREATE TABLE IF NOT EXISTS InspectionChecklist (
    InspectionID INTEGER NOT NULL REFERENCES Inspections(InspectionID) ON DELETE CASCADE,
    ItemCode     TEXT NOT NULL,
    Response     TEXT NOT NULL CHECK (Response IN ('Yes','No','N/A')),
    PRIMARY KEY (InspectionID, ItemCode)
);
CREATE TABLE IF NOT EXISTS InspectionViolations (
    ViolationID      SERIAL PRIMARY KEY,
    InspectionID     INTEGER NOT NULL REFERENCES Inspections(InspectionID) ON DELETE CASCADE,
    LineNumber       INTEGER NOT NULL,
    ItemCode         TEXT,
    Description      TEXT NOT NULL,
    CorrectiveAction TEXT NOT NULL,
    CorrectBy        TEXT
);
CREATE TABLE IF NOT EXISTS InspectionDocuments (
    DocumentID   SERIAL PRIMARY KEY,
    InspectionID INTEGER NOT NULL REFERENCES Inspections(InspectionID) ON DELETE CASCADE,
    FileName     TEXT NOT NULL,
    ContentType  TEXT NOT NULL DEFAULT 'application/pdf',
    Content      BYTEA NOT NULL,
    SizeBytes    INTEGER NOT NULL,
    Sha256       TEXT NOT NULL,
    CreatedAt    TIMESTAMPTZ NOT NULL DEFAULT now()
);

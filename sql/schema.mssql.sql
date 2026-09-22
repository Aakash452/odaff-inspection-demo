/* =====================================================================
   Inspections schema - Microsoft SQL Server (T-SQL)
   Form: CF-101 Commercial Feed Inspection Report (demo)
   Pattern: one header table per inspection, child tables for repeating
   sections, and one shared documents table for generated PDFs.
   ===================================================================== */

IF DB_ID(N'Inspections') IS NULL CREATE DATABASE Inspections;
GO
USE Inspections;
GO

CREATE TABLE dbo.Inspections (
    InspectionID        INT IDENTITY(1,1)  NOT NULL CONSTRAINT PK_Inspections PRIMARY KEY,
    InspectionNumber    NVARCHAR(20)       NULL,
    FormCode            NVARCHAR(10)       NOT NULL,
    FirmName            NVARCHAR(150)      NOT NULL,
    LicenseNumber       NVARCHAR(30)       NOT NULL,
    StreetAddress       NVARCHAR(200)      NOT NULL,
    City                NVARCHAR(80)       NOT NULL,
    County              NVARCHAR(40)       NOT NULL,
    Zip                 CHAR(5)            NOT NULL,
    ContactName         NVARCHAR(100)      NULL,
    ContactPhone        NVARCHAR(20)       NULL,
    InspectionDate      DATE               NOT NULL,
    TimeIn              TIME(0)            NOT NULL,
    TimeOut             TIME(0)            NULL,
    InspectionType      NVARCHAR(30)       NOT NULL,
    FirmType            NVARCHAR(30)       NOT NULL,
    StopSaleIssued      BIT                NOT NULL CONSTRAINT DF_Insp_StopSale DEFAULT (0),
    StopSaleOrderNumber NVARCHAR(30)       NULL,
    StopSaleUnits       INT                NULL,
    Remarks             NVARCHAR(MAX)      NULL,
    InspectorName       NVARCHAR(100)      NOT NULL,
    InspectorBadge      NVARCHAR(20)       NOT NULL,
    FirmRepName         NVARCHAR(100)      NULL,
    RepRefusedToSign    BIT                NOT NULL CONSTRAINT DF_Insp_Refused DEFAULT (0),
    InspectorSignature  VARBINARY(MAX)     NULL,   -- PNG bytes from the signature pad
    FirmRepSignature    VARBINARY(MAX)     NULL,
    Status              NVARCHAR(20)       NOT NULL CONSTRAINT DF_Insp_Status DEFAULT (N'Submitted'),
    RawPayload          NVARCHAR(MAX)      NOT NULL,  -- exact JSON received, for audit
    CreatedAt           DATETIME2(0)       NOT NULL CONSTRAINT DF_Insp_Created DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT UQ_Inspections_Number UNIQUE (InspectionNumber),
    CONSTRAINT CK_Insp_Payload_IsJson CHECK (ISJSON(RawPayload) = 1),
    CONSTRAINT CK_Insp_StopSale CHECK (StopSaleIssued = 0 OR (StopSaleOrderNumber IS NOT NULL AND StopSaleUnits > 0))
);

CREATE TABLE dbo.InspectionSamples (
    SampleID         INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_InspectionSamples PRIMARY KEY,
    InspectionID     INT               NOT NULL CONSTRAINT FK_Samples_Inspection REFERENCES dbo.Inspections(InspectionID) ON DELETE CASCADE,
    LineNumber       SMALLINT          NOT NULL,
    ProductName      NVARCHAR(150)     NOT NULL,
    Guarantor        NVARCHAR(150)     NOT NULL,
    LotNumber        NVARCHAR(50)      NULL,
    SampleType       NVARCHAR(20)      NOT NULL,
    PackageSize      NVARCHAR(30)      NULL,
    UnitsOnHand      INT               NULL,
    CrudeProteinPct  DECIMAL(5,2)      NULL,
    CONSTRAINT UQ_Samples_Line UNIQUE (InspectionID, LineNumber)
);

CREATE TABLE dbo.InspectionChecklist (
    InspectionID  INT          NOT NULL CONSTRAINT FK_Checklist_Inspection REFERENCES dbo.Inspections(InspectionID) ON DELETE CASCADE,
    ItemCode      NVARCHAR(10) NOT NULL,
    Response      NVARCHAR(3)  NOT NULL CONSTRAINT CK_Checklist_Response CHECK (Response IN (N'Yes', N'No', N'N/A')),
    CONSTRAINT PK_InspectionChecklist PRIMARY KEY (InspectionID, ItemCode)
);

CREATE TABLE dbo.InspectionViolations (
    ViolationID       INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_InspectionViolations PRIMARY KEY,
    InspectionID      INT               NOT NULL CONSTRAINT FK_Violations_Inspection REFERENCES dbo.Inspections(InspectionID) ON DELETE CASCADE,
    LineNumber        SMALLINT          NOT NULL,
    ItemCode          NVARCHAR(10)      NULL,   -- links back to the checklist item, if any
    Description       NVARCHAR(500)     NOT NULL,
    CorrectiveAction  NVARCHAR(500)     NOT NULL,
    CorrectBy         DATE              NULL
);

CREATE TABLE dbo.InspectionDocuments (
    DocumentID    INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_InspectionDocuments PRIMARY KEY,
    InspectionID  INT               NOT NULL CONSTRAINT FK_Documents_Inspection REFERENCES dbo.Inspections(InspectionID) ON DELETE CASCADE,
    FileName      NVARCHAR(200)     NOT NULL,
    ContentType   NVARCHAR(50)      NOT NULL CONSTRAINT DF_Docs_Type DEFAULT (N'application/pdf'),
    Content       VARBINARY(MAX)    NOT NULL,
    SizeBytes     INT               NOT NULL,
    Sha256        CHAR(64)          NOT NULL,   -- tamper check for the official record
    CreatedAt     DATETIME2(0)      NOT NULL CONSTRAINT DF_Docs_Created DEFAULT (SYSUTCDATETIME())
);

CREATE INDEX IX_Inspections_License_Date ON dbo.Inspections (LicenseNumber, InspectionDate DESC);
CREATE INDEX IX_Inspections_County_Date  ON dbo.Inspections (County, InspectionDate DESC);
CREATE INDEX IX_Violations_Inspection    ON dbo.InspectionViolations (InspectionID);
CREATE INDEX IX_Documents_Inspection     ON dbo.InspectionDocuments (InspectionID);
GO

/* Supervisor view: one row per inspection with roll-up counts. */
CREATE OR ALTER VIEW dbo.vInspectionSummary AS
SELECT  i.InspectionID,
        i.InspectionNumber,
        i.FirmName,
        i.County,
        i.InspectionDate,
        i.InspectionType,
        i.InspectorName,
        (SELECT COUNT(*) FROM dbo.InspectionSamples    s WHERE s.InspectionID = i.InspectionID) AS SampleCount,
        (SELECT COUNT(*) FROM dbo.InspectionViolations v WHERE v.InspectionID = i.InspectionID) AS ViolationCount,
        i.StopSaleIssued
FROM    dbo.Inspections i;
GO

/* Example report query: firms with repeat violations in the last 12 months. */
-- SELECT LicenseNumber, FirmName, COUNT(DISTINCT i.InspectionID) AS InspectionsWithViolations
-- FROM dbo.Inspections i
-- JOIN dbo.InspectionViolations v ON v.InspectionID = i.InspectionID
-- WHERE i.InspectionDate >= DATEADD(MONTH, -12, CAST(GETDATE() AS DATE))
-- GROUP BY LicenseNumber, FirmName
-- HAVING COUNT(DISTINCT i.InspectionID) > 1
-- ORDER BY InspectionsWithViolations DESC;

-- Postgresql
-- Author: Wesker
-- Date: 2025-03-19
-- Description: Schema for the database EyeOfWeb_AntiTerror


-- Custom Face Storage Table

CREATE EXTENSION IF NOT EXISTS "vector";

CREATE TABLE IF NOT EXISTS "CustomFaceStorage" (
    "ID"                SERIAL PRIMARY KEY,
    "MilvusID"          BIGINT DEFAULT NULL,
    "FaceName"          VARCHAR(255) NOT NULL,
    "FaceDescription"   TEXT DEFAULT NULL,
    "FaceImage"         BYTEA NOT NULL,
    "FaceImageHash"     VARCHAR(40) NOT NULL,
    "DetectionDate"     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS "CustomFaceStorage_MilvusID_Index" ON "CustomFaceStorage" ("MilvusID");

CREATE INDEX IF NOT EXISTS "CustomFaceStorage_DetectionDate_Index" ON "CustomFaceStorage" ("DetectionDate");
CREATE INDEX IF NOT EXISTS "CustomFaceStorage_FaceName_Index" ON "CustomFaceStorage" ("FaceName");
CREATE INDEX IF NOT EXISTS "CustomFaceStorage_FaceImageHash_Index" ON "CustomFaceStorage" ("FaceImageHash");


CREATE TABLE IF NOT EXISTS "WhiteListFaces" (
    "ID"                SERIAL PRIMARY KEY,
    "MilvusID"          BIGINT DEFAULT NULL,
    "FaceName"          VARCHAR(255) NOT NULL,
    "FaceDescription"   TEXT DEFAULT NULL,
    "FaceImage"         BYTEA NOT NULL,
    "FaceImageHash"     VARCHAR(40) NOT NULL,
    "DetectionDate"     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS "WhiteListFaces_MilvusID_Index" ON "WhiteListFaces" ("MilvusID");
CREATE INDEX IF NOT EXISTS "WhiteListFaces_DetectionDate_Index" ON "WhiteListFaces" ("DetectionDate");
CREATE INDEX IF NOT EXISTS "WhiteListFaces_FaceName_Index" ON "WhiteListFaces" ("FaceName");
CREATE INDEX IF NOT EXISTS "WhiteListFaces_FaceImageHash_Index" ON "WhiteListFaces" ("FaceImageHash");







CREATE TABLE IF NOT EXISTS "ExternalFaceStorage" (
    "ID"                SERIAL PRIMARY KEY,
    "MilvusID"          BIGINT DEFAULT NULL,
    "ImageData"         BYTEA NOT NULL,
    "ImageHash"         VARCHAR(40) NOT NULL,
    "FaceName"      VARCHAR(255) NOT NULL,
    "FaceDescription" VARCHAR(255) DEFAULT NULL,
    "Alarm"             BOOLEAN DEFAULT FALSE,
    "DetectionDate"     TIMESTAMP DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS "ExternalFaceStorage_MilvusID_Index" ON "ExternalFaceStorage" ("MilvusID");
CREATE INDEX IF NOT EXISTS idx_ExternalFaceStorage_DetectionDate ON "ExternalFaceStorage" ("DetectionDate");
CREATE INDEX IF NOT EXISTS idx_ExternalFaceStorage_FaceName ON "ExternalFaceStorage" ("FaceName");
CREATE INDEX IF NOT EXISTS idx_ExternalFaceStorage_FaceDescription ON "ExternalFaceStorage" ("FaceDescription");
CREATE INDEX IF NOT EXISTS idx_ExternalFaceStorage_ImageHash ON "ExternalFaceStorage" ("ImageHash");




-- For EGM TEROR ARANANLAR DATABASE 

CREATE TABLE IF NOT EXISTS "EgmArananlar" (
    "ID"                BIGSERIAL PRIMARY KEY,
    "MilvusID"          BIGINT DEFAULT NULL,
    "ImageData"         BYTEA NOT NULL,
    "ImageHash"         VARCHAR(40) NOT NULL,
    "FaceName"      VARCHAR(255) NOT NULL,
    "Organizer"     VARCHAR(255) NOT NULL,
    "OrganizerLevel" VARCHAR(255) NOT NULL,
    "BirthDateAndLocation"     VARCHAR(255) NOT NULL,
    "DetectionDate"     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS "EgmArananlar_MilvusID_Index" ON "EgmArananlar" ("MilvusID");
CREATE INDEX IF NOT EXISTS idx_EgmArananlar_DetectionDate ON "EgmArananlar" ("DetectionDate");
CREATE INDEX IF NOT EXISTS idx_EgmArananlar_FaceName ON "EgmArananlar" ("FaceName"); 
CREATE INDEX IF NOT EXISTS idx_EgmArananlar_Organizer ON "EgmArananlar" ("Organizer");
CREATE INDEX IF NOT EXISTS idx_EgmArananlar_OrganizerLevel ON "EgmArananlar" ("OrganizerLevel");
CREATE INDEX IF NOT EXISTS idx_EgmArananlar_BirthDateAndLocation ON "EgmArananlar" ("BirthDateAndLocation");
CREATE INDEX IF NOT EXISTS idx_EgmArananlar_ImageHash ON "EgmArananlar" ("ImageHash");


--------------------------------------






-- For EyeOfWeb Anti Terror
CREATE TABLE IF NOT EXISTS "ImageBasedMain" (
    "ID"            SERIAL PRIMARY KEY,
    "Protocol"      VARCHAR(10) DEFAULT NULL,
    "BaseDomainID"  BIGINT NOT NULL, 
    "UrlPathID"     BIGINT DEFAULT NULL, 
    "UrlEtcID"      BIGINT DEFAULT NULL,
    "ImageProtocol" VARCHAR(10) DEFAULT NULL,
    "ImageDomainID" BIGINT DEFAULT NULL,
    "ImagePathID"   BIGINT DEFAULT NULL,
    "ImageUrlEtcID" BIGINT DEFAULT NULL,
    "ImageTitleID"  BIGINT DEFAULT NULL,
    "ImageID"       BIGINT DEFAULT NULL,
    "FaceID"        BIGINT[] DEFAULT NULL,
    "RiskLevel"     VARCHAR(50) DEFAULT NULL,
    "CategoryID"    BIGINT DEFAULT NULL,
    "HashID"        BIGINT NOT NULL,  
    "Source"        TEXT DEFAULT 'www',
    "DetectionDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);

-- Removed duplicate index
CREATE INDEX IF NOT EXISTS "ImageBasedMain_BaseDomainID_Index" ON "ImageBasedMain" ("BaseDomainID");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_UrlPathID_Index" ON "ImageBasedMain" ("UrlPathID");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_UrlEtcID_Index" ON "ImageBasedMain" ("UrlEtcID");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_ImageDomainID_Index" ON "ImageBasedMain" ("ImageDomainID");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_ImagePathID_Index" ON "ImageBasedMain" ("ImagePathID");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_ImageUrlEtcID_Index" ON "ImageBasedMain" ("ImageUrlEtcID");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_ImageTitleID_Index" ON "ImageBasedMain" ("ImageTitleID");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_ImageID_Index" ON "ImageBasedMain" ("ImageID");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_FaceID_Index" ON "ImageBasedMain" ("FaceID");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_RiskLevel_Index" ON "ImageBasedMain" ("RiskLevel");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_CategoryID_Index" ON "ImageBasedMain" ("CategoryID");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_HashID_Index" ON "ImageBasedMain" ("HashID");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_DetectionDate_Index" ON "ImageBasedMain" ("DetectionDate");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_ImageProtocol_Index" ON "ImageBasedMain" ("ImageProtocol");
CREATE INDEX IF NOT EXISTS "ImageBasedMain_Source_Index" ON "ImageBasedMain" ("Source");


CREATE TABLE IF NOT EXISTS "PageBasedMain" (
    "ID"            SERIAL PRIMARY KEY,
    "Protocol"      VARCHAR(10) NOT NULL,
    "BaseDomainID"  BIGINT DEFAULT NULL, 
    "UrlPathID"     BIGINT DEFAULT NULL, 
    "UrlEtcID"      BIGINT DEFAULT NULL,
    "CategoryID"    BIGINT DEFAULT NULL,
    "PhoneID"       BIGINT[] DEFAULT NULL,
    "EmailID"       BIGINT[] DEFAULT NULL,
    "DetectionDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "PageBasedMain_DetectionDate_Index" ON "PageBasedMain" ("DetectionDate");
CREATE INDEX IF NOT EXISTS "PageBasedMain_BaseDomainID_Index" ON "PageBasedMain" ("BaseDomainID");
CREATE INDEX IF NOT EXISTS "PageBasedMain_UrlPathID_Index" ON "PageBasedMain" ("UrlPathID");
CREATE INDEX IF NOT EXISTS "PageBasedMain_UrlEtcID_Index" ON "PageBasedMain" ("UrlEtcID");
CREATE INDEX IF NOT EXISTS "PageBasedMain_CategoryID_Index" ON "PageBasedMain" ("CategoryID");
CREATE INDEX IF NOT EXISTS "PageBasedMain_PhoneID_Index" ON "PageBasedMain" ("PhoneID");
CREATE INDEX IF NOT EXISTS "PageBasedMain_EmailID_Index" ON "PageBasedMain" ("EmailID");


CREATE TABLE IF NOT EXISTS "EyeOfWebFaceID" (
    "ID"                BIGSERIAL PRIMARY KEY,
    "MilvusRefID"       BIGINT DEFAULT NULL,
    "DetectionDate"     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "EyeOfWebFaceID_MilvusRefID_Index" ON "EyeOfWebFaceID" ("MilvusRefID");
CREATE INDEX IF NOT EXISTS "EyeOfWebFaceID_DetectionDate_Index" ON "EyeOfWebFaceID" ("DetectionDate");




CREATE TABLE IF NOT EXISTS "ImageID" (
    "ID"            BIGSERIAL PRIMARY KEY,
    "BinaryImage"   BYTEA NOT NULL
);

CREATE TABLE IF NOT EXISTS "ImageHashID" (
    "ID"            BIGSERIAL PRIMARY KEY,
    "ImageHash"     VARCHAR(40), 
    "DetectionDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS "ImageHashID_ImageHash_Index" ON "ImageHashID" ("ImageHash");
CREATE INDEX IF NOT EXISTS "ImageHashID_DetectionDate_Index" ON "ImageHashID" ("DetectionDate");








CREATE TABLE IF NOT EXISTS "UrlPathID" (
    "ID"        BIGSERIAL PRIMARY KEY,
    "Path"      VARCHAR(1000) NOT NULL
);
CREATE INDEX IF NOT EXISTS "UrlPathID_Path_Index" ON "UrlPathID" ("Path");


CREATE TABLE IF NOT EXISTS "ImageTitleID" (
    "ID"        BIGSERIAL PRIMARY KEY,
    "Title"     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS "ImageTitleID_Title_Index" ON "ImageTitleID" ("Title");

CREATE TABLE IF NOT EXISTS "ImageUrlPathID" (
    "ID"        BIGSERIAL PRIMARY KEY,
    "Path"      VARCHAR(1000) NOT NULL
);
CREATE INDEX IF NOT EXISTS "ImageUrlPathID_Path_Index" ON "ImageUrlPathID" ("Path");

CREATE TABLE IF NOT EXISTS "UrlEtcID" (
    "ID"        BIGSERIAL PRIMARY KEY,
    "Etc"      VARCHAR(1000) NOT NULL
);
CREATE INDEX IF NOT EXISTS "UrlEtcID_Etc_Index" ON "UrlEtcID" ("Etc");

CREATE TABLE IF NOT EXISTS "ImageUrlEtcID" (
    "ID"        BIGSERIAL PRIMARY KEY,
    "Etc"      VARCHAR(1000) NOT NULL
);
CREATE INDEX IF NOT EXISTS "ImageUrlEtcID_Etc_Index" ON "ImageUrlEtcID" ("Etc");


CREATE TABLE IF NOT EXISTS "BaseDomainID" (
    "ID"        BIGSERIAL PRIMARY KEY,
    "Domain"    VARCHAR (150) NOT NULL
);
CREATE INDEX IF NOT EXISTS "BaseDomainID_Domain_Index" ON "BaseDomainID" ("Domain");


CREATE TABLE IF NOT EXISTS "PhoneNumberID"(
    "ID"            BIGSERIAL PRIMARY KEY,
    "PhoneNumber"   VARCHAR(20) NOT NULL
);
CREATE INDEX IF NOT EXISTS "PhoneNumberID_PhoneNumber_Index" ON "PhoneNumberID" ("PhoneNumber");

CREATE TABLE IF NOT EXISTS "EmailAddressID"(
    "ID"            SERIAL PRIMARY KEY,
    "EmailAddress"  VARCHAR(100) NOT NULL
);
CREATE INDEX IF NOT EXISTS "EmailAddressID_EmailAddress_Index" ON "EmailAddressID" ("EmailAddress");


CREATE TABLE IF NOT EXISTS "WebSiteCategoryID"(
    "ID"        BIGSERIAL PRIMARY KEY,
    "Category"  VARCHAR(100) NOT NULL
);
CREATE INDEX IF NOT EXISTS "WebSiteCategoryID_Category_Index" ON "WebSiteCategoryID" ("Category");


CREATE TABLE IF NOT EXISTS "CrawledAddress" (
    "ID"            BIGSERIAL PRIMARY KEY,
    "Protocol"      VARCHAR(10) NOT NULL,
    "BaseDomainID"  BIGINT NOT NULL,
    "BaseUrlPathID" BIGINT DEFAULT NULL, 
    "BaseUrlEtcID"  BIGINT DEFAULT NULL,   
    "FirstCrawlDate"     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "LastCrawlDate"      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "CrawledAddress_Protocol_Index" ON "CrawledAddress" ("Protocol");
CREATE INDEX IF NOT EXISTS "CrawledAddress_BaseDomainID_Index" ON "CrawledAddress" ("BaseDomainID");
CREATE INDEX IF NOT EXISTS "CrawledAddress_BaseUrlPathID_Index" ON "CrawledAddress" ("BaseUrlPathID");
CREATE INDEX IF NOT EXISTS "CrawledAddress_BaseUrlEtcID_Index" ON "CrawledAddress" ("BaseUrlEtcID");
CREATE INDEX IF NOT EXISTS "CrawledAddress_FirstCrawlDate_Index" ON "CrawledAddress" ("FirstCrawlDate");
CREATE INDEX IF NOT EXISTS "CrawledAddress_LastCrawlDate_Index" ON "CrawledAddress" ("LastCrawlDate");

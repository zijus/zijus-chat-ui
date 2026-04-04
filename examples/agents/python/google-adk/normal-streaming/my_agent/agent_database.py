from google.adk.agents import LlmAgent
from db_tool import query_postgres
import os
from datetime import datetime, timezone

DB_SCHEMA = """
CREATE TABLE landlords (
    landlord_id SERIAL PRIMARY KEY,
    reference_code VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    address TEXT,
    phone_mobile VARCHAR(50),
    phone_home VARCHAR(50),
    phone_work VARCHAR(50),
    email VARCHAR(255),
    id_document_1 VARCHAR(255),
    id_document_2 VARCHAR(255),
    id_document_3 VARCHAR(255)
);

CREATE TABLE properties (
    property_id SERIAL PRIMARY KEY,
    property_ref VARCHAR(50) UNIQUE NOT NULL,
    landlord_ref VARCHAR(50) NOT NULL,
    property_address TEXT NOT NULL,
    property_type VARCHAR(150),
    tenure VARCHAR(50),
    key_number VARCHAR(50),

    gas_metre_number VARCHAR(100),
    gas_supplier TEXT,

    electric_metre_number VARCHAR(100),
    electric_supplier TEXT,

    water_metre_number VARCHAR(100),
    water_supplier TEXT,

    management_commission_rate DECIMAL(5,2),
    rent_agreed DECIMAL(10,2),
    contract_type VARCHAR(150),
    council_tax_office TEXT,
    special_notes TEXT,

    CONSTRAINT fk_landlord
        FOREIGN KEY (landlord_ref)
        REFERENCES landlords(reference_code)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE tenancies (
    tenancy_id SERIAL PRIMARY KEY,
    property_ref VARCHAR(50) NOT NULL,

    tenancy_start_date DATE,
    tenancy_end_date DATE,
    tenancy_period VARCHAR(100),

    electric_metre_reading VARCHAR(50),
    gas_metre_reading VARCHAR(50),
    water_metre_reading VARCHAR(50),

    tenancy_rent DECIMAL(10,2),
    tenancy_deposit DECIMAL(10,2),
    tenancy_deposit_number VARCHAR(100),

    tenancy_first_movein_date DATE,
    tenancy_last_rentreview_date DATE,
    tenancy_last_rent_increase DECIMAL(10,2),

    -- Tenant 1
    tenant_1_name VARCHAR(255),
    tenant_1_address TEXT,
    tenant_1_mobile_number VARCHAR(50),
    tenant_1_home_telephone VARCHAR(50),
    tenant_1_work_telephone VARCHAR(50),
    tenant_1_email VARCHAR(255),
    tenant_1_id_doc1 VARCHAR(255),
    tenant_1_id_doc2 VARCHAR(255),
    tenant_1_immigration_status VARCHAR(100),

    -- Tenant 2
    tenant_2_name VARCHAR(255),
    tenant_2_address TEXT,
    tenant_2_mobile_number VARCHAR(50),
    tenant_2_home_telephone VARCHAR(50),
    tenant_2_work_telephone VARCHAR(50),
    tenant_2_email VARCHAR(255),
    tenant_2_id_doc1 VARCHAR(255),
    tenant_2_id_doc2 VARCHAR(255),
    tenant_2_immigration_status VARCHAR(100),

    CONSTRAINT fk_property
        FOREIGN KEY (property_ref)
        REFERENCES properties(property_ref)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE TABLE compliance_certificates (
    cert_id SERIAL PRIMARY KEY,
    property_ref VARCHAR(50) NOT NULL,
    cert_type VARCHAR(100),
    provider_name VARCHAR(255),
    start_date DATE,
    expiry_date DATE,

    CONSTRAINT fk_property_compliance
        FOREIGN KEY (property_ref)
        REFERENCES properties(property_ref)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);
"""

agent = LlmAgent(
    name="root_agent",
    model="gemini-2.5-flash",
    description="An AI Assistant for Cpaital Lettings, built by Zijus",
    instruction=f"""
You are an AI assistant with access to a database.

DATABASE RULES:
- You may ONLY generate SELECT and UPDATE queries
- Use the schema exactly as defined below
- If unsure, ask a clarifying question

DATABASE SCHEMA:
{DB_SCHEMA}

Today is {datetime.now(timezone.utc).date().isoformat()}
""",
    tools=[query_postgres],
)

root_agent = agent

-- Rare Disease Federated Detection — Initial Database Migration
-- Run against Neon Postgres with pgvector extension enabled

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Per-hospital local tables (one per hospital, identical schema)
-- ============================================================

CREATE TABLE IF NOT EXISTS hospital_tvm_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_ref_id TEXT NOT NULL,
    raw_symptom_text TEXT NOT NULL,
    hpo_terms JSONB,
    embedding VECTOR(384),
    is_unique BOOLEAN DEFAULT NULL,
    pushed_to_global BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hospital_kochi_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_ref_id TEXT NOT NULL,
    raw_symptom_text TEXT NOT NULL,
    hpo_terms JSONB,
    embedding VECTOR(384),
    is_unique BOOLEAN DEFAULT NULL,
    pushed_to_global BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hospital_kzk_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_ref_id TEXT NOT NULL,
    raw_symptom_text TEXT NOT NULL,
    hpo_terms JSONB,
    embedding VECTOR(384),
    is_unique BOOLEAN DEFAULT NULL,
    pushed_to_global BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT now()
);

-- ============================================================
-- Global cases table (receives pushed unique cases)
-- ============================================================

CREATE TABLE IF NOT EXISTS global_cases (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id TEXT NOT NULL,
    patient_ref_id TEXT NOT NULL,
    hpo_terms JSONB,
    embedding VECTOR(384),
    disease_candidate_label TEXT,
    region TEXT NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    privacy_epsilon_used FLOAT DEFAULT 5.0,
    confidence_score FLOAT,
    created_at TIMESTAMP DEFAULT now()
);

-- pgvector cosine similarity index
CREATE INDEX IF NOT EXISTS idx_global_cases_embedding
    ON global_cases USING ivfflat (embedding vector_cosine_ops);

-- ============================================================
-- Hospital directory table
-- ============================================================

CREATE TABLE IF NOT EXISTS hospitals (
    hospital_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    contact_email TEXT,
    contact_phone TEXT
);

-- Seed the 3 demo hospitals (upsert to be idempotent)
INSERT INTO hospitals (hospital_id, name, region, latitude, longitude, contact_email, contact_phone)
VALUES
    ('HOSP_TVM_01', 'General Hospital Thiruvananthapuram', 'Thiruvananthapuram, Kerala', 8.5241, 76.9366, 'contact@gh-tvm.demo', '+91-471-000-0001'),
    ('HOSP_KCH_01', 'Kochi Medical Center', 'Kochi, Kerala', 9.9312, 76.2673, 'contact@kmc.demo', '+91-484-000-0002'),
    ('HOSP_KZK_01', 'Kozhikode Care Hospital', 'Kozhikode, Kerala', 11.2588, 75.7804, 'contact@kzk-care.demo', '+91-495-000-0003')
ON CONFLICT (hospital_id) DO NOTHING;

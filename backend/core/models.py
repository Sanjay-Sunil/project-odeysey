"""
Models for Rare Disease Federated Detection MVP.

Note: We use raw SQL for most DB operations because the tables use pgvector
VECTOR columns which Django ORM doesn't natively support. These model
definitions exist primarily for Django's app registry and documentation.
The actual table creation is handled by migrations/001_initial.sql.
"""
from django.db import models


# These are documentation-only model stubs.
# All actual DB operations use raw SQL via django.db.connection
# because pgvector VECTOR(384) columns aren't natively supported by Django ORM.

# Table: hospital_tvm_cases / hospital_kochi_cases / hospital_kzk_cases
# Columns: id (UUID PK), patient_ref_id (TEXT), raw_symptom_text (TEXT),
#           hpo_terms (JSONB), embedding (VECTOR(384)), is_unique (BOOLEAN),
#           pushed_to_global (BOOLEAN), created_at (TIMESTAMP)

# Table: global_cases
# Columns: case_id (UUID PK), hospital_id (TEXT), patient_ref_id (TEXT),
#           hpo_terms (JSONB), embedding (VECTOR(384)), disease_candidate_label (TEXT),
#           region (TEXT), latitude (FLOAT), longitude (FLOAT),
#           privacy_epsilon_used (FLOAT), confidence_score (FLOAT),
#           created_at (TIMESTAMP)

# Table: hospitals
# Columns: hospital_id (TEXT PK), name (TEXT), region (TEXT),
#           latitude (FLOAT), longitude (FLOAT), contact_email (TEXT),
#           contact_phone (TEXT)

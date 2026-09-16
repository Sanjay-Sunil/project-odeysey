#!/usr/bin/env python
"""
Synthetic Data Generation & Seeding Script (Module 2).

Populates global_cases with 30 synthetic, HPO-annotated rare disease case records.
Idempotent: truncates and reseeds global_cases on each run.

Usage:
    cd backend
    python seed_global_db.py

Requires: DATABASE_URL, LLM_PROVIDER, GROQ_API_KEY or GEMINI_API_KEY in .env
"""
import os
import sys
import json
import random
import time

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.db import connection
from core.agent_utils import extract_hpo, get_embedding, _llm_chat

# ============================================================
# 10 rare diseases with associated HPO terms for seed generation
# ============================================================

RARE_DISEASES = [
    {
        "name": "Fabry Disease",
        "hpo_hint": "angiokeratoma, acroparesthesia, cornea verticillata, renal insufficiency, cardiomyopathy",
    },
    {
        "name": "Ehlers-Danlos Syndrome",
        "hpo_hint": "joint hypermobility, skin hyperextensibility, easy bruising, chronic pain, mitral valve prolapse",
    },
    {
        "name": "Wilson's Disease",
        "hpo_hint": "Kayser-Fleischer rings, hepatomegaly, tremor, dysarthria, psychiatric symptoms",
    },
    {
        "name": "Gaucher Disease",
        "hpo_hint": "splenomegaly, hepatomegaly, bone pain, anemia, thrombocytopenia",
    },
    {
        "name": "Marfan Syndrome",
        "hpo_hint": "tall stature, arachnodactyly, lens subluxation, aortic root dilation, scoliosis",
    },
    {
        "name": "Huntington Disease",
        "hpo_hint": "chorea, cognitive decline, psychiatric disturbance, dystonia, weight loss",
    },
    {
        "name": "Phenylketonuria",
        "hpo_hint": "intellectual disability, seizures, musty body odor, fair skin, eczema",
    },
    {
        "name": "Myasthenia Gravis",
        "hpo_hint": "ptosis, diplopia, muscle weakness, fatigue, dysphagia",
    },
    {
        "name": "Pompe Disease",
        "hpo_hint": "progressive muscle weakness, respiratory insufficiency, cardiomegaly, hypotonia, feeding difficulties",
    },
    {
        "name": "Cystic Fibrosis",
        "hpo_hint": "recurrent pulmonary infections, pancreatic insufficiency, bronchiectasis, failure to thrive, salty sweat",
    },
]

# Hospital assignments (exact coordinates from hospitals table — NEVER randomize per AGENT.md)
HOSPITALS = [
    {"id": "HOSP_TVM_01", "region": "Thiruvananthapuram, Kerala", "lat": 8.5241, "lng": 76.9366},
    {"id": "HOSP_KCH_01", "region": "Kochi, Kerala", "lat": 9.9312, "lng": 76.2673},
    {"id": "HOSP_KZK_01", "region": "Kozhikode, Kerala", "lat": 11.2588, "lng": 75.7804},
]


def generate_vignette(disease_name: str, hpo_hint: str, vignette_num: int) -> str:
    """Generate a synthetic patient vignette using LLM."""
    system_prompt = (
        "You are a medical case writer creating synthetic patient vignettes for a rare disease database. "
        "Generate a realistic but fully fictional short clinical vignette (2-4 sentences) describing a patient "
        "presenting with symptoms consistent with the given disease. Vary the presentation between vignettes. "
        "Write ONLY the vignette text — no headers, no labels, no explanations."
    )
    user_prompt = (
        f"Disease: {disease_name}\n"
        f"Key features to include (pick 3-5): {hpo_hint}\n"
        f"Vignette variation: #{vignette_num} of 3 — make it distinct from other vignettes for this disease."
    )
    return _llm_chat(system_prompt, user_prompt)


def seed_global_db():
    """Main seeding function. Truncates global_cases and inserts 30 synthetic records."""
    print("=" * 60)
    print("Rare Disease Federated Detection — Seed Script")
    print("=" * 60)

    # Truncate global_cases (idempotent re-run)
    print("\n[1/3] Truncating global_cases table...")
    with connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE global_cases")
    print("      Done.")

    # Generate and insert 30 records (10 diseases × 3 vignettes)
    print(f"\n[2/3] Generating 30 synthetic vignettes...")
    total = len(RARE_DISEASES) * 3
    count = 0

    for disease in RARE_DISEASES:
        for vignette_num in range(1, 4):
            count += 1
            hospital = random.choice(HOSPITALS)

            print(f"\n  Generating vignette {count}/{total}: {disease['name']} (#{vignette_num})...")

            # Generate vignette text
            try:
                vignette = generate_vignette(disease['name'], disease['hpo_hint'], vignette_num)
                print(f"    Vignette: {vignette[:80]}...")
            except Exception as e:
                print(f"    ERROR generating vignette: {e}")
                continue

            # Extract HPO terms from the vignette
            try:
                hpo_terms = extract_hpo(vignette)
                print(f"    HPO terms: {[t['label'] for t in hpo_terms[:3]]}...")
            except Exception as e:
                print(f"    ERROR extracting HPO: {e}")
                # Fallback: create basic HPO terms from the hint
                hpo_terms = [{"id": f"HP:000{i}", "label": kw.strip()}
                             for i, kw in enumerate(disease['hpo_hint'].split(',')[:3])]

            # Generate embedding
            try:
                embedding = get_embedding(hpo_terms)
                print(f"    Embedding: [{embedding[0]:.4f}, {embedding[1]:.4f}, ...] ({len(embedding)} dims)")
            except Exception as e:
                print(f"    ERROR generating embedding: {e}")
                embedding = [0.0] * 384

            # Build patient ref ID
            patient_ref_id = f"SEED-{disease['name'][:3].upper()}-{vignette_num:02d}"

            # Insert into global_cases
            hpo_json = json.dumps(hpo_terms)
            embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO global_cases
                            (hospital_id, patient_ref_id, hpo_terms, embedding,
                             disease_candidate_label, region, latitude, longitude,
                             privacy_epsilon_used, confidence_score)
                        VALUES
                            (%s, %s, %s::jsonb, %s::vector, %s, %s, %s, %s, %s, %s)
                        """,
                        [
                            hospital['id'], patient_ref_id, hpo_json, embedding_str,
                            disease['name'], hospital['region'], hospital['lat'], hospital['lng'],
                            5.0, round(random.uniform(0.7, 0.95), 2),
                        ]
                    )
                print(f"    ✓ Inserted → {hospital['id']} ({hospital['region']})")
            except Exception as e:
                print(f"    ERROR inserting: {e}")

            # Small delay to avoid rate limiting
            time.sleep(0.5)

    # Verify
    print(f"\n[3/3] Verifying seed data...")
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM global_cases")
        count = cursor.fetchone()[0]
        cursor.execute("SELECT DISTINCT disease_candidate_label FROM global_cases ORDER BY disease_candidate_label")
        diseases = [row[0] for row in cursor.fetchall()]

    print(f"      Total records in global_cases: {count}")
    print(f"      Diseases represented: {', '.join(diseases)}")
    print(f"\n{'=' * 60}")
    print("Seeding complete!")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    seed_global_db()

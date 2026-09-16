"""
API views for Rare Disease Federated Detection MVP.

Endpoints:
    POST /agent          — Hospital agent: HPO extract → uniqueness → embed → save → conditional push
    POST /push           — Internal: validate privacy → insert into global_cases
    POST /refer          — RAG search: HPO extract → embed → pgvector top-5 → join hospitals
    POST /heatmap-search — Heatmap: keywords → HPO → embed → pgvector top-20 → cluster

All endpoints use shared functions from agent_utils.py — never duplicated here.
See AGENT.md §5 for the API contract.
"""
import json
import uuid
import logging
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import connection
from django.conf import settings

from .agent_utils import extract_hpo, judge_uniqueness, get_embedding

logger = logging.getLogger(__name__)

# Privacy-disallowed field names (for /push validation)
DISALLOWED_FIELDS = {
    'patient_name', 'name', 'first_name', 'last_name', 'full_name',
    'dob', 'date_of_birth', 'birth_date', 'birthday',
    'address', 'street', 'city', 'zip', 'postal_code',
    'symptom_text', 'raw_symptom_text', 'raw_text', 'notes',
    'ssn', 'social_security', 'insurance_id', 'phone', 'email',
}

# Cluster color palette for heatmap (muted accents — per AGENT.md,
# map markers are the one exception to the B&W theme)
CLUSTER_COLORS = [
    '#4A6FA5',  # muted blue
    '#B5651D',  # amber/brown
    '#2D8B7A',  # teal
    '#8B2252',  # maroon
    '#6B5B95',  # muted purple
    '#5B8C5A',  # sage green
    '#C4A35A',  # gold
    '#7B8D8E',  # slate
]


def _parse_json_body(request):
    """Parse JSON from request body."""
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError) as e:
        return None


# ============================================================
# POST /agent — Hospital Agent Endpoint (Module 3)
# ============================================================

@csrf_exempt
@require_POST
def agent_endpoint(request):
    """
    Hospital agent endpoint. Runs 3 sequential LLM-powered tool steps:
    1. HPO Mapping — extract HPO terms from symptom text
    2. Uniqueness Judgment — is this phenotype combination rare for this hospital?
    3. Embedding + Conditional Push — embed, save locally, push to global if unique

    Input: { hospital_id, patient_ref_id, symptom_text }
    Output: { hpo_terms, is_unique, reasoning, pushed_to_global }
    """
    body = _parse_json_body(request)
    if body is None:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    hospital_id = body.get('hospital_id', '').strip()
    patient_ref_id = body.get('patient_ref_id', '').strip()
    symptom_text = body.get('symptom_text', '').strip()

    if not all([hospital_id, patient_ref_id, symptom_text]):
        return JsonResponse(
            {'error': 'Missing required fields: hospital_id, patient_ref_id, symptom_text'},
            status=400
        )

    table_name = settings.HOSPITAL_TABLE_MAP.get(hospital_id)
    if not table_name:
        return JsonResponse(
            {'error': f'Unknown hospital_id: {hospital_id}'},
            status=400
        )

    # Tool 1 — HPO Mapping
    logger.info(f"[Agent] Tool 1: Extracting HPO terms for {patient_ref_id} at {hospital_id}")
    hpo_terms = extract_hpo(symptom_text)
    if not hpo_terms:
        return JsonResponse(
            {'error': 'Failed to extract HPO terms from symptom text'},
            status=500
        )

    # Tool 2 — Uniqueness Judgment
    logger.info(f"[Agent] Tool 2: Judging uniqueness for {patient_ref_id}")
    uniqueness = judge_uniqueness(hpo_terms, hospital_id)
    is_unique = uniqueness.get('is_unique', False)
    reasoning = uniqueness.get('reasoning', '')

    # Tool 3 — Embedding + Save + Conditional Push
    logger.info(f"[Agent] Tool 3: Generating embedding for {patient_ref_id}")
    embedding = get_embedding(hpo_terms)

    # Always save to local hospital table
    hpo_json = json.dumps(hpo_terms)
    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {table_name}
                    (patient_ref_id, raw_symptom_text, hpo_terms, embedding, is_unique, pushed_to_global)
                VALUES
                    (%s, %s, %s::jsonb, %s::vector, %s, %s)
                """,
                [patient_ref_id, symptom_text, hpo_json, embedding_str, is_unique, False]
            )
    except Exception as e:
        logger.error(f"Failed to save to {table_name}: {e}")
        return JsonResponse({'error': f'Database error: {str(e)}'}, status=500)

    # If unique, push to global DB via /push endpoint
    pushed_to_global = False
    if is_unique:
        logger.info(f"[Agent] Case is unique — pushing to global DB for {patient_ref_id}")
        try:
            push_payload = {
                'hospital_id': hospital_id,
                'patient_ref_id': patient_ref_id,
                'hpo_terms': hpo_terms,
                'embedding': embedding,
                'confidence_score': 0.87,  # placeholder for demo
                'privacy_epsilon_used': 5.0,  # cosmetic per AGENT.md
            }
            # Call push internally (direct function call instead of HTTP for reliability)
            push_result = _push_to_global(push_payload)
            if push_result.get('status') == 'pushed':
                pushed_to_global = True
                # Update the local record
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {table_name} SET pushed_to_global = TRUE "
                        f"WHERE patient_ref_id = %s",
                        [patient_ref_id]
                    )
        except Exception as e:
            logger.error(f"Push to global failed: {e}")
            # Don't fail the whole request — the local save succeeded

    return JsonResponse({
        'hpo_terms': hpo_terms,
        'is_unique': is_unique,
        'reasoning': reasoning,
        'pushed_to_global': pushed_to_global,
    })


# ============================================================
# POST /push — Internal Push Endpoint (Module 4)
# ============================================================

def _push_to_global(data: dict) -> dict:
    """
    Internal push function. Validates privacy, inserts into global_cases.
    Can be called directly by /agent or via the /push HTTP endpoint.
    """
    # Validate: reject disallowed fields (privacy boundary)
    for field in data.keys():
        if field.lower() in DISALLOWED_FIELDS:
            raise ValueError(f"Disallowed field detected: '{field}'. "
                           f"Privacy violation — raw patient data must never reach global DB.")

    hospital_id = data.get('hospital_id')
    patient_ref_id = data.get('patient_ref_id')
    hpo_terms = data.get('hpo_terms')
    embedding = data.get('embedding')
    confidence_score = data.get('confidence_score')
    privacy_epsilon = data.get('privacy_epsilon_used', 5.0)

    if not all([hospital_id, patient_ref_id, hpo_terms, embedding]):
        raise ValueError("Missing required fields for push")

    # Look up hospital region + coordinates
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT region, latitude, longitude FROM hospitals WHERE hospital_id = %s",
            [hospital_id]
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Hospital not found: {hospital_id}")

        region, latitude, longitude = row

    # Insert into global_cases
    hpo_json = json.dumps(hpo_terms)
    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
    case_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO global_cases
                (case_id, hospital_id, patient_ref_id, hpo_terms, embedding,
                 region, latitude, longitude, privacy_epsilon_used, confidence_score)
            VALUES
                (%s, %s, %s, %s::jsonb, %s::vector, %s, %s, %s, %s, %s)
            """,
            [case_id, hospital_id, patient_ref_id, hpo_json, embedding_str,
             region, latitude, longitude, privacy_epsilon, confidence_score]
        )

    return {'status': 'pushed', 'case_id': case_id}


@csrf_exempt
@require_POST
def push_endpoint(request):
    """
    HTTP endpoint for /push (Module 4).
    Called internally by /agent — not exposed to end users directly,
    but kept as a real HTTP endpoint for architectural clarity/demo narrative.

    Input: { hospital_id, patient_ref_id, hpo_terms, embedding, confidence_score, privacy_epsilon_used }
    Output: { status: "pushed", case_id: "<uuid>" }
    """
    body = _parse_json_body(request)
    if body is None:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    # Check for disallowed fields (privacy boundary — must be demoable/visible)
    for field in body.keys():
        if field.lower() in DISALLOWED_FIELDS:
            return JsonResponse(
                {'error': f"Privacy violation: field '{field}' is not allowed. "
                         f"No patient-identifiable data or raw symptom text may be pushed to the global DB."},
                status=400
            )

    try:
        result = _push_to_global(body)
        return JsonResponse(result)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Push endpoint error: {e}")
        return JsonResponse({'error': f'Internal error: {str(e)}'}, status=500)


# ============================================================
# POST /refer — RAG Search Endpoint (Module 6)
# ============================================================

@csrf_exempt
@require_POST
def refer_endpoint(request):
    """
    RAG search endpoint. Finds similar cases in the global registry.

    1. Extract HPO terms from query text (reuses extract_hpo)
    2. Generate embedding (reuses get_embedding)
    3. pgvector cosine similarity top-5 against global_cases
    4. Join hospitals table for contact info
    5. Return human-readable symptom names

    Input: { query_text }
    Output: { results: [{ symptoms, similarity_score, hospital_name, region, contact_email, contact_phone }] }
    """
    body = _parse_json_body(request)
    if body is None:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    query_text = body.get('query_text', '').strip()
    if not query_text:
        return JsonResponse({'error': 'Missing required field: query_text'}, status=400)

    # Step 1: Extract HPO terms
    logger.info(f"[Refer] Extracting HPO terms from query")
    hpo_terms = extract_hpo(query_text)
    if not hpo_terms:
        return JsonResponse({'error': 'Failed to extract HPO terms from query'}, status=500)

    # Step 2: Generate embedding
    logger.info(f"[Refer] Generating embedding")
    embedding = get_embedding(hpo_terms)
    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

    # Step 3 + 4: pgvector cosine similarity search + join hospitals
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    gc.hpo_terms,
                    1 - (gc.embedding <=> %s::vector) as similarity_score,
                    h.name as hospital_name,
                    h.region,
                    h.contact_email,
                    h.contact_phone
                FROM global_cases gc
                JOIN hospitals h ON gc.hospital_id = h.hospital_id
                ORDER BY gc.embedding <=> %s::vector ASC
                LIMIT 5
                """,
                [embedding_str, embedding_str]
            )
            rows = cursor.fetchall()
    except Exception as e:
        logger.error(f"Refer search failed: {e}")
        return JsonResponse({'error': f'Search error: {str(e)}'}, status=500)

    # Step 5: Build results with human-readable symptom names
    results = []
    for row in rows:
        hpo_data = row[0]  # JSONB
        similarity = round(float(row[1]), 4) if row[1] else 0.0
        hospital_name = row[2]
        region = row[3]
        contact_email = row[4]
        contact_phone = row[5]

        # Extract human-readable labels from HPO terms JSONB
        symptoms = []
        if isinstance(hpo_data, list):
            symptoms = [term.get('label', term.get('id', 'Unknown')) for term in hpo_data]
        elif isinstance(hpo_data, str):
            try:
                parsed = json.loads(hpo_data)
                symptoms = [term.get('label', term.get('id', 'Unknown')) for term in parsed]
            except json.JSONDecodeError:
                symptoms = ['Unable to parse symptoms']

        results.append({
            'symptoms': symptoms,
            'similarity_score': similarity,
            'hospital_name': hospital_name,
            'region': region,
            'contact_email': contact_email,
            'contact_phone': contact_phone,
        })

    return JsonResponse({'results': results})


# ============================================================
# POST /heatmap-search — Heatmap Search Endpoint (Module 8)
# ============================================================

@csrf_exempt
@require_POST
def heatmap_search_endpoint(request):
    """
    Heatmap search endpoint. Finds and clusters matching cases by symptom keywords.

    1. Extract HPO terms from all keywords (batched)
    2. Generate combined embedding
    3. pgvector cosine similarity top-20
    4. Cluster results by disease_candidate_label or proximity
    5. Assign cluster colors and return with lat/lng

    Input: { symptom_keywords: ["cough", "headache"] }
    Output: { clusters: [{ label, color, points: [{lat, lng, case_id}] }], top_matches_list: [...] }
    """
    body = _parse_json_body(request)
    if body is None:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    keywords = body.get('symptom_keywords', [])
    if not keywords or not isinstance(keywords, list):
        return JsonResponse(
            {'error': 'Missing or invalid field: symptom_keywords (must be a non-empty list)'},
            status=400
        )

    # Step 1: Extract HPO terms from all keywords (batched into one call)
    combined_text = ", ".join(keywords)
    logger.info(f"[Heatmap] Extracting HPO terms from keywords: {combined_text}")
    hpo_terms = extract_hpo(combined_text)
    if not hpo_terms:
        return JsonResponse({'error': 'Failed to extract HPO terms from keywords'}, status=500)

    # Step 2: Generate combined embedding
    logger.info(f"[Heatmap] Generating embedding for combined HPO terms")
    embedding = get_embedding(hpo_terms)
    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

    # Step 3: pgvector cosine similarity search
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    gc.case_id,
                    gc.hpo_terms,
                    gc.disease_candidate_label,
                    gc.latitude,
                    gc.longitude,
                    1 - (gc.embedding <=> %s::vector) as similarity_score,
                    h.name as hospital_name,
                    h.region
                FROM global_cases gc
                JOIN hospitals h ON gc.hospital_id = h.hospital_id
                WHERE 1 - (gc.embedding <=> %s::vector) > 0.1
                ORDER BY gc.embedding <=> %s::vector ASC
                LIMIT 20
                """,
                [embedding_str, embedding_str, embedding_str]
            )
            rows = cursor.fetchall()
    except Exception as e:
        logger.error(f"Heatmap search failed: {e}")
        return JsonResponse({'error': f'Search error: {str(e)}'}, status=500)

    # Step 4: Cluster by disease_candidate_label (or "Unknown" if null)
    clusters_dict = {}
    top_matches_list = []

    for row in rows:
        case_id = str(row[0])
        hpo_data = row[1]
        disease_label = row[2] or "Unknown phenotype cluster"
        lat = float(row[3])
        lng = float(row[4])
        similarity = round(float(row[5]), 4) if row[5] else 0.0
        hospital_name = row[6]
        region = row[7]

        # Build cluster key
        cluster_key = disease_label

        if cluster_key not in clusters_dict:
            clusters_dict[cluster_key] = {
                'label': f"Cluster — {cluster_key}",
                'points': [],
            }

        clusters_dict[cluster_key]['points'].append({
            'lat': lat,
            'lng': lng,
            'case_id': case_id,
        })

        # Build top matches list
        symptoms_summary = ""
        if isinstance(hpo_data, list):
            symptoms_summary = ", ".join(t.get('label', '') for t in hpo_data[:3])
        elif isinstance(hpo_data, str):
            try:
                parsed = json.loads(hpo_data)
                symptoms_summary = ", ".join(t.get('label', '') for t in parsed[:3])
            except json.JSONDecodeError:
                symptoms_summary = "Unknown symptoms"

        top_matches_list.append({
            'symptom_summary': symptoms_summary,
            'hospital_name': hospital_name,
            'region': region,
        })

    # Step 5: Assign colors to clusters
    clusters = []
    for idx, (key, cluster_data) in enumerate(clusters_dict.items()):
        color = CLUSTER_COLORS[idx % len(CLUSTER_COLORS)]
        clusters.append({
            'label': cluster_data['label'],
            'color': color,
            'points': cluster_data['points'],
        })

    return JsonResponse({
        'clusters': clusters,
        'top_matches_list': top_matches_list,
    })

"""
Shared utility functions for all endpoints.
This is the SINGLE source for HPO extraction, uniqueness judgment, and embedding generation.
Imported by /agent, /refer, and /heatmap-search — never duplicate this logic.

See AGENT.md §6 for the contract these functions must satisfy.
"""
import json
import os
import logging
from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

# ============================================================
# Lazy-loaded LLM clients
# ============================================================

_groq_client = None
_embedding_model = None


def _get_groq_client():
    """Lazy-init Groq client."""
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


def _get_embedding_model():
    """Lazy-init sentence-transformers model (all-MiniLM-L6-v2)."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Loaded all-MiniLM-L6-v2 embedding model")
    return _embedding_model


def _llm_chat(system_prompt: str, user_prompt: str) -> str:
    """
    Send a chat completion request to the configured LLM provider.
    Returns the raw text response.
    """
    provider = settings.LLM_PROVIDER

    if provider == 'groq':
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=2048,
        )
        return response.choices[0].message.content.strip()

    elif provider == 'gemini':
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            f"{system_prompt}\n\n{user_prompt}",
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
            ),
        )
        return response.text.strip()

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}. Use 'groq' or 'gemini'.")


def _parse_json_from_llm(text: str) -> any:
    """
    Extract JSON from LLM response, handling markdown code blocks.
    """
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith('```'):
        # Remove opening fence (possibly with language tag like ```json)
        first_newline = cleaned.index('\n')
        cleaned = cleaned[first_newline + 1:]
        # Remove closing fence
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3].strip()

    return json.loads(cleaned)


# ============================================================
# Core shared functions (AGENT.md §6)
# ============================================================

def extract_hpo(text: str) -> list[dict]:
    """
    Extract HPO terms from free-text symptom description using LLM.

    Args:
        text: Doctor's note or symptom description (natural language)

    Returns:
        List of dicts: [{"id": "HP:XXXXXXX", "label": "term name"}, ...]
    """
    system_prompt = (
        "You are a clinical NLP system. Extract Human Phenotype Ontology (HPO) terms "
        "from the following doctor's note. Return ONLY a JSON array of objects: "
        '[{"id": "HP:XXXXXXX", "label": "term name"}]. '
        "If you are not certain of the exact HPO code, provide your best estimate — "
        "do not return prose. Return at least 1 and at most 10 terms."
    )
    user_prompt = f'Doctor\'s note: "{text}"'

    try:
        response = _llm_chat(system_prompt, user_prompt)
        hpo_terms = _parse_json_from_llm(response)

        # Validate structure
        if not isinstance(hpo_terms, list):
            logger.error(f"HPO extraction returned non-list: {type(hpo_terms)}")
            return []

        validated = []
        for term in hpo_terms:
            if isinstance(term, dict) and 'id' in term and 'label' in term:
                validated.append({
                    'id': str(term['id']),
                    'label': str(term['label']),
                })
        return validated

    except Exception as e:
        logger.error(f"HPO extraction failed: {e}")
        return []


def judge_uniqueness(hpo_terms: list[dict], hospital_id: str) -> dict:
    """
    Ask the LLM to qualitatively judge whether a set of HPO terms represents
    a unique/rare phenotype combination relative to recent cases at the hospital.

    Per AGENT.md: This is a qualitative LLM judgment — no cosine-similarity
    threshold math is used for uniqueness.

    Args:
        hpo_terms: List of HPO term dicts [{"id": "...", "label": "..."}, ...]
        hospital_id: Hospital identifier to look up recent local cases

    Returns:
        Dict: {"is_unique": bool, "reasoning": "short reason"}
    """
    # Get the hospital's local table name
    table_name = settings.HOSPITAL_TABLE_MAP.get(hospital_id)
    if not table_name:
        logger.error(f"Unknown hospital_id: {hospital_id}")
        return {"is_unique": True, "reasoning": "Unknown hospital — treating as unique by default."}

    # Fetch last ~20 cases' HPO terms from the hospital's local table
    existing_cases_hpo = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT hpo_terms FROM {table_name} "
                f"WHERE hpo_terms IS NOT NULL "
                f"ORDER BY created_at DESC LIMIT 20"
            )
            rows = cursor.fetchall()
            for row in rows:
                if row[0]:
                    existing_cases_hpo.append(row[0])
    except Exception as e:
        logger.error(f"Failed to fetch existing cases from {table_name}: {e}")

    # Build context for the LLM
    if existing_cases_hpo:
        existing_summary = json.dumps(existing_cases_hpo, indent=2)
    else:
        existing_summary = "No existing cases found at this hospital."

    new_case_terms = json.dumps(hpo_terms, indent=2)

    system_prompt = (
        "You are a clinical decision support system. You are given a new patient's HPO "
        "(Human Phenotype Ontology) terms and the HPO terms from the last ~20 patients "
        "at the same hospital. Judge whether this new patient's phenotype combination is "
        "unique or rare relative to what has been seen recently at this hospital.\n\n"
        'Return ONLY a JSON object: {"is_unique": true/false, "reasoning": "short reason"}.\n'
        "A case is unique if its combination of HPO terms is significantly different from "
        "what has been seen before. Common presentations should be marked as NOT unique."
    )

    user_prompt = (
        f"New patient's HPO terms:\n{new_case_terms}\n\n"
        f"Recent cases at this hospital:\n{existing_summary}"
    )

    try:
        response = _llm_chat(system_prompt, user_prompt)
        result = _parse_json_from_llm(response)

        if isinstance(result, dict) and 'is_unique' in result:
            return {
                'is_unique': bool(result['is_unique']),
                'reasoning': str(result.get('reasoning', 'No reasoning provided.')),
            }
        else:
            logger.error(f"Uniqueness judgment returned unexpected structure: {result}")
            return {"is_unique": True, "reasoning": "Could not parse LLM judgment — defaulting to unique."}

    except Exception as e:
        logger.error(f"Uniqueness judgment failed: {e}")
        return {"is_unique": True, "reasoning": f"LLM judgment error — defaulting to unique. Error: {str(e)}"}


def get_embedding(hpo_terms: list[dict]) -> list[float]:
    """
    Generate a 384-dimensional embedding vector from a list of HPO terms.

    Uses all-MiniLM-L6-v2 locally by default, falls back to Gemini embedding API
    if EMBEDDING_PROVIDER=gemini. Per AGENT.md: NEVER route embeddings through Groq
    (it has no embedding endpoint).

    Args:
        hpo_terms: List of HPO term dicts [{"id": "...", "label": "..."}, ...]

    Returns:
        List of 384 floats (embedding vector)
    """
    # Build text representation of HPO terms for embedding
    text = ", ".join(term.get('label', term.get('id', '')) for term in hpo_terms)
    if not text:
        text = "unknown phenotype"

    provider = settings.EMBEDDING_PROVIDER

    if provider == 'local':
        model = _get_embedding_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    elif provider == 'gemini':
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        result = genai.embed_content(
            model="models/embedding-001",
            content=text,
            task_type="retrieval_document",
        )
        embedding = result['embedding']
        # Gemini embeddings are 768-dim by default; we need 384
        # Truncate or pad as needed (this is a fallback, not ideal)
        if len(embedding) > 384:
            embedding = embedding[:384]
        elif len(embedding) < 384:
            embedding = embedding + [0.0] * (384 - len(embedding))
        return embedding

    else:
        raise ValueError(f"Unknown EMBEDDING_PROVIDER: {provider}. Use 'local' or 'gemini'.")

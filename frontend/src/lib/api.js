/**
 * API utility — centralizes all backend calls.
 * Uses Vite's proxy in dev (/agent → localhost:8000/agent).
 */

const API_BASE = import.meta.env.VITE_API_BASE || '';

async function post(endpoint, body) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(error.error || `Request failed: ${res.status}`);
  }

  return res.json();
}

/**
 * POST /agent — Submit symptoms for HPO extraction + uniqueness judgment.
 */
export async function submitToAgent({ hospital_id, patient_ref_id, symptom_text }) {
  return post('/agent', { hospital_id, patient_ref_id, symptom_text });
}

/**
 * POST /refer — RAG search for similar cases.
 */
export async function searchSimilarCases({ query_text }) {
  return post('/refer', { query_text });
}

/**
 * POST /heatmap-search — Search by symptom keywords for map clusters.
 */
export async function searchHeatmap({ symptom_keywords }) {
  return post('/heatmap-search', { symptom_keywords });
}

# AGENT.md — Rare Disease Federated Detection MVP

This file is the single source of truth for this project. Any agent (Claude Code, Cursor, Copilot, etc.) picking up work on this codebase — whether continuing, fixing, or extending it — should read this file first before touching code. It captures decisions already made so they are never re-litigated or silently changed.

---

## 1. What This Project Is

A hackathon MVP that lets multiple hospitals detect rare/unique disease cases locally, contribute only privacy-safe signals (no raw symptoms, no patient identity) to a shared global registry, and lets clinicians/researchers query that registry two ways: a symptom heatmap and a natural-language case-similarity search.

**Non-negotiable core rule:** No patient-identifiable data or raw symptom text ever leaves a hospital's local system. Only `hospital_id`, `patient_ref_id` (a reference code, never a name), structured HPO terms, and embeddings cross into the global DB. Any endpoint accepting data from a hospital must validate against and reject disallowed fields (patient name, DOB, address, raw free text).

---

## 2. System Architecture

```
[Hospital A UI] --\
[Hospital B UI] ---> /agent (extract HPO -> judge uniqueness -> if unique) -> /push -> [Global DB: Neon Postgres + pgvector]
[Hospital C UI] --/                                                                          |
                                                                                              |
[Heatmap UI]    --(symptom tag keywords)--> /heatmap-search ------------------------------->|
[RAG Search UI] --(natural language query)--> /refer (extract HPO -> vector similarity -> retrieve top-k) -->|
```

- 3 hospitals simulated: each has its **own local DB table** (not a separate database instance — same Neon project, separate tables) AND its **own separate frontend UI deployment/route**.
- Heatmap and RAG Search are two more, fully separate, end-user-facing frontend apps — not part of any hospital's UI.
- `/agent` and `/refer` and `/heatmap-search` all share one backend utility module (`agent_utils.py`) for HPO extraction and embedding generation — never duplicate this logic.

---

## 3. Locked Tech Stack Decisions

Do not swap these without explicit instruction — they were chosen deliberately for hackathon time constraints:

| Layer | Choice | Why / Fallback |
|---|---|---|
| Backend | Django | Fixed |
| Database | Neon Postgres + `pgvector` extension | Fixed. Chosen over FAISS for reliability + zero extra infra during a hackathon |
| Frontend | React + Vite | Fixed |
| UI components | shadcn/ui | Fixed |
| UI theme | Minimalist, black/white/grey, accessible (ARIA labels, keyboard nav, visible focus states) | Map markers are the one exception — a small muted accent palette (blue/amber/teal/maroon) is allowed there since pure greyscale points are unreadable on a map |
| LLM (HPO extraction, uniqueness judgment) | Groq or Gemini — whichever is configured via `LLM_PROVIDER` env var | Provider must stay swappable in code, not hardcoded |
| Embeddings | `all-MiniLM-L6-v2` via `sentence-transformers`, run locally in the Django backend | Fallback: Gemini embedding API, if MiniLM setup is too slow to get working. Groq has **no** embedding endpoint — never route embeddings through Groq |
| Map | Leaflet (`react-leaflet`), tile layer CartoDB Positron, centered on Kerala (~lat 10.27, lng 76.4, zoom 7) | Fixed — demo scope is Kerala hospitals only |
| Deployment | Backend: Render/Railway/Fly.io (pick fastest free-tier). Frontends: Vercel/Netlify static builds, one deployment per hospital instance + heatmap + search | Flexible on exact host, fixed on the split (backend API + N static frontend builds) |
| Auth | None. Fully open, role-separated only by which UI/route is used | Do not add login flows — out of scope for this MVP |

---

## 4. Database Schema (Neon Postgres)

### Per-hospital local tables
One table per hospital: `hospital_tvm_cases`, `hospital_kochi_cases`, `hospital_kzk_cases`. Identical schema:

```sql
CREATE TABLE hospital_<name>_cases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_ref_id TEXT NOT NULL,
  raw_symptom_text TEXT NOT NULL,       -- stays LOCAL ONLY, never pushed
  hpo_terms JSONB,
  embedding VECTOR(384),
  is_unique BOOLEAN DEFAULT NULL,
  pushed_to_global BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT now()
);
```

### Global DB table
```sql
CREATE TABLE global_cases (
  case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  hospital_id TEXT NOT NULL,
  patient_ref_id TEXT NOT NULL,
  hpo_terms JSONB,
  embedding VECTOR(384),
  disease_candidate_label TEXT,          -- nullable, filled only post-diagnosis
  region TEXT NOT NULL,
  latitude FLOAT NOT NULL,
  longitude FLOAT NOT NULL,
  privacy_epsilon_used FLOAT DEFAULT 5.0, -- COSMETIC ONLY — no real differential privacy math is applied anywhere in this MVP. Do not imply otherwise in code comments or UI copy.
  confidence_score FLOAT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX ON global_cases USING ivfflat (embedding vector_cosine_ops);
```

### Hospital directory table
```sql
CREATE TABLE hospitals (
  hospital_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  region TEXT NOT NULL,
  latitude FLOAT NOT NULL,
  longitude FLOAT NOT NULL,
  contact_email TEXT,
  contact_phone TEXT
);
```

Seed values (fixed, do not change coordinates — heatmap demo depends on these exact points):

| hospital_id | name | region | lat | lng |
|---|---|---|---|---|
| HOSP_TVM_01 | General Hospital Thiruvananthapuram | Thiruvananthapuram, Kerala | 8.5241 | 76.9366 |
| HOSP_KCH_01 | Kochi Medical Center | Kochi, Kerala | 9.9312 | 76.2673 |
| HOSP_KZK_01 | Kozhikode Care Hospital | Kozhikode, Kerala | 11.2588 | 75.7804 |

---

## 5. API Endpoints (contract — do not change field names without updating all consumers)

### `POST /agent`
Called by a hospital's dashboard UI.
- In: `{ hospital_id, patient_ref_id, symptom_text }`
- Runs: extract_hpo() → judge_uniqueness() → get_embedding() → save to local hospital table → if unique, call `/push` internally
- Out: `{ hpo_terms, is_unique, reasoning, pushed_to_global }`

### `POST /push`
Called internally only by `/agent`, never exposed to a frontend directly.
- In: `{ hospital_id, patient_ref_id, hpo_terms, embedding, confidence_score, privacy_epsilon_used }`
- Validates: rejects (400) any field resembling patient name/DOB/address/raw text
- Out: `{ status: "pushed", case_id }`

### `POST /refer`
Called by the RAG Search UI.
- In: `{ query_text }`
- Runs: extract_hpo() → get_embedding() → pgvector cosine similarity top-5 → join `hospitals` table
- Out: `{ results: [ { symptoms, similarity_score, hospital_name, region, contact_email, contact_phone } ] }`

### `POST /heatmap-search`
Called by the Heatmap UI.
- In: `{ symptom_keywords: [...] }`
- Runs: extract_hpo() per keyword (batched) → get_embedding() → pgvector similarity top-20 → cluster by disease/proximity → assign cluster colors
- Out: `{ clusters: [ { label, color, points: [{lat, lng, case_id}] } ], top_matches_list: [...] }`

---

## 6. Shared Backend Module — `agent_utils.py`

Must contain exactly these functions, imported by `/agent`, `/refer`, and `/heatmap-search` — never duplicated inline in views:
- `extract_hpo(text: str) -> list[dict]` — LLM call, strict JSON-only output, `[{"id": "HP:XXXXXXX", "label": "..."}]`
- `judge_uniqueness(hpo_terms: list, hospital_id: str) -> dict` — LLM call comparing against last ~20 local cases at that hospital, returns `{"is_unique": bool, "reasoning": str}`. This is a qualitative LLM judgment — no cosine-similarity threshold math is used for uniqueness.
- `get_embedding(hpo_terms: list) -> list[float]` — `all-MiniLM-L6-v2` locally by default; Gemini embedding API if `EMBEDDING_PROVIDER=gemini`

---

## 7. Environment Variables

```
DATABASE_URL=            # Neon Postgres connection string
LLM_PROVIDER=            # "groq" or "gemini"
GROQ_API_KEY=
GEMINI_API_KEY=
EMBEDDING_PROVIDER=      # "local" (default) or "gemini"
```

---

## 8. Synthetic Seed Data

`seed_global_db.py` populates `global_cases` with 30 synthetic HPO-annotated vignettes across ~10 rare diseases (e.g. Fabry Disease, Ehlers-Danlos Syndrome, Wilson's Disease, Gaucher Disease, Marfan Syndrome), 3 vignettes each, LLM-generated, randomly assigned to one of the 3 seeded hospitals using that hospital's **exact** lat/long (never randomized coordinates). Script is idempotent — truncates and reseeds `global_cases` on each run. Run this once before any live demo.

---

## 9. Build Order (dependencies)

1. DB schema + hospitals seed table
2. Synthetic data seeding script
3. `/agent` backend (+ shared `agent_utils.py`)
4. `/push` backend
5. Hospital dashboard frontend (×3 instances)
6. `/refer` backend
7. RAG Search frontend
8. `/heatmap-search` backend
9. Heatmap frontend
10. Integration, env config, deployment

Full detailed module-by-module build prompts live in `rare-disease-mvp-build-prompt.md` in this same project — read that alongside this file when implementing any module.

---

## 10. Things Any Agent Must NOT Do

- Do not add real differential privacy math to `privacy_epsilon_used` — it is a demo-only cosmetic field.
- Do not add authentication/login flows.
- Do not route embeddings through Groq (it has no embedding endpoint).
- Do not merge the 3 hospital tables into one shared table — they must stay separate per hospital.
- Do not let any raw symptom text, patient name, or address reach the `global_cases` table or any `/push` payload.
- Do not build a 5th "mystery patient diagnosis" flow — this is already covered by `/refer` (RAG search doubles as the live diagnostic-query flow).
- Do not change the 3 hospital coordinates — the heatmap demo narrative depends on cases clustering at these exact points.
- Do not introduce a component library other than shadcn/ui, or break the black/white/grey theme (except map marker colors).

---

*Keep this file updated if any decision above changes mid-build — it is the contract between whichever agents touch this codebase.*

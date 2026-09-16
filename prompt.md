# Rare Disease Federated Detection — Hackathon MVP Build Prompt

**How to use this doc:** Build modules in the order listed — each depends on the one before it. Each module is written as a self-contained prompt you can hand to a coding agent. Integration notes at the end of each module tell you what the next module expects from it.

---

## Architecture Summary (read first)

```
[Hospital A UI] --\
[Hospital B UI] ---> /agent (HPO extract -> uniqueness judge -> if unique) -> /push -> [Global DB: Neon Postgres + pgvector]
[Hospital C UI] --/                                                                          |
                                                                                              |
[Heatmap UI]  --(symptom tags)--> /heatmap-search -----------------------------------------> |
[RAG Search UI] --(natural language)--> /refer (HPO extract -> vector similarity -> retrieve top-k) -> |
```

- **No patient-identifiable data ever leaves a hospital.** Only `hospital_id`, `patient_ref_id` (a reference code, not name), embeddings, and coarse region data are pushed to the global DB.
- Each hospital has its **own separate table** in the same Neon DB, but its **own separate frontend UI instance** (simulating 3 independent hospitals).
- Theme: shadcn/ui, minimalist, black/white/grey palette, accessible (proper contrast, keyboard nav, ARIA labels).

---

## MODULE 1 — Database Schema & Setup (Neon Postgres + pgvector)

**Prompt:**

> Set up a Neon Postgres database with the `pgvector` extension enabled. Create the following tables:
>
> **1. Per-hospital local tables** (create 3 identical tables, one per hospital: `hospital_tvm_cases`, `hospital_kochi_cases`, `hospital_kzk_cases`):
> ```sql
> CREATE TABLE hospital_<name>_cases (
>   id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>   patient_ref_id TEXT NOT NULL,        -- internal reference code only, never a real name
>   raw_symptom_text TEXT NOT NULL,
>   hpo_terms JSONB,                     -- list of {id, label} extracted by LLM
>   embedding VECTOR(384),               -- 384-dim if using all-MiniLM-L6-v2, adjust if using Gemini embeddings
>   is_unique BOOLEAN DEFAULT NULL,
>   pushed_to_global BOOLEAN DEFAULT FALSE,
>   created_at TIMESTAMP DEFAULT now()
> );
> ```
>
> **2. Global DB table:**
> ```sql
> CREATE TABLE global_cases (
>   case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>   hospital_id TEXT NOT NULL,           -- e.g. "HOSP_TVM_01"
>   patient_ref_id TEXT NOT NULL,        -- reference code, not identity
>   hpo_terms JSONB,
>   embedding VECTOR(384),
>   disease_candidate_label TEXT,        -- optional, filled post-diagnosis
>   region TEXT NOT NULL,                -- e.g. "Thiruvananthapuram, Kerala"
>   latitude FLOAT NOT NULL,
>   longitude FLOAT NOT NULL,
>   privacy_epsilon_used FLOAT DEFAULT 5.0,  -- cosmetic field for demo, no real DP math applied
>   confidence_score FLOAT,
>   created_at TIMESTAMP DEFAULT now()
> );
>
> CREATE INDEX ON global_cases USING ivfflat (embedding vector_cosine_ops);
> ```
>
> **3. Seed 3 fake hospital records** (for the "hospital directory" used by RAG search results):
> ```sql
> CREATE TABLE hospitals (
>   hospital_id TEXT PRIMARY KEY,
>   name TEXT NOT NULL,
>   region TEXT NOT NULL,
>   latitude FLOAT NOT NULL,
>   longitude FLOAT NOT NULL,
>   contact_email TEXT,
>   contact_phone TEXT
> );
>
> INSERT INTO hospitals VALUES
> ('HOSP_TVM_01', 'General Hospital Thiruvananthapuram', 'Thiruvananthapuram, Kerala', 8.5241, 76.9366, 'contact@gh-tvm.demo', '+91-471-000-0001'),
> ('HOSP_KCH_01', 'Kochi Medical Center', 'Kochi, Kerala', 9.9312, 76.2673, 'contact@kmc.demo', '+91-484-000-0002'),
> ('HOSP_KZK_01', 'Kozhikode Care Hospital', 'Kozhikode, Kerala', 11.2588, 75.7804, 'contact@kzk-care.demo', '+91-495-000-0003');
> ```
>
> Provide the full `.sql` migration file and connection instructions for Neon (connection string via env var `DATABASE_URL`).

**Integration note:** Modules 3, 4, 6, 8 all read/write to these tables. Keep table/column names exact.

---

## MODULE 2 — Synthetic Data Generation & Seeding Script

**Prompt:**

> Write a Python script (`seed_global_db.py`) that populates `global_cases` with 30 synthetic, HPO-annotated rare disease case records so the heatmap and RAG search never look empty.
>
> Requirements:
> - Pull rare disease + HPO term associations conceptually from Orphanet/HPO structure (e.g. Fabry Disease, Ehlers-Danlos Syndrome, Wilson's Disease, Gaucher Disease, Marfan Syndrome — pick ~10 rare diseases, 3 vignettes each).
> - For each of the 30 records, use an LLM (Gemini or Groq, whichever is configured in env) to generate one realistic but fully synthetic patient vignette: a short natural-language symptom description consistent with 3-5 HPO terms for that disease.
> - Extract/attach the corresponding HPO term list (id + label) as JSONB.
> - Generate the embedding using the same embedding pipeline as Module 3 (all-MiniLM-L6-v2 locally via `sentence-transformers`; fallback to Gemini embedding API if MiniLM isn't available in the environment).
> - Randomly assign each record to one of the 3 demo hospitals (`HOSP_TVM_01`, `HOSP_KCH_01`, `HOSP_KZK_01`) and use that hospital's exact lat/long from the `hospitals` table (do not randomize coordinates — heatmap should cluster at real hospital points).
> - Assign `disease_candidate_label` = the known disease name (since this is seed data, we know ground truth).
> - Set `privacy_epsilon_used = 5.0` for all rows (cosmetic).
> - Insert all 30 rows into `global_cases`.
> - Make the script idempotent/re-runnable (truncate + reseed on each run) so it can be re-run anytime before a demo to refresh data.
>
> Output: a runnable script with clear console logging of progress ("Generated vignette 4/30: Fabry Disease...").

**Integration note:** This must be run once before demoing the heatmap/RAG search so Module 8 and Module 6 have data to show.

---

## MODULE 3 — Hospital Agent Backend (Django `/agent` endpoint)

**Prompt:**

> Build a Django app with one endpoint: `POST /agent`.
>
> Input JSON:
> ```json
> { "hospital_id": "HOSP_TVM_01", "patient_ref_id": "PT-2091", "symptom_text": "free text from doctor" }
> ```
>
> The endpoint runs 3 sequential LLM-powered "tool" steps (use Groq or Gemini API, whichever is faster to set up — pick one, but structure the code so the LLM provider is swappable via env var):
>
> **Tool 1 — HPO Mapping:** Prompt the LLM to convert `symptom_text` into a structured list of HPO terms. Use a strict prompt template that forces JSON output only, e.g.:
> ```
> You are a clinical NLP system. Extract Human Phenotype Ontology (HPO) terms from the following doctor's note. Return ONLY a JSON array of objects: [{"id": "HP:XXXXXXX", "label": "term name"}]. If you are not certain of the exact HPO code, provide your best estimate — do not return prose.
> Doctor's note: "<symptom_text>"
> ```
>
> **Tool 2 — Uniqueness Judgment:** Prompt the same LLM with the extracted HPO terms plus a summary of the hospital's existing local case store (fetch last ~20 cases' HPO terms from that hospital's local table) and ask it to judge: is this phenotype combination unique/rare relative to what's already been seen at this hospital? Force JSON output: `{"is_unique": true/false, "reasoning": "short reason"}`. (Per your instruction, the LLM itself judges this qualitatively — no similarity threshold math needed here.)
>
> **Tool 3 — Embedding + Conditional Push:** Generate an embedding of the HPO term list (via `sentence-transformers` `all-MiniLM-L6-v2`, or Gemini embedding API as fallback) and store the case in the hospital's local table (`hospital_<name>_cases`) regardless of uniqueness. If `is_unique == true`, call the internal `/push` endpoint (Module 4) to send it to the global DB.
>
> **Response to frontend:**
> ```json
> {
>   "hpo_terms": [...],
>   "is_unique": true,
>   "reasoning": "...",
>   "pushed_to_global": true
> }
> ```
>
> Structure the code so each tool is a separate function (`extract_hpo()`, `judge_uniqueness()`, `push_if_unique()`) chained in the view — this is what will be described in the demo as "the agent."

**Integration note:** Depends on Module 1 (tables) and calls Module 4 internally. Frontend for this is Module 5.

---

## MODULE 4 — Push Endpoint (`/push`)

**Prompt:**

> Build one Django endpoint: `POST /push`, called internally by Module 3 (not exposed to end users, but keep it as a real HTTP endpoint for architectural clarity/demo narrative).
>
> Input JSON (matches the "final product" schema from the brief):
> ```json
> {
>   "hospital_id": "HOSP_TVM_01",
>   "patient_ref_id": "PT-2091",
>   "hpo_terms": [...],
>   "embedding": [0.0142, -0.0531, ...],
>   "confidence_score": 0.87,
>   "privacy_epsilon_used": 5.0
> }
> ```
>
> Logic:
> - Look up the hospital's region + lat/long from the `hospitals` table using `hospital_id`.
> - Insert a new row into `global_cases` with all fields populated. `disease_candidate_label` stays NULL at this stage (unknown until diagnosed).
> - Explicitly do NOT accept or store any field resembling a patient name, DOB, address, or free-text symptom description — only `patient_ref_id`, structured `hpo_terms`, and the embedding vector. Validate and reject the request (400) if any disallowed field is present, to make the privacy boundary demoable/visible.
> - Return `{"status": "pushed", "case_id": "<uuid>"}`.

**Integration note:** Consumes Module 1's `global_cases` and `hospitals` tables. Called only by Module 3.

---

## MODULE 5 — Hospital Dashboard Frontend (React + Vite + shadcn)

**Prompt:**

> Build a React + Vite app using shadcn/ui components, styled in a minimalist black/white/grey theme (high contrast, accessible — proper ARIA labels, keyboard-navigable, visible focus states).
>
> This is the **doctor-facing dashboard**. Build it as a single reusable app, but instantiate it 3 times (3 separate deployed instances/routes — `/hospital/tvm`, `/hospital/kochi`, `/hospital/kzk`) each pre-configured with a different `hospital_id` baked into its env/config, so each hospital has its own distinct UI instance per your requirement.
>
> UI:
> - A clean header showing the hospital name (e.g. "General Hospital Thiruvananthapuram — Agent Console").
> - A text input field labeled "Patient reference ID" and a large textarea labeled "Describe patient symptoms" where the doctor types natural language.
> - A "Submit to Agent" button (shadcn `Button`) that POSTs to `/agent` (Module 3) with `{hospital_id, patient_ref_id, symptom_text}`.
> - While waiting, show a shadcn `Skeleton` loading state.
> - On response, display in a shadcn `Card`:
>   - Extracted HPO terms as shadcn `Badge` chips
>   - Uniqueness verdict as a colored badge (grey = common, black outline = unique/rare) with the LLM's reasoning shown below in muted text
>   - A confirmation line: "✓ Pushed to global registry" only if `pushed_to_global: true`
> - Keep the whole flow on one screen, no navigation needed.

**Integration note:** Calls Module 3's `/agent` endpoint. Needs `hospital_id` per instance to match Module 1's seeded `hospitals` table.

---

## MODULE 6 — RAG Search Backend (`/refer`)

**Prompt:**

> Build a Django endpoint: `POST /refer`.
>
> Input JSON:
> ```json
> { "query_text": "doctor's natural language description of a confusing case" }
> ```
>
> Logic (the "orchestrator"):
> 1. Extract HPO terms from `query_text` using the same LLM-prompted extraction function as Module 3 (`extract_hpo()` — reuse it, don't duplicate).
> 2. Generate an embedding of the extracted HPO terms (same embedding function as Module 3/2).
> 3. Run a `pgvector` cosine similarity query against `global_cases.embedding`, ordered ascending by distance, return top 5.
> 4. For each result, join against the `hospitals` table to get hospital name, region, contact email, and contact phone.
> 5. Translate each result's HPO term codes back into human-readable **symptom names** (not raw HPO codes) for display — either by using the `label` already stored in `hpo_terms` JSONB, or re-resolving via the LLM if needed.
>
> Response JSON:
> ```json
> {
>   "results": [
>     {
>       "symptoms": ["Ptosis", "Muscle weakness", "Fatigue"],
>       "similarity_score": 0.91,
>       "hospital_name": "Kochi Medical Center",
>       "region": "Kochi, Kerala",
>       "contact_email": "contact@kmc.demo",
>       "contact_phone": "+91-484-000-0002"
>     },
>     ...
>   ]
> }
> ```

**Integration note:** Reuses Module 3's HPO extraction and embedding functions — refactor those into a shared `agent_utils.py` module so both `/agent` and `/refer` import from the same place. Depends on Module 1 + Module 2's seed data to have results to return.

---

## MODULE 7 — RAG Search Frontend

**Prompt:**

> Build a React + shadcn UI page (`/search`) in the same black/white/grey minimalist theme.
>
> UI:
> - A header: "Case Reference Search"
> - A large shadcn `Textarea` where a clinician types a natural-language case description (placeholder: "e.g. 45-year-old with progressive muscle weakness, drooping eyelids, and fatigue worsening through the day...")
> - A "Search similar cases" `Button` that POSTs `{query_text}` to `/refer` (Module 6)
> - Results shown as a vertical list of shadcn `Card`s, each showing:
>   - Symptom badges (shadcn `Badge`)
>   - Similarity score as a simple progress bar or percentage
>   - Hospital name + region
>   - Contact email/phone as clickable `mailto:`/`tel:` links
> - Empty state before search: muted placeholder text "Describe a case above to find similar patients across the registry."
> - Loading state: shadcn `Skeleton` cards while waiting.

**Integration note:** Calls Module 6's `/refer`. Independent of the hospital dashboards (Module 5) — this is the "end user" (clinician/researcher) facing app.

---

## MODULE 8 — Heatmap Backend (`/heatmap-search`)

**Prompt:**

> Build a Django endpoint: `POST /heatmap-search`.
>
> Input JSON:
> ```json
> { "symptom_keywords": ["cough", "headache"] }
> ```
>
> Logic:
> 1. For each keyword, extract/map to HPO term(s) using the shared `extract_hpo()` function (Module 3/6's shared utility) — batch these into one LLM call for speed if possible.
> 2. Generate a combined embedding from the resolved HPO terms.
> 3. Run `pgvector` cosine similarity search against `global_cases`, return top matches (e.g. top 20) above a reasonable similarity floor.
> 4. Cluster results by similarity into groups (simple approach: group by `disease_candidate_label` if present, else by rounding similarity/embedding proximity into clusters) — assign each cluster a distinct color hex code (from a small fixed palette of greyscale-friendly-but-distinguishable colors, since the theme is B&W&grey but map markers need to be visually distinct — allow a small accent palette here specifically for the map, e.g. muted blue/amber/teal/maroon, since pure greyscale markers would be unreadable on a map).
> 5. Return each matching case's lat/long (from its hospital), cluster color, and a short label.
>
> Response JSON:
> ```json
> {
>   "clusters": [
>     { "label": "Cluster A — likely Fabry Disease pattern", "color": "#4A6FA5", "points": [{"lat": 8.5241, "lng": 76.9366, "case_id": "..."}] },
>     { "label": "Cluster B — respiratory phenotype", "color": "#B5651D", "points": [...] }
>   ],
>   "top_matches_list": [ { "symptom_summary": "...", "hospital_name": "...", "region": "..." } ]
> }
> ```

**Integration note:** Reuses shared `extract_hpo()` + embedding functions. Depends on Module 2's seed data.

---

## MODULE 9 — Heatmap Frontend (Leaflet + shadcn)

**Prompt:**

> Build a React + shadcn + Leaflet UI page (`/heatmap`), theme consistent with the rest (black/white/grey chrome, map itself can use a light/clean tile layer like CartoDB Positron for minimalism).
>
> UI:
> - A tag-input component at the top: user types a symptom keyword and presses Enter/comma to convert it into a removable pill/chip (shadcn `Badge` with an "×" button), e.g. `[cough ×] [headache ×]`. Maintain the list of active keywords in state.
> - A "Search" button that sends the current keyword list to `/heatmap-search` (Module 8).
> - Below/beside the input: a `react-leaflet` map centered on Kerala (approx lat 10.27, lng 76.4, zoom 7), rendering colored circle markers per returned cluster point (color from the API response).
> - A side panel (or below on mobile) listing `top_matches_list` as compact shadcn `Card`s — symptom summary, hospital name, region.
> - Empty state: map still renders (centered on Kerala, no markers) with a muted prompt: "Add symptom keywords above to see matching cases on the map."
> - Ensure responsive layout: map full-width on mobile, side-by-side with results list on desktop.

**Integration note:** Calls Module 8's `/heatmap-search`. Fully independent UI from Modules 5 and 7.

---

## MODULE 10 — Integration, Env Config & Deployment

**Prompt:**

> Tie the system together for a live demo:
>
> 1. **Shared backend utils file** (`agent_utils.py`): confirm `extract_hpo()`, `judge_uniqueness()`, `get_embedding()` are defined once and imported by `/agent`, `/refer`, and `/heatmap-search` views — no duplicated logic.
> 2. **Env vars needed:**
>    - `DATABASE_URL` (Neon connection string)
>    - `LLM_PROVIDER` = `groq` or `gemini`
>    - `GROQ_API_KEY` / `GEMINI_API_KEY` (whichever is set)
>    - `EMBEDDING_PROVIDER` = `local` (all-MiniLM-L6-v2 via sentence-transformers) or `gemini` (fallback)
> 3. **CORS:** enable Django CORS headers for all 3 frontend apps' deployed origins (or `*` for hackathon speed).
> 4. **Deployment plan:**
>    - Backend: Django app deployed to Render/Railway/Fly.io (pick one — fastest free-tier deploy), pointing at Neon DB.
>    - Frontends: 3 hospital dashboard instances + heatmap + search app, all deployed as static Vite builds (Vercel/Netlify), each with its own env-configured `hospital_id` / API base URL.
>    - Run Module 2's seeding script once against the deployed Neon DB before the demo.
> 5. **Demo script order** (for the live walkthrough): (a) show a hospital dashboard submitting a symptom → agent flags it unique → pushes to global DB; (b) switch to heatmap, type keywords, show colored clusters appear including the just-pushed case; (c) switch to RAG search, type a natural-language case, show ranked similar cases with hospital contact info.

---

*End of build prompt. Build in module order 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 for smooth dependency resolution.*

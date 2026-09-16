# Rare Disease Federated Detection — MVP

A privacy-preserving rare disease case registry. Hospitals detect unique cases locally, push only safe signals (HPO terms + embeddings) to a shared global registry. Clinicians query via RAG search and symptom heatmap.

## Architecture

```
[Hospital UIs ×3] → /agent → /push → [Neon Postgres + pgvector]
[RAG Search UI]   → /refer → [pgvector similarity search]
[Heatmap UI]      → /heatmap-search → [pgvector + clustering]
```

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Neon Postgres database with pgvector extension

### 1. Environment Setup
```bash
# Copy .env and fill in your values
cp .env.example .env
# Required: DATABASE_URL, GROQ_API_KEY (or GEMINI_API_KEY)
```

### 2. Database Setup
```bash
# Run the SQL migration against your Neon DB
psql $DATABASE_URL -f backend/migrations/001_initial.sql
```

### 3. Backend
```bash
cd backend
pip install -r requirements.txt
python manage.py check          # Verify Django setup
python seed_global_db.py        # Populate 30 synthetic cases
python manage.py runserver      # Start on :8000
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev                     # Start on :5173 (proxies API to :8000)
```

### 5. Open in Browser
- Hospital TVM: http://localhost:5173/hospital/tvm
- Hospital Kochi: http://localhost:5173/hospital/kochi
- Hospital KZK: http://localhost:5173/hospital/kzk
- RAG Search: http://localhost:5173/search
- Heatmap: http://localhost:5173/heatmap

## Demo Script
1. **Hospital Dashboard**: Open `/hospital/tvm`, enter a patient ref + symptoms → agent extracts HPO terms, judges uniqueness, pushes to global DB if unique
2. **Heatmap**: Open `/heatmap`, type symptom keywords → see colored cluster markers on Kerala map
3. **RAG Search**: Open `/search`, describe a case in natural language → find similar cases with hospital contact info

## Environment Variables
| Variable | Description |
|---|---|
| `DATABASE_URL` | Neon Postgres connection string |
| `LLM_PROVIDER` | `groq` or `gemini` |
| `GROQ_API_KEY` | Groq API key |
| `GEMINI_API_KEY` | Gemini API key |
| `EMBEDDING_PROVIDER` | `local` (MiniLM) or `gemini` |

## Tech Stack
- **Backend**: Django, Neon Postgres + pgvector
- **Frontend**: React + Vite + shadcn-inspired components
- **LLM**: Groq (default) / Gemini
- **Embeddings**: all-MiniLM-L6-v2 (local)
- **Map**: Leaflet + CartoDB Positron tiles

## Privacy
No patient-identifiable data (names, DOB, addresses, raw symptoms) ever leaves a hospital's local system. Only structured HPO terms, reference IDs, and embedding vectors cross into the global DB.

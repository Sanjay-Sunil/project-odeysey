# Odyssey: Rare Disease Federated Detection

Odyssey is a privacy-preserving federated case registry designed to accelerate the diagnosis and research of rare diseases. By connecting isolated hospital systems through a secure, centralized intelligence layer, Odyssey allows medical institutions to collaborate and discover matching symptom patterns globally without ever compromising patient privacy.

## The Problem
Rare diseases are notoriously difficult to diagnose because individual doctors or hospitals may only see a specific condition once in their career. Valuable diagnostic data is trapped in local hospital silos, locked behind strict privacy regulations (like HIPAA) that prevent sharing raw patient notes. 

When a doctor encounters a confounding set of symptoms, they often lack the ability to check if another hospital has successfully diagnosed a patient with the exact same presentation.

## The Solution
Odyssey introduces a **federated agent architecture**. 

1. **Local Hospital Agents**: An AI agent runs securely on each hospital's local premises. When a clinician enters a complex case, the local agent analyzes the unstructured clinical notes and extracts standardized medical concepts (Human Phenotype Ontology or HPO terms).
2. **Privacy-Preserving Vectorization**: The agent converts these HPO terms into high-dimensional embeddings (vectors). The raw, identifiable clinical text *never leaves the hospital*.
3. **Global Collaboration**: The extracted HPO terms and vector embeddings are securely pushed to a central global database. Clinicians across the network can then query this global database to find similar cases using AI-powered semantic similarity (RAG) and geographic heatmaps.

## Architecture & Data Flow

Odyssey utilizes a decoupled frontend/backend architecture, integrating cutting-edge LLMs and Vector databases.

```mermaid
graph TD
    %% Local Hospital Boundary
    subgraph Hospital Local Environment [Hospital Local Environment - Secure]
        UI[Hospital Clinician UI]
        Agent[Local AI Agent / LLM]
    end

    %% Global Boundary
    subgraph Global Environment [Global Federated Cloud]
        API[Odyssey Backend API]
        DB[(Neon Postgres + pgvector)]
        RAG[RAG Search Engine]
        Map[Geographic Heatmap]
    end

    %% Data Flow
    UI -- "1. Raw Patient Notes (Private)" --> Agent
    Agent -- "2. Extracts HPO Terms" --> Agent
    Agent -- "3. Pushes Safe Signals (HPO + Embeddings)" --> API
    API -- "4. Stores global cases" --> DB
    
    RAG -- "5. Semantic Search" --> DB
    Map -- "6. Geospatial Clustering" --> DB
```

### Components

#### 1. Hospital Agent Endpoint (`/agent`)
- **Input**: Raw, unstructured symptom text and patient demographic metadata.
- **Process**: 
  - Uses an LLM (Groq) to extract standardized **Human Phenotype Ontology (HPO)** terms.
  - Converts the HPO terms into a semantic embedding using a local `all-MiniLM-L6-v2` embedding model.
  - Checks the local hospital database to determine if this symptom combination is **unique**.
- **Output**: If unique, it automatically pushes the anonymized data to the global registry. All personally identifiable information (PII) is stripped.

#### 2. RAG Search Engine (`/refer`)
- **Input**: A clinician's natural language query (e.g., "tall stature, long fingers, chest pain").
- **Process**: Converts the query into a vector embedding and performs a **Cosine Similarity Search** against the global database using `pgvector`.
- **Output**: Returns the top matching historical cases from across the federated network, allowing clinicians to request referrals or collaborate.

#### 3. Geographic Heatmap (`/heatmap-search`)
- **Input**: Specific symptom keywords (e.g., "chorea", "tremor").
- **Process**: Filters the global database for cases matching the symptoms and groups them geographically.
- **Output**: Returns clustered coordinate data rendered on a Leaflet map, enabling researchers to track regional outbreaks or genetic clusters of rare symptoms.

## Tech Stack

- **Frontend**: React + Vite, Shadcn UI, Tailwind CSS, React Router, Leaflet (Mapping)
- **Backend**: Django (Python)
- **Database**: Neon Serverless Postgres with the `pgvector` extension
- **AI / LLM**: Groq API (`openai/gpt-oss-20b` fallback) for rapid HPO extraction
- **Embeddings**: HuggingFace `sentence-transformers/all-MiniLM-L6-v2` (Local execution)

## Privacy & Security Guarantees
- **No PII Transmission**: Names, addresses, dates of birth, and raw symptom text are strictly retained in the local hospital schema.
- **Information Boundary**: Only deterministic HPO terms and their mathematical vector representations are transmitted to the `/push` endpoint.
- **Secure Architecture**: The global database is strictly separated from local patient records.

---

## Developer Setup Guide

### Prerequisites
- Python 3.10+
- Node.js 18+
- Neon Postgres database with the `pgvector` extension installed.

### 1. Environment Setup
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgres://user:password@ep-name.region.aws.neon.tech/dbname?sslmode=require
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key_here
EMBEDDING_PROVIDER=local
```

### 2. Database Migration
Apply the initial schema migration to your Neon database:
```bash
# Using psql or any Postgres client
psql $DATABASE_URL -f backend/migrations/001_initial.sql
```

### 3. Backend Setup
Install Python dependencies and start the Django server:
```bash
cd backend
python -m pip install -r requirements.txt

# (Optional) Seed the database with 30 synthetic rare disease cases
python seed_global_db.py

# Start the server on http://localhost:8000
python manage.py runserver
```

### 4. Frontend Setup
Install Node dependencies and start the Vite dev server:
```bash
cd frontend
npm install

# Start the frontend on http://localhost:5173
npm run dev
```

### 5. Running the Application
Access the applications in your browser:
- **Hospital Dashboards**: 
  - [Thiruvananthapuram (TVM)](http://localhost:5173/hospital/tvm)
  - [Kochi](http://localhost:5173/hospital/kochi)
  - [Kozhikode (KZK)](http://localhost:5173/hospital/kzk)
- **RAG Search Engine**: [http://localhost:5173/search](http://localhost:5173/search)
- **Global Heatmap**: [http://localhost:5173/heatmap](http://localhost:5173/heatmap)

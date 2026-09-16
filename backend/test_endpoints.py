import requests
import json

BASE_URL = "http://localhost:8000"

print("========================================")
print("1. Testing Agent Extraction & Uniqueness")
print("========================================")
agent_res = requests.post(f"{BASE_URL}/agent", json={
    "hospital_id": "HOSP_TVM_01",
    "patient_ref_id": "TEST_CASE_01",
    "symptom_text": "A 45-year-old male presenting with progressive muscle weakness in lower limbs, drooping eyelids bilaterally, and fatigue that worsens significantly through the day."
})
print("Status:", agent_res.status_code)
agent_data = agent_res.json()
print("Response:", json.dumps(agent_data, indent=2))

if agent_data.get("is_unique"):
    print("\n[Case was automatically pushed to Global DB by the Agent]")

print("\n========================================")
print("3. Testing RAG Similarity Search")
print("========================================")
rag_res = requests.post(f"{BASE_URL}/refer", json={
    "query_text": "tall stature with long fingers and chest pain"
})
print("Status:", rag_res.status_code)
print("Response:", json.dumps(rag_res.json(), indent=2))

print("\n========================================")
print("4. Testing Heatmap Search")
print("========================================")
heat_res = requests.post(f"{BASE_URL}/heatmap-search", json={
    "symptom_keywords": ["chorea", "tremor"]
})
print("Status:", heat_res.status_code)
print("Response:", json.dumps(heat_res.json(), indent=2))

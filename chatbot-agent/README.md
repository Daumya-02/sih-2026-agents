# Chat Agent — conversational Q&A for the women's health app

One endpoint: `POST /agent/chat/{user_id}` — `{"message": "..."}` → a conversational reply,
grounded in that user's own profile + logs (via the shared backend) and WHO/ICMR/ACOG guidelines
(via the same FAISS index the lifestyle coach agent builds).

Read-only: this agent never writes to the backend. It can:
- Answer questions about the user's cycle, symptoms, and history using their real profile/logs.
- Summarize medical-report data already on file — extracted lab values/medications/doctor notes
  live in a log entry's `note`/`symptoms` fields (put there by the OCR intake agent); ongoing
  conditions/allergies live in the profile's `health_conditions` field.
- Ground advice in WHO/ICMR/ACOG guidelines instead of general knowledge.
- Flag red-flag symptoms and recommend seeing a doctor/gynecologist — it does **not** have a real
  clinic directory or location data, so it won't invent clinic names; it just nudges the user to
  search "gynecologist near me" or check their existing provider.

Conversation history is kept in-memory per `user_id` (same pattern/caveat as the OCR agent's
report cache — resets on restart, single-instance only; swap for Redis/DB if you need it to
persist). `DELETE /agent/chat/{user_id}` clears a user's conversation to start fresh.

## Setup

```bash
cd chatbot-agent
python -m venv venv
venv\Scripts\activate      # Windows; source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env       # then paste your real GEMINI_API_KEY into .env (not .env.example!)
uvicorn main:app --reload --port 8002
```

The `guideline_index.faiss` / `guideline_chunks.pkl` files are copied from the lifestyle coach
agent so this service is self-contained. If you rebuild the guideline index there (`ingest.py`),
copy the two files over here again.

## Test

```bash
curl -X POST http://127.0.0.1:8002/agent/chat/1 \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"where am I in my cycle right now?\"}"

curl -X POST http://127.0.0.1:8002/agent/chat/1 \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"summarize anything from my recent reports\"}"

curl -X DELETE http://127.0.0.1:8002/agent/chat/1   # reset the conversation
```

Known-good test user ids on the shared backend: `1`, `2`, `3`, `10`.

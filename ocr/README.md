# Document Agent — OCR + Chat for medical reports

Two endpoints:
- `POST /agent/ocr/{user_id}` — multipart image upload → OCR → agent reads current profile/logs,
  merges in symptoms/conditions/medications, writes back via PATCH/PUT, returns a plain-language summary.
- `POST /agent/chat/{user_id}` — `{"message": "..."}` → answers questions grounded in the last uploaded
  report for that user (plus their profile/logs).

`user_id` is a path parameter, never something the LLM has to read or output.

## Step 1 — Install

```bash
cd womens-health-agent
python3 -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2 — Get a free Gemini API key

Go to https://aistudio.google.com/apikey → create key.

## Step 3 — Configure

```bash
cp .env.example .env
```
Open `.env`, paste your key into `GEMINI_API_KEY`. Leave everything else as-is
(`BACKEND_BASE_URL` already points at your Workers API, `ADMIN_TOOL_ENABLED=false`).

## Step 4 — Run

```bash
uvicorn app.main:app --reload --port 8000
```
First OCR call downloads EasyOCR's model weights (~100MB, one-time).

## Step 5 — Test

```bash
curl -F "file=@report.jpg" http://localhost:8000/agent/ocr/123

curl -X POST http://localhost:8000/agent/chat/123 \
  -H "Content-Type: application/json" \
  -d '{"message": "what medication did the report mention?"}'
```

Check the response's `summary`, and hit `GET /users/123/profile` and `/users/123/logs` on your
backend directly to confirm the fields actually updated.

## Step 6 — Wire into the app

```js
// OCR upload (track screen)
const form = new FormData();
form.append("file", imageFile);
const res = await fetch(`${AGENT_BASE_URL}/agent/ocr/${userId}`, { method: "POST", body: form });
const { summary } = await res.json();   // show this; DB is already updated

// Chat about the report
const res2 = await fetch(`${AGENT_BASE_URL}/agent/chat/${userId}`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: userInput }),
});
const { reply } = await res2.json();
```

Typed entries (no photo): call `/agent/chat/{user_id}` directly, or add a tiny
`/agent/text/{user_id}` route that calls `process_report()` with the typed string instead of OCR text.

## Step 7 — Make it reachable from your phone/app (prototype-friendly, no deploy)

Easiest for a hackathon demo — expose your local server with a tunnel instead of deploying:
```bash
# in a second terminal, with the server still running on :8000
npx localtunnel --port 8000
# or: ngrok http 8000   (https://ngrok.com, free)
```
Use the `https://...` URL it gives you as `AGENT_BASE_URL` in the app. Works from anywhere,
zero deployment config, but only live while your machine + tunnel are running.

## Step 8 — Actual deploy (optional, when you want it always-on)

Render free tier, no Docker needed:
1. Push this folder to a GitHub repo.
2. https://render.com → New → Web Service → connect the repo.
3. Environment: **Python 3**.
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add env vars in the dashboard: `BACKEND_BASE_URL`, `GEMINI_API_KEY`, `LLM_MODEL`,
   `ADMIN_TOOL_ENABLED`, `ADMIN_TOKEN`, `OCR_ENGINE`.
5. Deploy → you get `https://your-agent.onrender.com` as `AGENT_BASE_URL`.

Free tier sleeps after inactivity; first request after sleep is slow (~15–20s, EasyOCR reload).
For a snappier demo, set `OCR_ENGINE=tesseract` in env vars and add `pytesseract` +
`apt-get install tesseract-ocr` on Render's build (Python runtime supports an `apt-packages`
file — see Render docs) — smaller and faster than EasyOCR.

## Known limitations (worth mentioning in your write-up)

- `_last_report_by_user` (main.py) is in-memory — resets on restart, single-instance only.
  Fine for a demo; swap for Redis/DB if you need it to persist.
- No dedicated `medications`/`allergies` columns in the current schema — the agent folds
  allergies into `health_conditions` and medications/dosage/timing into the log `note` field
  as structured text. Add real columns later and update `tools.py`'s schemas + the prompt in
  `agent.py` to match.
- `admin_query` is off by default, server-side only, token never touches the frontend.

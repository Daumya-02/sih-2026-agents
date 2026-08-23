# Agents → API Endpoint Mapping

This file documents, per agent in the repo, which backend endpoints they call, what data they send, and what they expect back or update.

## 1) Lifestyle Coach agent (`lifestyle coach/agent.py`)

- Purpose: generate personalized lifestyle suggestions and optionally persist a computed flag/score for the user.

- Tools and HTTP endpoints called:
  - `get_user_profile` -> GET `/users/{user_id}/profile`
    - Request: HTTP GET to `/users/{user_id}/profile` (agent's `tools.get_user_profile(user_id)`).
    - Auth: backend should enforce that the token maps to `user_id` when used by non-admin callers; server-side agent calls may use service credentials.
    - Expected response: full `Profile` JSON (see `api-client-endpoints.md` for schema). Example fields returned: `user_id, name, email, age, birth_year, cycle_length, period_length, last_period_start, goals, track_priorities, health_conditions, reminder_*`, etc.

  - `get_user_logs` -> GET `/users/{user_id}/logs`
    - Request: HTTP GET to `/users/{user_id}/logs` (agent calls without query params in current code).
    - Expected response: array of `Log` objects: `{id, user_id, date, flow, mood, symptoms, note, updated_at}`.

  - `admin_query` -> POST `/admin/query`
    - Request: JSON `{ "query": "<SQL statement>" }`. Header: `Authorization: Bearer <ADMIN_TOKEN>` (server-side only).
    - Agent intent: lifestyle agent only uses this to persist a computed score/flag for the user; client-side `tools.py` enforces that the SQL begins with `UPDATE` but backend must also validate.
    - Expected response: JSON with execution result or affected-row count. Backend must write an `admin_audit` record for every call.

  - `retrieve_guideline` — NOT an HTTP backend call. This is an internal retrieval via `retrieval.py` / FAISS and returns guideline text to the agent.

- Agent output returned to caller (the function `run_lifestyle_coach`) — not an HTTP API response but the structured JSON the agent produces:
  - Schema (must match): `{ "summary": string, "diet": [string], "sleep": [string], "exercise": [string], "hydration": [string], "flags_for_doctor": [string] }`.

Notes for backend implementers:
- Ensure GET `/users/{id}/logs` returns logs in the array shape and supports `date` ordering.
- Enforce `POST /admin/query` restrictions server-side (only `UPDATE` allowed for lifestyle agent) and create `admin_audit` entries including caller=`agent:lifestyle_coach`.

## 2) OCR / Report Intake agent (`ocr/app/agent.py` + `ocr/app/tools.py`)

- Purpose: ingest OCR text from medical reports, merge extracted data into the user's profile/logs, and return a short user-facing summary.

- Tools and HTTP endpoints called:
  - `get_profile` -> GET `/users/{user_id}/profile`
    - Request: HTTP GET to `/users/{user_id}/profile` via `_get_profile(user_id)`.
    - Expected response: full `Profile` JSON as in client schema.

  - `get_logs` -> GET `/users/{user_id}/logs`
    - Request: HTTP GET to `/users/{user_id}/logs` via `_get_logs(user_id)`.
    - Expected response: array of `Log` objects.

  - `update_profile` -> PATCH `/users/{user_id}/profile`
    - Request: JSON partial `Profile` fields (agent's `ProfileUpdate` schema). Example payloads the agent may send:
      - `{ "health_conditions": "PCOS, penicillin allergy" }`
      - `{ "birth_control": "IUD" }`
    - Behavior: agent is expected to perform a read-merge-update pattern (it calls `get_profile` then `update_profile` with merged/changed fields).
    - Expected response: the updated `Profile` JSON.

  - `update_log` -> PUT `/users/{user_id}/logs/{date}`
    - Request: JSON using `LogUpdate` schema: `{ "log_date": "YYYY-MM-DD", "symptoms": "headache, nausea", "mood": "low", "flow": "light", "note": "Metformin 500mg BID; TSH 4.1 (high)" }` (the agent's tool sends `log_date` plus partial fields in `_put_log`).
    - Behavior: create or upsert the day's log entry for the provided `log_date`.
    - Expected response: saved `Log` object (include `id`, `user_id`, `date`, `symptoms`, `note`, `updated_at`).

  - `admin_query` -> POST `/admin/query` (LAST RESORT)
    - Request: JSON `{ "sql": "<SQL>", "params": [...] }` and `Authorization: Bearer <ADMIN_TOKEN>` when enabled.
    - Behavior: OCR agent uses this only if extracted data cannot be represented in `profiles`/`logs`. Backend must gate this behind `ADMIN_TOOL_ENABLED` and log in `admin_audit`.

- Agent output returned to caller: `process_report` returns a short user-facing summary string; the agent persists extracted data via `update_profile` and `update_log` endpoints.

Notes for backend implementers:
- `PATCH /users/{id}/profile` must accept partial updates and return the full updated profile so the agent can reconcile merges.
- `PUT /users/{id}/logs/{date}` must perform UPSERT semantics and return the saved log with `id` and `updated_at`.
- `POST /admin/query` must accept parameterized queries (`params`) and reject disallowed verbs or multi-statement SQL; log every call in `admin_audit` with `caller='agent:ocr_intake'` when used.

---

Common auth and audit requirements (applies to both agents):
- Service/admin calls must use `Authorization: Bearer <ADMIN_TOKEN>` for `POST /admin/query` and any other admin endpoints.
- Agents bind `user_id` server-side (tools close over `user_id`) so the LLM never receives raw identifiers — backend must still validate the token/credentials mapping to `user_id` for safety.
- All admin-level changes must create `admin_audit` records capturing caller, action, SQL (if any), params, and before/after snapshots when possible.

Reference: see `api-client-endpoints.md` and `api-admin-endpoints.md` for full schemas and SQL examples.

## Additional fields needed for better accuracy

**Profile — missing for lifestyle coaching:**

- `weight`, `height` / BMI (diet/exercise suggestions need this)
- `activityLevel` (sedentary/moderate/active)
- `dietaryPreference` (veg/non-veg/vegan, allergies, restrictions)
- `sleepGoalHours` / `typicalSleepHours`
- `waterIntakeGoalMl`
- `stressLevel` baseline (if self-reported)
- `medications` (list — currently only `birthControl` and `healthConditions`)
- `pregnancyStatus` / `tryingToConceive` (changes advice drastically)
- `timezone` (for reminder logic)

**Logs — missing for trend detection:**

- `sleepHours` (numeric, per day) — you're inferring sleep from mood/symptoms, but no direct signal
- `waterIntakeMl`
- `exerciseMinutes` / `exerciseType`
- `weight` (optional daily/weekly entry)
- `stressLevel` (1-5 scale, more useful than mood tags alone)
- `basalBodyTemp` (optional, for cycle-phase precision)
- `painLevel` (1-10, separate from symptom tags — "cramps" alone doesn't tell severity)

Without sleep/water/exercise/stress numeric fields, the agent's `diet`/`sleep`/`exercise`/`hydration` output fields have nothing to reason over except mood and symptom tags — it'll be guessing, not personalizing.

## Datasets to use / generate

No public dataset maps cleanly to this schema (menstrual + lifestyle logs are sensitive/rare in open data), so synthetic generation is the practical path:

- **Reference for realistic ranges:** Kaggle's "Menstrual Cycle Data" / "FitBit Fitness Tracker Data" (public, for realistic sleep/exercise/step ranges) — use only to calibrate plausible value distributions, don't merge directly (different schema).
- **Generate 4–5 synthetic user profiles + 30-60 days of logs each** covering distinct patterns:

1. Regular cycle, active lifestyle, good sleep — baseline/healthy case
2. Irregular cycle, PCOS flagged, poor sleep, high stress — tests `flags_for_doctor` logic
3. On birth control, low symptom variance — tests suppressed-cycle handling
4. Irregular sleep/hydration, frequent headaches/fatigue — tests correlation detection (e.g., low water → headache)
5. Trying to conceive, tracking BBT — tests a completely different advice branch

I can generate this synthetic dataset (JSON matching your exact schema, extended with the new fields) if useful — say the word and I'll build it as a file.

## Agent output → endpoint mapping

Agent
Produces
Sent to

Lifestyle Coach
`{summary, diet[], sleep[], exercise[], hydration[], flags_for_doctor[]}`
Returned directly to caller (not persisted by default) — only a computed score/flag, if any, goes via `POST /admin/query` (UPDATE only)

OCR Intake
Short summary string (to caller/chat)
Extracted structured fields go via `PATCH /users/{id}/profile` (health_conditions, birth_control, medications) and `PUT /users/{id}/logs/{date}` (symptoms, note, mood); anything unrepresentable falls back to `POST /admin/query` (last resort, gated)

If you add the new fields above, both `update_profile`/`PATCH` and `update_log`/`PUT` need their schemas extended to accept them — currently the client schema you pasted has no room for sleep hours, water intake, weight, or stress level.

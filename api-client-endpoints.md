# Client API Endpoints (App)

This document lists API endpoints called by the mobile/desktop app, what data they send and receive, and the DB changes expected so backend can implement schema and migrations.

**Auth**: App endpoints assume per-install `Bearer <user_token>` (short-lived) or `X-Install-Id: <uuid>` + shared secret. Backend: require authenticated request for all `/users/{id}` routes; `POST /users` may accept an initial install token.

---

## POST /users
- Purpose: Register a new install/user record after onboarding (called once per install).
- Auth: optional initial app key; returns created user id and auth token.
- Request JSON:
  - name: string
  - email: string
  - birth_year: integer (optional)
  - age: integer (optional)
  - cycle_length: integer (days, optional)
  - period_length: integer (days, optional)
  - last_period_start: date (YYYY-MM-DD, optional)
  - onboarding fields (goals, track_priorities, birth_control, health_conditions)
  - timezone: string (IANA)
- Response JSON (201):
  - id: integer
  - install_id: uuid
  - token: string (JWT or opaque)
  - profile: Profile object
- DB effects:
  - INSERT into `profiles` (see schema below)
  - create initial row in `logs` optional for first day

---

## GET /users/by-email?email={email}
- Purpose: Lookup a `user_id` by email for recovery.
- Auth: server API key or limited auth; rate-limit.
- Response JSON (200):
  - id: integer
  - email: string
  - name: string
- DB effects: SELECT from `profiles` WHERE email = :email

---

## GET /users/{id}/profile
- Purpose: Retrieve app's own profile.
- Auth: Bearer token that maps to `id`.
- Response JSON (200): `Profile` object (see schema)
- DB effects: SELECT from `profiles` WHERE user_id = :id

---

## PATCH /users/{id}/profile
- Purpose: Update profile fields for the app's install.
- Auth: Bearer token.
- Request JSON: Partial `Profile` fields. Allowed keys:
  - name, email, age, birth_year, cycle_length, period_length, last_period_start,
    goals (string), track_priorities (array|string), period_frequency (string),
    health_conditions (array|string), birth_control (string), reminder_enabled (bool),
    reminder_days_before (int), reminder_time (HH:MM), reminder_message (string),
    reminder_sound (string), onboarded (bool), theme (string)
- Response JSON (200): updated `Profile` object
- DB effects: UPDATE `profiles` SET ... WHERE user_id = :id; update `updated_at` timestamp.

---

## GET /users/{id}/logs?start=YYYY-MM-DD&end=YYYY-MM-DD
- Purpose: Return daily logs for a date range (app displays history).
- Auth: Bearer token.
- Response JSON (200): array of `Log` objects
- DB effects: SELECT * FROM `logs` WHERE user_id = :id AND date BETWEEN start AND end ORDER BY date

---

## PUT /users/{id}/logs/{date}
- Purpose: Create or update a log entry for a given day.
- Auth: Bearer token.
- Request JSON:
  - flow: string (e.g., "light", "medium", "heavy")
  - mood: string (or numeric scale)
  - symptoms: array of strings OR object {code, severity}
  - note: string
- Response JSON (200/201): saved `Log` object
- DB effects: UPSERT into `logs` (unique on `user_id`,`date`). Update `updated_at`.

---

## GET /version
- Purpose: App queries current published app version for feature gating.
- Auth: none or public API key
- Response JSON (200):
  - version: string (semver)
  - release_notes: string
  - min_supported: string (semver)
- DB effects: SELECT from `app_version` table


# Data Schemas (recommended)

Below are suggested SQL schemas and notes to guide DB implementation. Choose PostgreSQL for JSONB support.

**profiles** (table)
- SQL (Postgres):

```sql
CREATE TABLE profiles (
  user_id SERIAL PRIMARY KEY,
  install_id UUID UNIQUE,
  name TEXT,
  email TEXT UNIQUE,
  age INT,
  birth_year INT,
  cycle_length INT,
  period_length INT,
  last_period_start DATE,
  goals TEXT,
  track_priorities JSONB,
  period_frequency TEXT,
  health_conditions JSONB,
  birth_control TEXT,
  reminder_enabled BOOLEAN DEFAULT FALSE,
  reminder_days_before INT,
  reminder_time TIME,
  reminder_message TEXT,
  reminder_sound TEXT,
  onboarded BOOLEAN DEFAULT FALSE,
  theme TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX idx_profiles_email ON profiles(email);
```

Notes:
- `track_priorities` and `health_conditions` are JSONB to allow arrays/objects.
- `email` unique index required for `/users/by-email`.

**logs** (table)
- SQL (Postgres):

```sql
CREATE TABLE logs (
  id BIGSERIAL PRIMARY KEY,
  user_id INT REFERENCES profiles(user_id) ON DELETE CASCADE,
  date DATE NOT NULL,
  flow TEXT,
  mood TEXT,
  symptoms JSONB,
  note TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  UNIQUE(user_id, date)
);

CREATE INDEX idx_logs_user_date ON logs(user_id, date);
```

Notes:
- `symptoms` JSONB (array of strings or objects). If analytics require structured queries, create `symptoms` normalized table instead.

**app_version** (table)

```sql
CREATE TABLE app_version (
  id SERIAL PRIMARY KEY,
  version TEXT NOT NULL,
  release_notes TEXT,
  min_supported TEXT,
  published_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

---

# Migration / Upsert examples

- Upsert log (Postgres):

```sql
INSERT INTO logs (user_id, date, flow, mood, symptoms, note, updated_at)
VALUES ($1,$2,$3,$4,$5,$6, now())
ON CONFLICT (user_id, date)
  DO UPDATE SET flow = EXCLUDED.flow,
                mood = EXCLUDED.mood,
                symptoms = EXCLUDED.symptoms,
                note = EXCLUDED.note,
                updated_at = now();
```

- Update profile partial (example in server): build SET clause only for provided fields and run `UPDATE profiles SET ... WHERE user_id = $id RETURNING *`.

---

# Backend notes / recommendations
- Use transactions for multi-row updates.
- Add audit log table for admin changes: `admin_audit(id, admin_id, action, target_table, target_id, payload, created_at)`.
- Consider soft deletes (`deleted_at`) if required.
- Store symptoms normalized if you need to run aggregated queries across symptom codes.

---

END OF CLIENT DOC

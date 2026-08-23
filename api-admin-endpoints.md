# Admin API Endpoints

This document lists admin API endpoints, expected request/response shapes, and DB implications so backend can create appropriate schema, RBAC, and migrations.

**Auth**: Admin endpoints must enforce strong auth (API key, admin JWT, or OAuth2 with admin scope). Audit all changes.

---

## GET /admin/schema
- Purpose: Return current DB schema objects (tables, indexes) and CREATE statements.
- Auth: Admin only.
- Response: array of objects {name, type, create_statement}
- DB effects: SELECT from information_schema or `pg_dump -s` equivalent.

---

## POST /admin/query
- Purpose: Run a single SELECT/INSERT/UPDATE/DELETE statement (no DDL).
- Auth: Admin only, restricted origin, rate-limited, and logged.
- Request JSON: { sql: string }
- Response: query result or affected-row count
- DB effects: Executes the provided SQL within a transaction.
- Safety: Disallow multiple statements, require parameterization support.

---

## GET /admin/users
- Purpose: List all users with a profile summary for admin overview.
- Auth: Admin only.
- Query params: `limit`, `offset`, optional filters (onboarded, email, created_before)
- Response JSON: array of summaries: {user_id, name, email, onboarded, last_active, created_at}
- DB effects: SELECT from `profiles`; join latest log if `last_active` required.

---

## GET /admin/users/{id}
- Purpose: Get a user's full profile and logs.
- Auth: Admin only.
- Response JSON:
  - profile: Profile object
  - logs: array of Log objects
- DB effects: SELECT * FROM profiles WHERE user_id = :id; SELECT * FROM logs WHERE user_id = :id ORDER BY date DESC

---

## PATCH /admin/users/{id}/profile
- Purpose: Update profile fields (schema is fixed).
- Auth: Admin only.
- Request JSON: allowed fields (explicit list): `name,email,age,birth_year,cycle_length,period_length,last_period_start,goals,track_priorities,period_frequency,health_conditions,birth_control,reminder_* ,onboarded,theme`
- Response JSON: updated Profile
- DB effects: UPDATE profiles SET ...; write admin audit entry.

---

## PATCH /admin/logs/{id}
- Purpose: Update a log entry's mutable fields: `flow, mood, symptoms, note`.
- Auth: Admin only.
- Request JSON: partial Log fields
- Response JSON: updated Log
- DB effects: UPDATE logs SET ... WHERE id = :id; write admin audit entry.

---

## GET /version
(Also available to admin and public)
- Purpose: Retrieve current app version metadata (see client doc)
- DB effects: SELECT from `app_version`.

## POST /admin/version/bump
- Purpose: Publish or bump app version (admin action).
- Auth: Admin only.
- Request JSON:
  - version: string (semver)
  - release_notes: string
  - min_supported: string (semver)
- Response JSON: created `app_version` record
- DB effects: INSERT into `app_version` and optionally update a single-row `current_version` table or cache.

---

# Admin DB support tables and suggestions

**admin_audit**
- Purpose: Track admin changes for compliance.

```sql
CREATE TABLE admin_audit (
  id BIGSERIAL PRIMARY KEY,
  admin_id INT NULL, -- references admins table when available
  action TEXT NOT NULL,
  target_table TEXT,
  target_id TEXT,
  payload JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

**admins** (optional)

```sql
CREATE TABLE admins (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  role TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

# Admin usage notes
- All admin mutations must create an `admin_audit` entry with `payload` containing before/after snapshots where possible.
- For `POST /admin/query`, keep a strict allowlist or sandbox the SQL to trusted read-only operations for non-superusers.
- Back up schema before running DDL via admin tools; disallow DDL via `POST /admin/query`.

---

END OF ADMIN DOC

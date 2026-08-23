"""
Thin client around your Workers backend + LangChain tool wrappers.

Design choice per your requirement: userId is NEVER put in the LLM prompt.
`build_tools_for_user(user_id)` closes over the id, so every tool the
model sees just takes the *fields* to read/write — the id is bound at
the Python level, before the agent ever runs.
"""
import httpx
from datetime import date as date_type
from typing import Optional
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.config import BACKEND_BASE_URL, ADMIN_TOKEN, ADMIN_TOOL_ENABLED

_client = httpx.Client(base_url=BACKEND_BASE_URL, timeout=15.0)


# ---------- raw HTTP helpers ----------

def _get_profile(user_id: int) -> dict:
    r = _client.get(f"/users/{user_id}/profile")
    r.raise_for_status()
    return r.json()


def _patch_profile(user_id: int, fields: dict) -> dict:
    r = _client.patch(f"/users/{user_id}/profile", json=fields)
    r.raise_for_status()
    return r.json()


def _get_logs(user_id: int) -> dict:
    r = _client.get(f"/users/{user_id}/logs")
    r.raise_for_status()
    return r.json()


def _put_log(user_id: int, log_date: str, fields: dict) -> dict:
    r = _client.put(f"/users/{user_id}/logs/{log_date}", json=fields)
    r.raise_for_status()
    return r.json()


def _admin_query(sql: str, params: Optional[list] = None) -> dict:
    if not ADMIN_TOOL_ENABLED:
        raise PermissionError("Admin query tool is disabled (set ADMIN_TOOL_ENABLED=true).")
    if not ADMIN_TOKEN:
        raise PermissionError("ADMIN_TOKEN not configured server-side.")
    lowered = sql.strip().lower()
    if not lowered.startswith(("select", "insert", "update", "delete")):
        raise ValueError("Only SELECT/INSERT/UPDATE/DELETE allowed — no DDL.")
    r = _client.post(
        "/admin/query",
        json={"sql": sql, "params": params or []},
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    )
    r.raise_for_status()
    return r.json()


# ---------- per-user tool factory ----------

class ProfileUpdate(BaseModel):
    health_conditions: Optional[str] = Field(None, description="Comma-separated conditions/allergies/diagnoses to merge into the profile, e.g. 'PCOS, penicillin allergy'")
    birth_control: Optional[str] = None
    goals: Optional[str] = None
    track_priorities: Optional[str] = None


class LogUpdate(BaseModel):
    log_date: str = Field(..., description="YYYY-MM-DD. Use the report/prescription date if present, else today.")
    symptoms: Optional[str] = Field(None, description="Comma-separated symptoms found in the report")
    mood: Optional[str] = None
    flow: Optional[str] = None
    note: Optional[str] = Field(None, description="Free text: medications, dosage, timing, lab values, doctor notes — anything that doesn't fit a dedicated column")


def build_tools_for_user(user_id: int):

    @tool("get_profile", return_direct=False)
    def get_profile() -> dict:
        """Fetch this user's health profile (name, age, cycle info, health_conditions, birth_control, goals, etc.)."""
        return _get_profile(user_id)

    @tool("get_logs", return_direct=False)
    def get_logs() -> dict:
        """Fetch this user's daily logs (date, flow, mood, symptoms, note)."""
        return _get_logs(user_id)

    @tool("update_profile", args_schema=ProfileUpdate)
    def update_profile(**fields) -> dict:
        """Update profile-level fields. Only pass fields that changed; merge with existing values yourself before calling (read the profile first)."""
        clean = {k: v for k, v in fields.items() if v is not None}
        if not clean:
            return {"skipped": "no fields to update"}
        return _patch_profile(user_id, clean)

    @tool("update_log", args_schema=LogUpdate)
    def update_log(log_date: str, **fields) -> dict:
        """Create/update a day's log entry with symptoms, mood, flow, or free-text notes extracted from a report."""
        clean = {k: v for k, v in fields.items() if v is not None}
        return _put_log(user_id, log_date, clean)

    @tool("admin_query")
    def admin_query(sql: str) -> dict:
        """
        LAST RESORT ONLY. Run a single SELECT/INSERT/UPDATE/DELETE (no DDL) when
        a piece of extracted data has nowhere to go in profile/log fields.
        Prefer update_profile / update_log whenever possible.
        """
        return _admin_query(sql)

    tools = [get_profile, get_logs, update_profile, update_log]
    if ADMIN_TOOL_ENABLED:
        tools.append(admin_query)
    return tools

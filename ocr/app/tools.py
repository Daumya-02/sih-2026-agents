"""
Thin client around your Workers backend + LangChain tool wrappers.

Matches the REAL deployed schema (confirmed from live /profile and /logs
responses):
  - responses are wrapped: {"profile": {...}} and {"logs": [...]}
  - fields are camelCase (healthConditions, trackPriorities, ...)
  - healthConditions, medications, goals, trackPriorities, symptoms, mood
    are all arrays, not comma-separated strings
  - logs carry extra metrics: sleepHours, waterIntakeMl, exerciseMinutes,
    exerciseType, weightKg, stressLevel, basalBodyTemp, painLevel

userId is NEVER put in the LLM prompt — build_tools_for_user(user_id)
closes over the id, so every tool the model sees just takes the *fields*
to read/write; the id is bound at the Python level before the agent runs.
"""
import httpx
from typing import Optional, List
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.config import BACKEND_BASE_URL, ADMIN_TOKEN, ADMIN_TOOL_ENABLED

_client = httpx.Client(base_url=BACKEND_BASE_URL, timeout=15.0)


# ---------- raw HTTP helpers ----------

def _get_profile(user_id: int) -> dict:
    r = _client.get(f"/users/{user_id}/profile")
    r.raise_for_status()
    return r.json()["profile"]


def _patch_profile(user_id: int, fields: dict) -> dict:
    r = _client.patch(f"/users/{user_id}/profile", json=fields)
    r.raise_for_status()
    return r.json()


def _get_logs(user_id: int) -> list:
    r = _client.get(f"/users/{user_id}/logs")
    r.raise_for_status()
    return r.json()["logs"]


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
    healthConditions: Optional[List[str]] = Field(None, description="FULL replacement list of conditions/diagnoses. Merge yourself: take what get_profile returned, add the new ones, pass the whole merged list — this overwrites, it does not append.")
    medications: Optional[List[str]] = Field(None, description="FULL replacement list of medications (include dosage/timing in each string, e.g. 'Metformin 500mg BID'). Merge with existing before calling — this overwrites, it does not append.")
    birthControl: Optional[str] = None
    goals: Optional[List[str]] = None
    trackPriorities: Optional[List[str]] = None
    pregnancyStatus: Optional[str] = None


class LogUpdate(BaseModel):
    log_date: str = Field(..., description="YYYY-MM-DD, path param. Use the report/prescription date if present, else today.")
    symptoms: Optional[List[str]] = Field(None, description="FULL replacement list of symptoms for this day. Merge with the existing log's symptoms first.")
    mood: Optional[List[str]] = None
    flow: Optional[str] = Field(None, description="none | light | medium | heavy")
    note: Optional[str] = Field(None, description="Free text for anything with no dedicated field — lab values, doctor remarks, etc.")
    painLevel: Optional[int] = Field(None, description="0-10 scale, only if the report states it")
    sleepHours: Optional[float] = None
    stressLevel: Optional[int] = Field(None, description="If the report implies a stress/anxiety level, 1-5 scale")


def build_tools_for_user(user_id: int):

    @tool("get_profile", return_direct=False)
    def get_profile() -> dict:
        """Fetch this user's health profile: name, age, cycle info, goals, trackPriorities, healthConditions, medications, birthControl, pregnancyStatus, etc. ALWAYS call this before update_profile so you can merge array fields instead of overwriting them."""
        return _get_profile(user_id)

    @tool("get_logs", return_direct=False)
    def get_logs() -> list:
        """Fetch this user's daily logs (date, flow, mood, symptoms, note, sleepHours, painLevel, etc). ALWAYS call this before update_log to find the matching date and merge its symptoms/mood arrays instead of overwriting them."""
        return _get_logs(user_id)

    @tool("update_profile", args_schema=ProfileUpdate)
    def update_profile(**fields) -> dict:
        """Update profile-level fields. healthConditions/medications/goals/trackPriorities are FULL replacement arrays — read the current profile first and include existing values plus new ones, don't send only the new item."""
        clean = {k: v for k, v in fields.items() if v is not None}
        if not clean:
            return {"skipped": "no fields to update"}
        return _patch_profile(user_id, clean)

    @tool("update_log", args_schema=LogUpdate)
    def update_log(log_date: str, **fields) -> dict:
        """Create/update a day's log entry. symptoms/mood are FULL replacement arrays — if a log already exists for this date, read it via get_logs first and merge, don't overwrite with only the new items."""
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

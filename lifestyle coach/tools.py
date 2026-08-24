import os
import requests

BASE_URL = os.getenv("BACKEND_BASE_URL",
    "https://women-health-backend-team-bread.nadamkrishna.workers.dev/api")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")  # server-side only, never sent to frontend

def get_user_profile(user_id: str) -> dict:
    r = requests.get(f"{BASE_URL}/users/{user_id}/profile", timeout=15)
    r.raise_for_status()
    return r.json()

def get_user_logs(user_id: str) -> dict:
    r = requests.get(f"{BASE_URL}/users/{user_id}/logs", timeout=15)
    r.raise_for_status()
    return r.json()

def admin_query(sql: str) -> dict:
    """Controlled writes only. Called by the agent, never exposed to the frontend."""
    if not sql.strip().lower().startswith("update"):
        return {"error": "Only UPDATE statements are permitted via this tool."}
    if not ADMIN_TOKEN:
        return {"error": "ADMIN_TOKEN not configured server-side."}
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    r = requests.post(f"{BASE_URL}/admin/query", json={"query": sql},
                       headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()
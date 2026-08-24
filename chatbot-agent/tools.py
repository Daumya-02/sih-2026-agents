import os
import requests

BASE_URL = os.getenv("BACKEND_BASE_URL",
    "https://women-health-backend-team-bread.nadamkrishna.workers.dev/api")


def get_user_profile(user_id: int) -> dict:
    r = requests.get(f"{BASE_URL}/users/{user_id}/profile", timeout=15)
    r.raise_for_status()
    return r.json()["profile"]


def get_user_logs(user_id: int) -> list:
    r = requests.get(f"{BASE_URL}/users/{user_id}/logs", timeout=15)
    r.raise_for_status()
    return r.json()["logs"]

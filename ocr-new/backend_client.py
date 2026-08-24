import os
import requests
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL")


def get_logs(user_id: int):
    url = f"{BACKEND_URL}/users/{user_id}/logs"

    response = requests.get(url)
    response.raise_for_status()

    return response.json()


def update_log(user_id: int, date: str, log_data: dict):
    url = f"{BACKEND_URL}/users/{user_id}/logs/{date}"

    response = requests.put(
        url,
        json=log_data
    )

    response.raise_for_status()

    return response.json()
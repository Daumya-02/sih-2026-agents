import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agent import run_lifestyle_coach
from ratelimit import enforce_rate_limit

app = FastAPI(title="Lifestyle Coach Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your app's domain before production
    allow_methods=["GET"],
    allow_headers=["*"],
)

RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "10"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))


@app.get("/api/insights/{user_id}")
def get_insights(user_id: str):
    enforce_rate_limit(user_id, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW_SECONDS)
    try:
        return run_lifestyle_coach(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
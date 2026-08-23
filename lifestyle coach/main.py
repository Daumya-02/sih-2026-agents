from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agent import run_lifestyle_coach

app = FastAPI(title="Lifestyle Coach Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your app's domain before production
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/api/insights/{user_id}")
def get_insights(user_id: str):
    try:
        return run_lifestyle_coach(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
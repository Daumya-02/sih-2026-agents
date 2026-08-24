from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from agent import chat_with_user, reset_session

app = FastAPI(title="Women's Health — Chat Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your app's domain before production
    allow_methods=["POST", "DELETE"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


@app.post("/agent/chat/{user_id}")
async def chat(user_id: int, body: ChatRequest):
    try:
        # chat_with_user is sync (LLM round-trips, tool calls) — offload so one
        # user's turn doesn't block every other concurrent request.
        reply = await run_in_threadpool(chat_with_user, user_id, body.message)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent error: {e}")
    return {"user_id": user_id, "reply": reply}


@app.delete("/agent/chat/{user_id}")
def clear_chat(user_id: int):
    """Drop this user's in-memory conversation so their next message starts fresh."""
    reset_session(user_id)
    return {"user_id": user_id, "status": "conversation reset"}


@app.get("/health")
def health():
    return {"status": "ok"}

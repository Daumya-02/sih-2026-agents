from fastapi import FastAPI, UploadFile, File, HTTPException, Path
from pydantic import BaseModel

from app.ocr import extract_text
from app.agent import process_report, chat_about_report

app = FastAPI(title="Women's Health — Document Agent")

# In-memory cache of each user's last-uploaded report text, for the chat flow.
# Swap for Redis/DB in production — this resets on restart and doesn't scale
# across multiple server instances.
_last_report_by_user: dict[int, str] = {}


class ChatRequest(BaseModel):
    message: str


@app.post("/agent/ocr/{user_id}")
async def upload_report(user_id: int = Path(...), file: UploadFile = File(...)):
    image_bytes = await file.read()
    try:
        raw_text = extract_text(image_bytes)
    except ValueError as e:
        raise HTTPException(422, str(e))

    _last_report_by_user[user_id] = raw_text

    try:
        summary = process_report(user_id, raw_text)
    except Exception as e:
        # OCR succeeded but the agent/backend step failed — still return the raw text
        # so the app isn't left with nothing.
        raise HTTPException(502, f"Extracted text but failed to process/update: {e}")

    return {
        "user_id": user_id,
        "raw_text": raw_text,
        "summary": summary,
    }


@app.post("/agent/chat/{user_id}")
async def chat(user_id: int = Path(...), body: ChatRequest = None):
    report_text = _last_report_by_user.get(user_id, "")
    try:
        reply = chat_about_report(user_id, body.message, report_text)
    except Exception as e:
        raise HTTPException(502, f"Agent error: {e}")
    return {"user_id": user_id, "reply": reply}


@app.get("/health")
def health():
    return {"status": "ok"}

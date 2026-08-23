import os
from dotenv import load_dotenv

load_dotenv()

# --- Backend (your Workers API) ---
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "https://women-health-backend-team-bread.nadamkrishna.workers.dev/api")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")          # server-side only, never sent to frontend
ADMIN_TOOL_ENABLED = os.getenv("ADMIN_TOOL_ENABLED", "false").lower() == "true"

# --- LLM (Gemini has a usable free tier — swap for OpenAI if you prefer) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")

# --- OCR ---
# "easyocr" (better accuracy, heavier, downloads models on first run)
# "tesseract" (lighter, faster to set up, needs the tesseract binary installed)
OCR_ENGINE = os.getenv("OCR_ENGINE", "easyocr")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY missing in .env")

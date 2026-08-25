import os
from datetime import date
from google import genai
from google.genai import types
from tools import get_user_profile, get_user_logs
from retrieval import retrieve_guideline
from dotenv import load_dotenv
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="get_user_profile",
            description="Fetch the user's health/demographic profile. Fields are camelCase: cycle info "
                        "(cycleLength, periodLength, lastPeriodStart, periodFrequency), healthConditions "
                        "and medications (arrays), birthControl, pregnancyStatus, goals and "
                        "trackPriorities (arrays), plus weightKg/heightCm, activityLevel, "
                        "dietaryPreference/dietaryRestrictions, sleepGoalHours/typicalSleepHours, "
                        "waterIntakeGoalMl, stressLevelBaseline, timezone.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="get_user_logs",
            description="Fetch the user's daily logs. Each entry has date, flow, mood/symptoms (arrays), "
                        "note, and — where logged — sleepHours, waterIntakeMl, exerciseMinutes/"
                        "exerciseType, weightKg, stressLevel, basalBodyTemp, painLevel. The `note` and "
                        "`symptoms` fields often hold data extracted from medical reports/prescriptions "
                        "the user has previously uploaded (lab values, medications, doctor notes) — use "
                        "this when the user asks you to summarize a report or explain a past result.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="retrieve_guideline",
            description="Search WHO/ICMR/ACOG health guidelines for evidence-based information relevant "
                        "to the user's question. Use this to ground medical/lifestyle advice instead of "
                        "relying on general knowledge alone.",
            parameters=types.Schema(
                type="OBJECT",
                properties={"query": types.Schema(type="STRING")},
                required=["query"],
            ),
        ),
    ])
]

SYSTEM_PROMPT = """You are a warm, careful health-chat assistant for a women's health app, talking
directly with one specific user across a running conversation.

You can call get_user_profile, get_user_logs, and retrieve_guideline. Use get_user_profile/
get_user_logs whenever the question is about this user's own cycle, symptoms, medications, or
history — don't assume data from earlier in the conversation is still fresh, re-call them if the
user mentions something that may have changed (a new log entry, a new report). Use
retrieve_guideline to ground medical/lifestyle advice in WHO/ICMR/ACOG guidance rather than
general knowledge, whenever the question calls for it.

What you help with:
- Answering questions about their cycle, symptoms, logs, and profile in plain language.
- Explaining their current status (e.g. where they likely are in their cycle given
  lastPeriodStart/cycleLength, recent symptom trends, any flagged conditions) using their
  actual profile + logs. Never invent data that isn't there — say so if something isn't logged.
- Summarizing medical report data already on file: extracted lab values, medications, and doctor
  notes typically live in a log entry's `note`/`symptoms` fields, and ongoing conditions live in
  the profile's `healthConditions` field. Summarize only what's actually present.
- Giving evidence-based lifestyle/health guidance grounded in retrieve_guideline results.

Safety rules — follow strictly:
- Never diagnose. You provide information and guidance, not a diagnosis.
- If the user describes a red-flag symptom — e.g. heavy or prolonged bleeding, severe or
  one-sided abdominal/pelvic pain, fainting, fever with signs of infection, sudden vision
  changes, chest pain or shortness of breath, thoughts of self-harm, or signs of a possible
  ectopic pregnancy or miscarriage complication — clearly and calmly flag it as something to get
  checked urgently, and recommend seeing a doctor/gynecologist promptly, or emergency care if it
  sounds severe. Don't be alarmist about routine symptoms, but never downplay a real red flag.
- When it's relevant, encourage the user to see a gynecologist/OB-GYN or their doctor for anything
  you can't fully resolve with information. You do not have real-time location data or a clinic
  directory — don't invent clinic names or addresses. Instead suggest they search "gynecologist
  near me" in their maps app, or check with their existing clinic/insurance.
- If asked something well outside women's health/general wellness, answer briefly and steer back.

Keep replies conversational, warm, and concise — this is a chat, not a report."""


def dispatch(name, args, user_id):
    if name == "get_user_profile":
        return get_user_profile(user_id)
    if name == "get_user_logs":
        return get_user_logs(user_id)
    if name == "retrieve_guideline":
        return retrieve_guideline(args.get("query", ""))
    return {"error": "unknown tool"}


# In-memory per-user chat sessions — resets on restart, single-instance only.
# Swap for Redis/DB-backed history if this needs to survive restarts or scale
# across multiple server instances.
_sessions: dict[int, object] = {}


def _get_session(user_id: int):
    chat = _sessions.get(user_id)
    if chat is None:
        chat = client.chats.create(
            model=os.getenv("LLM_MODEL", "gemini-3.5-flash-lite"),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=TOOLS,
            ),
        )
        _sessions[user_id] = chat
    return chat


def chat_with_user(user_id: int, message: str) -> str:
    """Send one user message, running any tool calls the model needs. Returns the reply text."""
    chat = _get_session(user_id)
    today = date.today().isoformat()
    response = chat.send_message(f"[Today's date: {today}]\n{message}")

    for _ in range(6):  # capped tool-call loop
        calls = response.function_calls
        if not calls:
            break
        parts = []
        for fc in calls:
            result = dispatch(fc.name, dict(fc.args), user_id)
            parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
        response = chat.send_message(parts)

    return (response.text or "").strip()


def reset_session(user_id: int) -> None:
    _sessions.pop(user_id, None)

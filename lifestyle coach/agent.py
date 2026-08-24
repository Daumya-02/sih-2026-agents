import os, json, re
from google import genai
from google.genai import types
from tools import get_user_profile, get_user_logs, admin_query
from retrieval import retrieve_guideline
from dotenv import load_dotenv
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="get_user_profile",
            description="Fetch the user's medical/demographic profile (conditions, cycle info, etc.)",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="get_user_logs",
            description="Fetch the user's daily logs: water intake, sleep, exercise, meals, wearable data, mood, symptoms.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="admin_query",
            description="Run a single controlled SQL UPDATE to persist a computed value for this user. Never for reads.",
            parameters=types.Schema(
                type="OBJECT",
                properties={"sql": types.Schema(type="STRING")},
                required=["sql"],
            ),
        ),
        types.FunctionDeclaration(
            name="retrieve_guideline",
            description="Search WHO/ICMR/ACOG health guidelines for evidence-based recommendations relevant to the user's condition.",
            parameters=types.Schema(
                type="OBJECT",
                properties={"query": types.Schema(type="STRING")},
                required=["query"],
            ),
        ),
    ])
]

SYSTEM_PROMPT = """You are the Lifestyle Planning Coach for a women's health app.
Always call get_user_profile and get_user_logs for the current user first.
Then call retrieve_guideline with relevant queries (e.g. "PCOS diet", "sleep recommendations
adult women", "menopause exercise") to ground your suggestions in real guidelines before answering.
Give specific, encouraging, evidence-based lifestyle suggestions. Never diagnose — flag concerning
patterns for clinician follow-up instead.
Only call admin_query to persist a computed score/flag for this user, as a single UPDATE scoped to their row.
Return ONLY JSON matching:
{
  "summary": string,
  "diet": [string],
  "sleep": [string],
  "exercise": [string],
  "hydration": [string],
  "flags_for_doctor": [string]
}
"""

def dispatch(name, args, user_id):
    if name == "get_user_profile":
        return get_user_profile(user_id)
    if name == "get_user_logs":
        return get_user_logs(user_id)
    if name == "admin_query":
        return admin_query(args.get("sql", ""))
    if name == "retrieve_guideline":
        return retrieve_guideline(args.get("query", ""))
    return {"error": "unknown tool"}

def run_lifestyle_coach(user_id: str) -> dict:
    chat = client.chats.create(
        model=os.getenv("LLM_MODEL", "gemini-3.6-flash"),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=TOOLS,
        ),
    )
    response = chat.send_message(f"Generate today's lifestyle insights for user_id={user_id}.")

    for _ in range(6):  # capped tool-call loop
        calls = response.function_calls
        if not calls:
            break
        parts = []
        for fc in calls:
            result = dispatch(fc.name, dict(fc.args), user_id)
            parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
        response = chat.send_message(parts)

    text = (response.text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"summary": text, "diet": [], "sleep": [], "exercise": [],
                 "hydration": [], "flags_for_doctor": []}
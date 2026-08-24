from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.config import GEMINI_API_KEY, LLM_MODEL
from app.tools import build_tools_for_user

_llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=GEMINI_API_KEY, temperature=0)

REPORT_SYSTEM_PROMPT = """You are a medical-report intake agent for a women's health app.
You will be given raw OCR text from a photo of a medical report, prescription, or lab result
for ONE specific user (already identified — you never need to ask for or output a user id).

healthConditions, medications, goals, trackPriorities on the profile, and symptoms/mood on a
log entry, are all FULL REPLACEMENT ARRAYS — the backend does not append for you. You must:

1. Call get_profile and get_logs FIRST, every time, before writing anything.
2. Extract from the OCR text: symptoms, diagnoses/conditions, medications (with dosage/timing
   folded into the string, e.g. "Metformin 500mg BID"), and any other clinically relevant note.
3. For update_profile: take the existing healthConditions list from get_profile, add any new
   conditions found in the report (skip duplicates), and pass the WHOLE merged list. Do the same
   for medications. Never call update_profile with just the new item(s) — that would delete the
   rest of the user's history.
4. For update_log: find (in get_logs) whether an entry already exists for the report's date (or
   today if no date is visible). If it does, merge its symptoms/mood arrays with any new ones the
   same way — full merged list, not just the new items. Put anything with no dedicated field
   (lab values, doctor remarks) in the note field as short plain text.
5. Only use admin_query if a value genuinely cannot fit any profile/log field.
6. After updating, respond with a short plain-language summary of what the report says and what
   you updated — this is shown to the user, so keep it clear and non-alarming. Do not invent
   findings that aren't in the text.

If the OCR text is garbled or clearly not a medical document, say so and update nothing.
"""

CHAT_SYSTEM_PROMPT = """You are a helpful assistant answering a user's questions about a medical
report they uploaded, and about their own health data. You may call get_profile and get_logs for
context. The full OCR text of their most recently uploaded report is provided below — answer
using it; if the question needs info not in the report or their stored data, say so plainly.
Never give a diagnosis; suggest they confirm anything clinically significant with their doctor.

--- REPORT TEXT ---
{report_text}
--- END REPORT TEXT ---
"""


def _make_executor(system_prompt: str, user_id: int, extra_vars: dict | None = None) -> AgentExecutor:
    tools = build_tools_for_user(user_id)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt.format(**(extra_vars or {})) if extra_vars else system_prompt),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(_llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False, max_iterations=8)


def process_report(user_id: int, ocr_text: str) -> str:
    """Run the intake agent on freshly OCR'd report text. Returns the user-facing summary."""
    executor = _make_executor(REPORT_SYSTEM_PROMPT, user_id)
    result = executor.invoke({"input": f"OCR text of the uploaded report:\n\n{ocr_text}"})
    return result["output"]


def chat_about_report(user_id: int, message: str, report_text: str) -> str:
    """Answer a follow-up question, with the last report text as grounding context."""
    executor = _make_executor(CHAT_SYSTEM_PROMPT, user_id, {"report_text": report_text or "(no report on file yet)"})
    result = executor.invoke({"input": message})
    return result["output"]

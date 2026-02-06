# import re
# import json
# from summrizeStdConv import summarize_text_with_groq
# from agents.studyPlane import extract_topic_from_sentence
# # -----------------------------
# # Intent Detection
# # -----------------------------
# def detect_intent_and_topic(query: str) -> dict:
#     q = query.lower()

#     if any(x in q for x in ["quiz", "test me", "start quiz"]):
#         match = re.search(r"(?:on|from|of)\s+(.*)", q)
#         return {"intent": "QUIZ", "topic": match.group(1) if match else None}

#     if any(x in q for x in ["study plan", "how to learn", "start learning"]):
#         match = re.search(r"(?:learn|study)\s+(.*)", q)
#         return {"intent": "STUDY_PLAN", "topic": match.group(1) if match else None}
    
#     if any(word in query.lower() for word in ["notes", "make notes", "summary", "revision"]):
#         return {
#             "intent": "NOTES",
#             "topic": extract_topic_from_sentence(query)
#         }
#     return {"intent": "CHAT", "topic": None}


# # -----------------------------
# # Safe JSON Loader
# # -----------------------------
# def safe_json_load(raw: str) -> dict:
#     match = re.search(r"\{[\s\S]*?\}", raw)
#     if not match:
#         return {}

#     json_str = match.group(0)
#     json_str = json_str.replace("'", '"')
#     json_str = re.sub(r",\s*}", "}", json_str)

#     try:
#         return json.loads(json_str)
#     except:
#         return {}


# # -----------------------------
# # Confusion Diagnosis
# # -----------------------------
# def diagnose_student_confusion(question: str, subject: str, class_name: str) -> dict:
#     prompt = f"""
# Return ONLY valid JSON.

# Class: {class_name}
# Subject: {subject}
# Question: "{question}"

# Rules:
# - Use NO_CONFUSION when the student is asking a clear factual or conceptual question (e.g. "what is X?", "is X equal to Y?", "explain Z"). Only use CONCEPT_GAP / FORMULA_CONFUSION / PROCEDURAL_ERROR when the question itself shows a clear misconception (wrong claim, confused formula, or wrong procedure).
# - If in doubt, prefer NO_CONFUSION so we do not mark correct or neutral questions as wrong.

# JSON:
# {{
#   "confusion_type": "NO_CONFUSION | CONCEPT_GAP | FORMULA_CONFUSION | PROCEDURAL_ERROR",
#   "reason": "short reason",
#   "teaching_strategy": "how to explain"
# }}
# """

#     raw = summarize_text_with_groq(text=question, prompt=prompt)

#     try:
#         return json.loads(raw)
#     except:
#         return safe_json_load(raw) or {
#             "confusion_type": "NO_CONFUSION",
#             "reason": "",
#             "teaching_strategy": ""
#         }


# # -----------------------------
# # Teacher Chat (Preference Aware + Session-aware Follow-ups)
# # -----------------------------
# def diagnosis_chat(student_agent, query, class_name, subject, student_profile, context=None):
#     """
#     Generate a personalized, session-aware response.

#     Args:
#         student_agent: instance of StudentAgent
#         query: current student query
#         class_name: student's class
#         subject: subject of query
#         student_profile: student's profile/preferences
#         context: optional list of previous query-response dictionaries for follow-ups
#     Returns:
#         dict with response, confusion_type, updated profile, quality_scores
#     """

#     # -----------------------------
#     # Diagnose confusion first
#     # -----------------------------
#     diagnosis = diagnose_student_confusion(query, subject, class_name)
#     confusion_type = diagnosis.get("confusion_type", "NO_CONFUSION")

#     # Initialize student profile fields
#     student_profile.setdefault("confusion_counter", {})
#     student_profile.setdefault("common_mistakes", [])

#     if confusion_type != "NO_CONFUSION":
#         student_profile["confusion_counter"][confusion_type] = (
#             student_profile["confusion_counter"].get(confusion_type, 0) + 1
#         )
#         if confusion_type not in student_profile["common_mistakes"]:
#             student_profile["common_mistakes"].append(confusion_type)

#     # -----------------------------
#     # Load preferences
#     # -----------------------------
#     level = student_profile.get("level", "basic")
#     tone = student_profile.get("tone", "friendly")
#     learning_style = student_profile.get("learning_style", "step-by-step")
#     response_length = student_profile.get("response_length", "long")
#     include_example = student_profile.get("include_example", True)
#     common_mistakes = student_profile.get("common_mistakes") or []

#     # -----------------------------
#     # Prepare session-aware context text
#     # -----------------------------
#     session_history_text = ""
#     if context:
#         for turn in context:
#             if isinstance(turn, dict):
#                 session_history_text += f"Previous Q: {turn.get('query','')}\nPrevious A: {turn.get('response','')}\n"
#             elif isinstance(turn, str):
#                 session_history_text += f"{turn}\n"

#     # -----------------------------
#     # Build full query for the agent
#     # -----------------------------
#     full_query = ""
#     if session_history_text:
#         full_query += f"Previous conversation:\n{session_history_text}\n"
#     full_query += f"Current Question:\n{query}\n"

#     full_query += f"""
# Class: {class_name}
# Subject: {subject}

# Student preferences:
# - Level: {level}
# - Tone: {tone}
# - Learning style: {learning_style}
# - Response length: {response_length}
# - Include example: {include_example}
# - Common mistakes to address: {common_mistakes}

# Rules:
# - If the student asks a follow-up based on previous answers, use prior context to answer.
# - Teach at {level} level. Be {tone}. Use {learning_style} style.
# - Response length MUST be {response_length}. {"Include ONE brief example only." if include_example else "Do NOT add examples."}
# - Be encouraging. Gently address common mistakes if present.
# - If the student provides new facts in previous queries, incorporate them when relevant.
# """

#     if response_length == "very short":
#         full_query += "\nCRITICAL: Give a VERY SHORT answer (2-4 sentences max). No long explanations.\n"
#     elif response_length == "short":
#         full_query += "\nKeep the answer SHORT (one short paragraph).\n"

#     # -----------------------------
#     # Get LLM response
#     # -----------------------------
#     result = student_agent.ask(
#         query=full_query,
#         class_name=class_name,
#         subject=subject,
#         student_profile=student_profile
#     )

#     if isinstance(result, dict):
#         response = result.get("response", "")
#         quality_scores = result.get("quality_scores", {})
#     else:
#         response = result or ""
#         quality_scores = {}

#     return {
#         "response": response,
#         "confusion_type": confusion_type,
#         "profile": student_profile,
#         "quality_scores": quality_scores
#     }



import re
import json
from threading import Lock
from studentProfileDetails.summrizeStdConv import summarize_text_with_groq
from studentProfileDetails.agents.studyPlane import extract_topic_from_sentence


# =====================================================
# 🔐 IN-MEMORY PROMPT CACHE (GLOBAL, NO DB)
# =====================================================

_PROMPT_LOCK = Lock()

PROMPT_CACHE = {
    "BASE_TEACHER_PROMPT": """
You are an expert teacher AI.

Core rules:
- Be clear, calm, and encouraging
- Never shame or discourage the student
- Prefer intuitive explanations before formulas
- Do not hallucinate facts
- Adjust explanation to student level and preferences
"""
}

def get_base_prompt() -> str:
    with _PROMPT_LOCK:
        return PROMPT_CACHE["BASE_TEACHER_PROMPT"]


def update_base_prompt(new_prompt: str):
    with _PROMPT_LOCK:
        PROMPT_CACHE["BASE_TEACHER_PROMPT"] = new_prompt.strip()


# =====================================================
# 🎯 INTENT DETECTION
# =====================================================

def detect_intent_and_topic(query: str) -> dict:
    q = query.lower()

    if any(x in q for x in ["quiz", "test me", "start quiz"]):
        match = re.search(r"(?:on|from|of)\s+(.*)", q)
        return {"intent": "QUIZ", "topic": match.group(1) if match else None}

    if any(x in q for x in ["study plan", "how to learn", "start learning"]):
        match = re.search(r"(?:learn|study)\s+(.*)", q)
        return {"intent": "STUDY_PLAN", "topic": match.group(1) if match else None}

    if any(word in q for word in ["notes", "make notes", "summary", "revision"]):
        return {
            "intent": "NOTES",
            "topic": extract_topic_from_sentence(query)
        }

    return {"intent": "CHAT", "query": q, "topic": None}


# =====================================================
# 🛡 SAFE JSON LOADER
# =====================================================

def safe_json_load(raw: str) -> dict:
    match = re.search(r"\{[\s\S]*?\}", raw)
    if not match:
        return {}

    json_str = match.group(0)
    json_str = json_str.replace("'", '"')
    json_str = re.sub(r",\s*}", "}", json_str)

    try:
        return json.loads(json_str)
    except Exception:
        return {}


# =====================================================
# 🧠 CONFUSION DIAGNOSIS
# =====================================================

def diagnose_student_confusion(question: str, subject: str, class_name: str) -> dict:
    prompt = f"""
Return ONLY valid JSON.

Class: {class_name}
Subject: {subject}
Question: "{question}"

Rules:
- Use NO_CONFUSION when the question is neutral or correct
- Use CONCEPT_GAP / FORMULA_CONFUSION / PROCEDURAL_ERROR only if misconception is explicit
- If unsure, choose NO_CONFUSION

JSON:
{{
  "confusion_type": "NO_CONFUSION | CONCEPT_GAP | FORMULA_CONFUSION | PROCEDURAL_ERROR",
  "reason": "short reason",
  "teaching_strategy": "how to explain"
}}
"""

    raw = summarize_text_with_groq(text=question, prompt=prompt)

    try:
        return json.loads(raw)
    except Exception:
        return safe_json_load(raw) or {
            "confusion_type": "NO_CONFUSION",
            "reason": "",
            "teaching_strategy": ""
        }


# =====================================================
# 🧱 PROMPT BUILDER (BASE + STUDENT + SESSION)
# =====================================================

def build_teacher_prompt(
    *,
    student_profile: dict,
    class_name: str,
    subject: str,
    confusion_type: str,
    session_context: str
) -> str:

    base_prompt = get_base_prompt()

    prompt = f"""
{base_prompt}

Class: {class_name}
Subject: {subject}
Detected confusion: {confusion_type}

Student preferences:
- Level: {student_profile.get("level", "basic")}
- Tone: {student_profile.get("tone", "friendly")}
- Learning style: {student_profile.get("learning_style", "step-by-step")}
- Response length: {student_profile.get("response_length", "long")}
- Include example: {student_profile.get("include_example", True)}
- Common mistakes: {student_profile.get("common_mistakes", [])}

Rules:
- Follow student preferences strictly
- Address confusion gently if present
- Be motivating and supportive
"""

    if session_context:
        prompt += f"\nPrevious conversation:\n{session_context}\n"

    response_length = student_profile.get("response_length", "long")

    if response_length == "very short":
        prompt += "\nCRITICAL: 2–4 sentences only.\n"
    elif response_length == "short":
        prompt += "\nKeep response to one short paragraph.\n"

    return prompt.strip()


# =====================================================
# 👩‍🏫 TEACHER CHAT (MAIN ENTRY)
# =====================================================

def diagnosis_chat(
    student_agent,
    query,
    class_name,
    subject,
    student_profile,
    context=None
):
    """
    Preference-aware, session-aware teacher response
    """

    # -----------------------------
    # Diagnose confusion
    # -----------------------------
    diagnosis = diagnose_student_confusion(query, subject, class_name)
    confusion_type = diagnosis.get("confusion_type", "NO_CONFUSION")

    student_profile.setdefault("confusion_counter", {})
    student_profile.setdefault("common_mistakes", [])

    if confusion_type != "NO_CONFUSION":
        student_profile["confusion_counter"][confusion_type] = (
            student_profile["confusion_counter"].get(confusion_type, 0) + 1
        )
        if confusion_type not in student_profile["common_mistakes"]:
            student_profile["common_mistakes"].append(confusion_type)

    # -----------------------------
    # Build session context
    # -----------------------------
    session_history_text = ""
    if context:
        for turn in context:
            if isinstance(turn, dict):
                session_history_text += (
                    f"Previous Q: {turn.get('query','')}\n"
                    f"Previous A: {turn.get('response','')}\n"
                )
            elif isinstance(turn, str):
                session_history_text += f"{turn}\n"

    # -----------------------------
    # Build final prompt
    # -----------------------------
    full_prompt = build_teacher_prompt(
        student_profile=student_profile,
        class_name=class_name,
        subject=subject,
        confusion_type=confusion_type,
        session_context=session_history_text
    )

    full_prompt += f"\nCurrent Question:\n{query}\n"

    # -----------------------------
    # Ask LLM
    # -----------------------------
    result = student_agent.ask(
        query=full_prompt,
        class_name=class_name,
        subject=subject,
        student_profile=student_profile
    )

    if isinstance(result, dict):
        response = result.get("response", "")
        quality_scores = result.get("quality_scores", {})
    else:
        response = result or ""
        quality_scores = {}

    return {
        "response": response,
        "confusion_type": confusion_type,
        "profile": student_profile,
        "quality_scores": quality_scores
    }

def set_base_prompt(new_prompt: str):
    with _PROMPT_LOCK:
        PROMPT_CACHE["BASE_TEACHER_PROMPT"] = new_prompt.strip()
# =====================================================
from fastapi.responses import JSONResponse
from pydantic import BaseModel

class UpdatePromptRequest(BaseModel):
    prompt: str

def update_base_prompt_handler(payload: UpdatePromptRequest):
    """
    Admin-only route logic.
    """

    if not payload.prompt or len(payload.prompt.strip()) < 20:
        return JSONResponse(
            status_code=400,
            content={"error": "Prompt is too short or empty"}
        )

    # ✅ CALL REAL SETTER
    set_base_prompt(payload.prompt)

    return {
        "status": "success",
        "message": "Base prompt updated successfully",
        "active_prompt_preview": get_base_prompt()[:300]
    }

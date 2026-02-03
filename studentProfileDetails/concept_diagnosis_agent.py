import re
import json
from summrizeStdConv import summarize_text_with_groq

# -----------------------------
# Intent Detection
# -----------------------------
def detect_intent_and_topic(query: str) -> dict:
    q = query.lower()

    if any(x in q for x in ["quiz", "test me", "start quiz"]):
        match = re.search(r"(?:on|from|of)\s+(.*)", q)
        return {"intent": "QUIZ", "topic": match.group(1) if match else None}

    if any(x in q for x in ["study plan", "how to learn", "start learning"]):
        match = re.search(r"(?:learn|study)\s+(.*)", q)
        return {"intent": "STUDY_PLAN", "topic": match.group(1) if match else None}

    return {"intent": "CHAT", "topic": None}


# -----------------------------
# Safe JSON Loader
# -----------------------------
def safe_json_load(raw: str) -> dict:
    match = re.search(r"\{[\s\S]*?\}", raw)
    if not match:
        return {}

    json_str = match.group(0)
    json_str = json_str.replace("'", '"')
    json_str = re.sub(r",\s*}", "}", json_str)

    try:
        return json.loads(json_str)
    except:
        return {}


# -----------------------------
# Confusion Diagnosis
# -----------------------------
def diagnose_student_confusion(question: str, subject: str, class_name: str) -> dict:
    prompt = f"""
Return ONLY valid JSON.

Class: {class_name}
Subject: {subject}
Question: "{question}"

Rules:
- Use NO_CONFUSION when the student is asking a clear factual or conceptual question (e.g. "what is X?", "is X equal to Y?", "explain Z"). Only use CONCEPT_GAP / FORMULA_CONFUSION / PROCEDURAL_ERROR when the question itself shows a clear misconception (wrong claim, confused formula, or wrong procedure).
- If in doubt, prefer NO_CONFUSION so we do not mark correct or neutral questions as wrong.

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
    except:
        return safe_json_load(raw) or {
            "confusion_type": "NO_CONFUSION",
            "reason": "",
            "teaching_strategy": ""
        }


# -----------------------------
# Teacher Chat (Preference Aware + Session-aware Follow-ups)
# -----------------------------
def diagnosis_chat(student_agent, query, class_name, subject, student_profile, context=None):
    """
    Generate a personalized, session-aware response.

    Args:
        student_agent: instance of StudentAgent
        query: current student query
        class_name: student's class
        subject: subject of query
        student_profile: student's profile/preferences
        context: optional list of previous query-response dictionaries for follow-ups
    Returns:
        dict with response, confusion_type, updated profile, quality_scores
    """

    # -----------------------------
    # Diagnose confusion first
    # -----------------------------
    diagnosis = diagnose_student_confusion(query, subject, class_name)
    confusion_type = diagnosis.get("confusion_type", "NO_CONFUSION")

    # Initialize student profile fields
    student_profile.setdefault("confusion_counter", {})
    student_profile.setdefault("common_mistakes", [])

    if confusion_type != "NO_CONFUSION":
        student_profile["confusion_counter"][confusion_type] = (
            student_profile["confusion_counter"].get(confusion_type, 0) + 1
        )
        if confusion_type not in student_profile["common_mistakes"]:
            student_profile["common_mistakes"].append(confusion_type)

    # -----------------------------
    # Load preferences
    # -----------------------------
    level = student_profile.get("level", "basic")
    tone = student_profile.get("tone", "friendly")
    learning_style = student_profile.get("learning_style", "step-by-step")
    response_length = student_profile.get("response_length", "long")
    include_example = student_profile.get("include_example", True)
    common_mistakes = student_profile.get("common_mistakes") or []

    # -----------------------------
    # Prepare session-aware context text
    # -----------------------------
    session_history_text = ""
    if context:
        for turn in context:
            if isinstance(turn, dict):
                session_history_text += f"Previous Q: {turn.get('query','')}\nPrevious A: {turn.get('response','')}\n"
            elif isinstance(turn, str):
                session_history_text += f"{turn}\n"

    # -----------------------------
    # Build full query for the agent
    # -----------------------------
    full_query = ""
    if session_history_text:
        full_query += f"Previous conversation:\n{session_history_text}\n"
    full_query += f"Current Question:\n{query}\n"

    full_query += f"""
Class: {class_name}
Subject: {subject}

Student preferences:
- Level: {level}
- Tone: {tone}
- Learning style: {learning_style}
- Response length: {response_length}
- Include example: {include_example}
- Common mistakes to address: {common_mistakes}

Rules:
- If the student asks a follow-up based on previous answers, use prior context to answer.
- Teach at {level} level. Be {tone}. Use {learning_style} style.
- Response length MUST be {response_length}. {"Include ONE brief example only." if include_example else "Do NOT add examples."}
- Be encouraging. Gently address common mistakes if present.
- If the student provides new facts in previous queries, incorporate them when relevant.
"""

    if response_length == "very short":
        full_query += "\nCRITICAL: Give a VERY SHORT answer (2-4 sentences max). No long explanations.\n"
    elif response_length == "short":
        full_query += "\nKeep the answer SHORT (one short paragraph).\n"

    # -----------------------------
    # Get LLM response
    # -----------------------------
    result = student_agent.ask(
        query=full_query,
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

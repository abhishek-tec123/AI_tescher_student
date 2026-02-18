import re
import json
from threading import Lock
from studentProfileDetails.summrizeStdConv import summarize_text_with_groq
from studentProfileDetails.agents.studyPlane import extract_topic_from_sentence
from studentProfileDetails.agents.rl_optimizer import RLOptimizer


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

Conversation handling rules:
- Student inputs may be questions OR general information.
- If the student provides general information about themselves,
  their situation, or their understanding, acknowledge it briefly.
- Do NOT reject general information for lacking academic content.
- Store acknowledged information implicitly through the conversation.

Context usage rules:
- Treat the previous conversation as reliable context.
- If the answer to the current input is already present in the
  conversation history, respond using that information directly.
- Do NOT say information is unavailable if it appears earlier.
- CRITICAL: For personal questions (name, preferences, info shared),
  ALWAYS search the conversation history first and use that information.
- If a student asks "what is my name" or similar, look for where they
  previously told you their name and answer directly.

Response rules:
- Match the student's preferences strictly.
- Keep responses concise when requested.
- Answer naturally and directly when no explanation is required.
- For personal questions, be direct and use the context information.

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

    level = student_profile.get("level", "basic")
    tone = student_profile.get("tone", "friendly")
    learning_style = student_profile.get("learning_style", "step-by-step")
    response_length = student_profile.get("response_length", "long")
    include_example = student_profile.get("include_example", True)
    common_mistakes = student_profile.get("common_mistakes", [])

    prompt = f"""
{base_prompt}

You are an expert and supportive school teacher.

CLASS: {class_name}
SUBJECT: {subject}
DETECTED CONFUSION: {confusion_type}

STUDENT PROFILE:
- Level: {level}
- Tone: {tone}
- Learning style: {learning_style}
- Response length: {response_length}
- Include example: {include_example}
- Common mistakes: {common_mistakes}

IMPORTANT INSTRUCTIONS:

1. Answer ONLY what the student asked.
2. Do NOT introduce future or unrelated topics.
3. Keep explanation appropriate for a {level} student.
4. Follow tone: {tone}.
5. If confusion exists, gently correct it.
6. Follow learning style: {learning_style}.
7. Provide slightly deeper conceptual clarity when appropriate.
8. Do NOT use labels like "Subtopics:" or markdown formatting.
9. Use clean plain text with this structure:

Topic: <Main topic>

- Key idea
  Clear and slightly deep explanation

- Key idea
  Clear and slightly deep explanation

10. If include_example is True, include one simple example naturally.
11. If common mistakes are provided, include one brief correction section written as:
   Common mistake
   Short clarification

12. End with a short encouraging sentence.

Keep the response structured but natural.
Avoid robotic formatting.
"""

    if session_context:
        prompt += f"\nPrevious conversation:\n{session_context}\n"

    # Response length control (updated: very long, long, short only)
    if response_length == "very long":
        prompt += "\nProvide comprehensive detailed explanation with examples and context.\n"
    elif response_length == "short":
        prompt += "\nKeep response concise but structured in one short explanation.\n"
    else:  # long (default)
        prompt += "\nProvide detailed but focused explanation.\n"

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
    personal_info_summary = ""
    
    if context:
        # Extract personal information for easy access
        personal_info = []
        for turn in context:
            if isinstance(turn, dict):
                query = turn.get('query', '').lower()
                # Handle both string responses and dict responses
                response_data = turn.get('response', '')
                if isinstance(response_data, dict):
                    response = response_data.get('response', '')
                else:
                    response = response_data
                
                # Look for personal information sharing
                if any(phrase in query for phrase in ['my name is', 'i am', 'i\'m', 'my favorite', 'i like', 'i dislike']):
                    personal_info.append(f"Student shared: {turn.get('query','')}")
                
                session_history_text += (
                    f"Previous Q: {turn.get('query','')}\n"
                    f"Previous A: {response}\n"
                )
            elif isinstance(turn, str):
                session_history_text += f"{turn}\n"
        
        # Add personal info summary at the beginning for emphasis
        if personal_info:
            personal_info_summary = "\nIMPORTANT PERSONAL INFORMATION SHARED BY STUDENT:\n" + "\n".join(personal_info) + "\n\n"

    # -----------------------------
    # Build final prompt context
    # -----------------------------
    full_context = personal_info_summary + session_history_text

    # -----------------------------
    # RL-based Query Optimization
    # -----------------------------
    optimizer = RLOptimizer()
    state = optimizer.define_state(query=query, context_chunks=[], student_profile=student_profile)
    top_k = 10
    
    # Small RL loop to refine query/retrieval (max 2 steps for latency)
    for _ in range(2):
        action = optimizer.select_action(state)
        state["previous_actions"].append(action)
        
        if action == "rewrite_query":
            state["current_query"] = optimizer.rewrite_query(state["current_query"])
        elif action == "expand_context":
            top_k += 5
        elif action == "generate_response":
            break
            
    # Final prompt still uses session context and diagnosis
    full_prompt = build_teacher_prompt(
        student_profile=student_profile,
        class_name=class_name,
        subject=subject,
        confusion_type=confusion_type,
        session_context=full_context
    )

    full_prompt += f"\nCurrent Question:\n{state['current_query']}\n"

    # -----------------------------
    # Ask LLM (with RL-optimized parameters)
    # -----------------------------
    result = student_agent.ask(
        query=full_prompt,
        class_name=class_name,
        subject=subject,
        student_profile=student_profile,
        top_k=top_k
    )

    if isinstance(result, dict):
        response = result.get("response", "")
        quality_scores = result.get("quality_scores", {})
    else:
        response = result or ""
        quality_scores = {}

    # -----------------------------
    # Attach RL Metadata
    # -----------------------------
    rl_metadata = {
        "trajectory": state["previous_actions"],
        "optimized_query": state["current_query"],
        "top_k": top_k
    }

    return {
        "response": response,
        "confusion_type": confusion_type,
        "profile": student_profile,
        "quality_scores": quality_scores,
        "rl_metadata": rl_metadata
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

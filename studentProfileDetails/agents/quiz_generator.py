import json
import re
from typing import List, Dict, Any

from studentProfileDetails.summrizeStdConv import summarize_text_with_groq, extract_text_from_history

# -------------------------------------------------
# JSON Extraction (robust against bad LLM output)
# -------------------------------------------------
def extract_json_from_text(text: str) -> dict:
    """
    Extracts the first valid JSON object or array from LLM output.
    Always returns a dict with a 'quiz' key.
    """

    # 1️⃣ Direct JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "quiz" in parsed:
            return parsed
        if isinstance(parsed, list):
            return {"quiz": parsed}
    except json.JSONDecodeError:
        pass

    # 2️⃣ Try extracting JSON array
    array_match = re.search(r"\[\s*{.*?}\s*\]", text, re.DOTALL)
    if array_match:
        try:
            parsed = json.loads(array_match.group())
            if isinstance(parsed, list):
                return {"quiz": parsed}
        except json.JSONDecodeError:
            pass

    # 3️⃣ Try extracting JSON object
    object_match = re.search(r"\{.*\}", text, re.DOTALL)
    if object_match:
        try:
            parsed = json.loads(object_match.group())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    print("⚠️ WARNING: Failed to extract JSON from LLM output")
    return {"quiz": []}

# -------------------------------------------------
# Validation & Cleanup
# -------------------------------------------------
def normalize_quiz_items(
    quiz: List[Dict[str, Any]],
    expected_count: int
) -> List[Dict[str, Any]]:
    """
    Ensures:
    - exactly expected_count questions
    - 4 options
    - answer exists in options
    """

    valid_questions = []

    for q in quiz:
        if not isinstance(q, dict):
            continue

        if not all(k in q for k in ["question", "options", "answer"]):
            continue

        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            continue

        if q["answer"] not in q["options"]:
            continue

        valid_questions.append({
            "question": q["question"].strip(),
            "options": [opt.strip() for opt in q["options"]],
            "answer": q["answer"].strip()
        })

        if len(valid_questions) == expected_count:
            break

    return valid_questions

# -------------------------------------------------
# Main Quiz Generator
# -------------------------------------------------
def generate_quiz_from_history(
    history: list,
    subject: str,
    topic: str | None = None,
    num_questions: int = 5
) -> dict:
    """
    Generates a multiple-choice quiz ONCE.

    Returns:
    {
        "subject": str,
        "topic": str | None,
        "quiz": [ {question, options, answer} ],
        "current_question": {
            "question_number": int,
            "total_questions": int,
            "question": str,
            "options": list[str],
            "answer": str
        }
    }
    """

    # Safety fallback
    if not history and not topic:
        return {
            "subject": subject,
            "topic": topic,
            "quiz": [],
            "current_question": None
        }

    conversation_text = extract_text_from_history(history) if history else ""

    # Filter history to focus on topic-relevant conversations if topic is specified
    if topic and history:
        topic_keywords = topic.lower().split()
        topic_relevant_history = []
        
        for item in history:
            item_text = f"{item.get('query', '')} {item.get('response', '')}".lower()
            # Check if any topic keywords appear in the conversation
            if any(keyword in item_text for keyword in topic_keywords if len(keyword) > 2):
                topic_relevant_history.append(item)
        
        # If we found topic-relevant history, use it; otherwise use all history
        if topic_relevant_history:
            conversation_text = extract_text_from_history(topic_relevant_history)
            print(f"🎯 Using {len(topic_relevant_history)} topic-relevant conversations out of {len(history)} total")

    topic_instruction = (
        f"The quiz MUST be strictly about this topic: {topic}.\n"
        f"Focus on concepts discussed in the student's learning history.\n"
        if topic else
        "The quiz should be based on the student's recent learning conversations.\n"
    )

    prompt = f"""
You are an intelligent exam generator that creates personalized quizzes based on student learning history.

CRITICAL RULES (DO NOT BREAK):
- Generate EXACTLY {num_questions} multiple-choice questions
- Return ONLY valid JSON
- NO markdown
- NO explanations
- NO text before or after JSON
- Each question MUST include:
  - question (string)
  - options (array of exactly 4 strings)
  - answer (string matching one option)

QUIZ GENERATION GUIDELINES:
- Base questions on the student's actual learning conversations
- Focus on concepts the student has discussed or struggled with
- If topic is specified, ALL questions must be about that topic
- Use appropriate difficulty level based on conversation context
- Create questions that test understanding, not just memorization

{topic_instruction}

Student Learning Context:
{conversation_text}

JSON FORMAT (ONLY THIS):
{{
  "quiz": [
    {{
      "question": "Question text",
      "options": ["A", "B", "C", "D"],
      "answer": "A"
    }}
  ]
}}
"""

    raw_output = summarize_text_with_groq(
        text=conversation_text if conversation_text else topic,
        prompt=prompt
    )

    parsed = extract_json_from_text(raw_output)

    quiz_raw = parsed.get("quiz", [])
    quiz_clean = normalize_quiz_items(quiz_raw, num_questions)

    # Hard safety check
    if len(quiz_clean) != num_questions:
        print(
            f"⚠️ WARNING: Expected {num_questions} questions, "
            f"got {len(quiz_clean)}"
        )

    # Prepare current question (first question)
    current_question = None
    if quiz_clean:
        first_q = quiz_clean[0]
        current_question = {
            "question_number": 1,
            "total_questions": len(quiz_clean),
            "question": first_q["question"],
            "options": first_q["options"],
            "answer": first_q["answer"]  # ✅ Included answer
        }

    return {
        "subject": subject,
        "topic": topic,
        "quiz": quiz_clean,
        "current_question": current_question
    }

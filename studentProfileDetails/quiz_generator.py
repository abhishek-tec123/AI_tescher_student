import json
import re

def extract_json_from_text(text: str) -> dict:
    """
    Extracts the first valid JSON object or array from LLM output.
    Returns empty quiz dict if invalid JSON is found.
    """
    # Try direct load first
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"quiz": parsed if isinstance(parsed, list) else []}
    except json.JSONDecodeError:
        pass

    # Try to find JSON array first (for quiz arrays) - find outermost complete array
    bracket_count = 0
    array_start_idx = -1
    for i, char in enumerate(text):
        if char == '[':
            if bracket_count == 0:
                array_start_idx = i
            bracket_count += 1
        elif char == ']':
            bracket_count -= 1
            if bracket_count == 0 and array_start_idx != -1:
                try:
                    parsed = json.loads(text[array_start_idx:i+1])
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return {"quiz": parsed}
                except json.JSONDecodeError:
                    continue

    # Extract JSON objects (handle nested structures properly)
    # Find the outermost complete JSON object
    brace_count = 0
    start_idx = -1
    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                try:
                    return json.loads(text[start_idx:i+1])
                except json.JSONDecodeError:
                    continue

    # If all fail, return empty quiz instead of raising
    print("⚠️ Warning: Could not extract JSON from LLM output. Returning empty quiz.")
    return {"quiz": []}

from summrizeStdConv import summarize_text_with_groq, extract_text_from_history

def generate_quiz_from_history(
    history: list,
    subject: str,
    topic: str | None = None,
    num_questions: int = 5
) -> dict:

    if not history and not topic:
        return {"subject": subject, "topic": topic, "quiz": []}

    text = extract_text_from_history(history) if history else ""

    topic_instruction = (
        f"The quiz MUST be strictly about the topic: {topic}.\n"
        if topic else
        "The quiz should be based on the student's recent learning.\n"
    )

    prompt = f"""
You are a teacher AI.

CRITICAL: Generate EXACTLY {num_questions} multiple-choice questions. You MUST return {num_questions} questions, not just one.

{topic_instruction}

RULES:
- Return ONLY valid JSON
- NO markdown formatting (no ```json or ```)
- NO explanations or text before/after JSON
- Generate EXACTLY {num_questions} questions
- Each question must include:
  - question (string)
  - options (array of exactly 4 strings)
  - answer (string that matches one of the options)

REQUIRED JSON FORMAT:
{{
  "quiz": [
    {{
      "question": "Question 1 text here",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": "Option A"
    }},
    {{
      "question": "Question 2 text here",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": "Option B"
    }},
    {{
      "question": "Question 3 text here",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": "Option C"
    }},
    {{
      "question": "Question 4 text here",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": "Option A"
    }},
    {{
      "question": "Question 5 text here",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": "Option B"
    }}
  ]
}}

Conversation (for context only):
{text}
"""

    raw_output = summarize_text_with_groq(
        text=text if text else topic,
        prompt=prompt
    )

    quiz_json = extract_json_from_text(raw_output)
    print("=== Quiz Raw Output ===")
    print(json.dumps(quiz_json, indent=3))
    
    # Handle different response formats
    quiz_list = []
    
    # Case 1: Correct format with "quiz" key
    if "quiz" in quiz_json:
        quiz_list = quiz_json["quiz"]
        if not isinstance(quiz_list, list):
            quiz_list = []
    
    # Case 2: Direct array of questions (no "quiz" wrapper)
    elif isinstance(quiz_json, list):
        quiz_list = quiz_json
    
    # Case 3: Single question object (wrap it in array)
    elif isinstance(quiz_json, dict) and "question" in quiz_json:
        quiz_list = [quiz_json]
        print(f"⚠️ Warning: LLM returned only 1 question instead of {num_questions}. Wrapping in array.")
    
    # Case 4: Try to find questions in nested structure
    else:
        # Look for any array that might contain questions
        for key, value in quiz_json.items():
            if isinstance(value, list) and len(value) > 0:
                # Check if first item looks like a question
                if isinstance(value[0], dict) and "question" in value[0]:
                    quiz_list = value
                    break
    
    # Validate and ensure we have questions
    if not quiz_list:
        print(f"⚠️ Warning: No questions found in LLM output. Expected {num_questions} questions.")
    
    # Ensure all items have required fields
    validated_quiz = []
    for q in quiz_list:
        if isinstance(q, dict) and "question" in q and "options" in q and "answer" in q:
            validated_quiz.append(q)
    
    if len(validated_quiz) < num_questions:
        print(f"⚠️ Warning: Only {len(validated_quiz)} valid questions found, expected {num_questions}.")
    
    print(f"=== Final Quiz ({len(validated_quiz)} questions) ===")
    print(json.dumps(validated_quiz, indent=3))
    
    return {
        "subject": subject,
        "topic": topic,
        "quiz": validated_quiz
    }


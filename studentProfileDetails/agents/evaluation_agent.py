# import os
# import json
# from dotenv import load_dotenv
# from langchain_groq import ChatGroq
# from langchain_core.messages import HumanMessage

# # --------------------------------------------------
# # Load environment
# # --------------------------------------------------
# load_dotenv()

# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# if not GROQ_API_KEY:
#     raise ValueError("GROQ_API_KEY is not set in environment variables.")

# # --------------------------------------------------
# # Evaluator LLM (STRICT, LOW TEMP)
# # --------------------------------------------------
# evaluator_llm = ChatGroq(
#     model_name="llama-3.1-8b-instant",
#     api_key=GROQ_API_KEY,
#     temperature=0.1,   # 🔴 CRITICAL: judging must be cold
#     max_tokens=400,
# )

# # --------------------------------------------------
# # Evaluation Prompt Template (STRICT)
# # --------------------------------------------------
# EVALUATION_PROMPT = """
# You are a STRICT educational response evaluator.

# IMPORTANT:
# - You did NOT generate the assistant response.
# - You are an external reviewer.
# - Do NOT default to mid-range scores.
# - Use the FULL score range when justified.
# - Penalize mismatches with the student profile.
# - If the response is TOO BASIC for an ADVANCED student,
#   personalization MUST be BELOW 0.4.
# - Be fair, but do not be lenient.

# Return ONLY valid JSON. No extra text.

# --------------------------------------------------
# SCORING GUIDELINES (0.0 – 1.0)
# --------------------------------------------------

# clarity:
# - Is the explanation easy to follow and well-structured?
# - Is it concise and aligned with desired response length?

# correctness:
# - Is the response factually correct?
# - Simplified explanations are OK IF NOT misleading.

# personalization:
# - Does the response match the student's level, tone,
#   learning style, and length constraints?
# - Penalize generic or beginner-level explanations
#   given to advanced students.

# pedagogical_value:
# - Does the response meaningfully help learning?
# - Does it provide insight, structure, or conceptual clarity?
# - Generic encouragement without substance should score LOW.

# --------------------------------------------------
# CONTEXT
# --------------------------------------------------

# Student Query:
# {query}

# Subject:
# {subject}

# Student Profile:
# - Level: {level}
# - Learning Style: {learning_style}
# - Prefers Examples: {include_example}
# - Tone Preference: {tone}
# - Desired Response Length: {response_length}

# Detected Confusion Type:
# {confusion_type}

# Assistant Response:
# {response}

# --------------------------------------------------
# OUTPUT FORMAT (STRICT)
# --------------------------------------------------

# Return JSON EXACTLY in this format:

# {{
#   "scores": {{
#     "clarity": float,
#     "correctness": float,
#     "personalization": float,
#     "pedagogical_value": float
#   }},
#   "overall": float,
#   "feedback": "short, constructive, actionable feedback"
# }}

# Rules:
# - Overall score MUST be the average of the four scores
# - Use decimals like 0.35, 0.60, 0.85
# - Do NOT add any text outside the JSON
# """

# # --------------------------------------------------
# # Public Evaluation Function
# # --------------------------------------------------
# def evaluate_response(
#     *,
#     query: str,
#     response: str,
#     subject: str,
#     profile: dict,
#     confusion_type: str | None = None,
# ):
#     """
#     Evaluates a generated tutoring response and returns structured scores.
#     """

#     prompt = EVALUATION_PROMPT.format(
#         query=query,
#         subject=subject,
#         level=profile.get("level", "unknown"),
#         learning_style=profile.get("learning_style", "unknown"),
#         include_example=profile.get("include_example", False),
#         tone=profile.get("tone", "neutral"),
#         response_length=profile.get("response_length", "unspecified"),
#         confusion_type=confusion_type or "None",
#         response=response,
#     )

#     message = HumanMessage(content=prompt)

#     try:
#         result = evaluator_llm.invoke([message])
#         raw_output = result.content.strip()

#         evaluation = json.loads(raw_output)

#         # ---- Safety validation ----
#         scores = evaluation.get("scores", {})
#         if not isinstance(scores, dict) or len(scores) != 4:
#             raise ValueError("Invalid score structure")

#         # Recompute overall to enforce rule
#         evaluation["overall"] = round(
#             sum(float(v) for v in scores.values()) / 4, 2
#         )

#         return evaluation

#     except Exception as e:
#         # ---- Hard fallback (never crash prod) ----
#         return {
#             "scores": {
#                 "clarity": 0.5,
#                 "correctness": 0.5,
#                 "personalization": 0.3,
#                 "pedagogical_value": 0.4,
#             },
#             "overall": 0.43,
#             "feedback": f"Evaluation failed; fallback used ({str(e)})"
#         }

import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

# --------------------------------------------------
# Load environment
# --------------------------------------------------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set in environment variables.")

# --------------------------------------------------
# Evaluator LLM (STRICT, LOW TEMP)
# --------------------------------------------------
evaluator_llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    api_key=GROQ_API_KEY,
    temperature=0.1,   # judging must be cold
    max_tokens=400,
)

# --------------------------------------------------
# Evaluation Prompt Template (SCORES ONLY)
# --------------------------------------------------
EVALUATION_PROMPT = """
You are a STRICT educational response evaluator.

IMPORTANT:
- You did NOT generate the assistant response.
- You are an external reviewer.
- Do NOT default to mid-range scores.
- Use the FULL score range when justified.
- Penalize mismatches with the student profile.
- If the response is TOO BASIC for an ADVANCED student,
  personalization MUST be BELOW 0.4.
- Be fair, but do not be lenient.

Return ONLY valid JSON. No extra text.

--------------------------------------------------
SCORING GUIDELINES (0.0 – 1.0)
--------------------------------------------------

clarity:
- Is the explanation easy to follow and well-structured?
- Is it concise and aligned with desired response length?

correctness:
- Is the response factually correct?
- Simplified explanations are OK IF NOT misleading.

personalization:
- Does the response match the student's level, tone,
  learning style, and length constraints?
- Penalize generic or beginner-level explanations
  given to advanced students.

pedagogical_value:
- Does the response meaningfully help learning?
- Does it provide insight, structure, or conceptual clarity?

critical_confidence:
- Is the answer confident and decisive when appropriate?
- Penalize unnecessary hedging.

model_certainty:
- Is certainty justified by content?
- Penalize unjustified confidence or excessive doubt.

rag_relevance:
- If external context or retrieval is implied, is it used meaningfully?
- Penalize generic answers when context-specific grounding is expected.

answer_completeness:
- Does the response fully address all parts of the query?
- Penalize partial or shallow answers.

hallucination_risk:
- Likelihood of fabricated facts or unsupported claims.
- 1.0 = very low risk, 0.0 = high risk.

--------------------------------------------------
CONTEXT
--------------------------------------------------

Student Query:
{query}

Subject:
{subject}

Student Profile:
- Level: {level}
- Learning Style: {learning_style}
- Prefers Examples: {include_example}
- Tone Preference: {tone}
- Desired Response Length: {response_length}

Detected Confusion Type:
{confusion_type}

Assistant Response:
{response}

--------------------------------------------------
OUTPUT FORMAT (STRICT)
--------------------------------------------------

Return JSON EXACTLY in this format:

{{
  "pedagogical_value": float,
  "critical_confidence": float,
  "rag_relevance": float,
  "answer_completeness": float,
  "hallucination_risk": float
}}

Rules:
- Scores must be between 0.0 and 1.0
- Use decimals like 0.35, 0.60, 0.85
- Do NOT add any text outside the JSON
"""

# --------------------------------------------------
# Public Evaluation Function (SCORES ONLY)
# --------------------------------------------------
def evaluate_response(
    *,
    query: str,
    response: str,
    subject: str,
    profile: dict,
    confusion_type: str | None = None,
):
    """
    Evaluates a generated tutoring response and returns ONLY scores.
    """

    prompt = EVALUATION_PROMPT.format(
        query=query,
        subject=subject,
        level=profile.get("level", "unknown"),
        learning_style=profile.get("learning_style", "unknown"),
        include_example=profile.get("include_example", False),
        tone=profile.get("tone", "neutral"),
        response_length=profile.get("response_length", "unspecified"),
        confusion_type=confusion_type or "None",
        response=response,
    )

    message = HumanMessage(content=prompt)

    EXPECTED_KEYS = {
        # "clarity",
        # "correctness",
        # "personalization",
        # "model_certainty",
        "pedagogical_value",
        "critical_confidence",
        "rag_relevance",
        "answer_completeness",
        "hallucination_risk",
    }

    try:
        result = evaluator_llm.invoke([message])
        raw_output = result.content.strip()
        scores = json.loads(raw_output)

        if not isinstance(scores, dict):
            raise ValueError("Scores is not a dict")

        missing = EXPECTED_KEYS - scores.keys()
        extra = scores.keys() - EXPECTED_KEYS

        if missing:
            raise ValueError(f"Missing score keys: {missing}")
        if extra:
            raise ValueError(f"Unexpected score keys: {extra}")

        # ensure all values are floats
        scores = {k: float(v) for k, v in scores.items()}

        return scores

    except Exception:
        # ---- Hard fallback (schema-safe) ----
        return {
            # "clarity": 0.5,
            # "correctness": 0.5,
            # "personalization": 0.3,
            "pedagogical_value": 0.4,
            "critical_confidence": 0.4,
            # "model_certainty": 0.4,
            "rag_relevance": 0.3,
            "answer_completeness": 0.4,
            "hallucination_risk": 0.5,
        }

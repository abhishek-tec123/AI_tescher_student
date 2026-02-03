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
    temperature=0.0,          # critical for judging
    max_tokens=400,
)

# --------------------------------------------------
# Evaluation Prompt Template
# --------------------------------------------------
EVALUATION_PROMPT = """
You are an educational response evaluator.

IMPORTANT:
- You did NOT generate the assistant response.
- Be fair and calibrated, not overly harsh.
- Do NOT give a score of 0.0 unless the response is clearly wrong or misleading.

Evaluate the assistant's response using the rubric below.
Return ONLY valid JSON. No extra text.

--------------------------------------------------
SCORING GUIDELINES (0.0 – 1.0)
--------------------------------------------------

clarity:
- Is the explanation easy to follow and well-structured?
- Does it avoid unnecessary ambiguity?

correctness:
- Is the response factually correct for the subject?
- A simplified explanation is STILL correct if it is not misleading.
- Do NOT penalize correctness for being basic or brief.
- Only give a low score if facts are wrong or misleading.

personalization:
- Does the response respect the student's profile (level, tone, learning style)?
- Penalize if the response ignores advanced level, step-by-step style, or length constraints.

pedagogical_value:
- Does the response help the student learn?
- Consider explanations, scaffolding, examples, or conceptual framing.
- A short but clear explanation can still score moderately well.

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

Return JSON in EXACT format:

{{
  "scores": {{
    "clarity": float,
    "correctness": float,
    "personalization": float,
    "pedagogical_value": float
  }},
  "overall": float,
  "feedback": "short, constructive, actionable feedback"
}}

Rules:
- Overall score MUST be the average of the four scores
- Use decimals like 0.65 or 0.80
- Do not add any text outside the JSON
"""

# --------------------------------------------------
# Public Evaluation Function
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
    Evaluates a generated tutoring response and returns structured scores.
    """

    prompt = EVALUATION_PROMPT.format(
        query=query,
        subject=subject,
        level=profile.get("level", "unknown"),
        learning_style=profile.get("learning_style", "unknown"),
        include_example=profile.get("include_example", False),
        tone=profile.get("tone", "neutral"),
        confusion_type=confusion_type or "None",
        response_length=profile.get("response_length"),
        response=response,
    )

    message = HumanMessage(content=prompt)

    try:
        result = evaluator_llm.invoke([message])
        raw_output = result.content.strip()

        evaluation = json.loads(raw_output)

        # ---- Safety validation ----
        scores = evaluation.get("scores", {})
        if len(scores) != 4:
            raise ValueError("Invalid score structure")

        evaluation["overall"] = round(
            sum(scores.values()) / len(scores), 2
        )

        return evaluation

    except Exception as e:
        # ---- Hard fallback (never crash prod) ----
        return {
            "scores": {
                "clarity": 0.5,
                "correctness": 0.5,
                "personalization": 0.5,
                "pedagogical_value": 0.5,
            },
            "overall": 0.5,
            "feedback": f"Evaluation failed, fallback used ({str(e)})"
        }

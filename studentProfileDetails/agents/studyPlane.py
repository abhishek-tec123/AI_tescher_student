from studentProfileDetails.summrizeStdConv import summarize_text_with_groq

# -----------------------------
# Topic Extraction (LLM-based)
# -----------------------------
def extract_topic_from_sentence(sentence: str) -> str:
    """
    Extracts the main learning topic from a student's sentence.
    """

    prompt = """
Extract ONLY the main learning topic from the sentence.

Rules:
- Return only the topic
- No explanation
- No punctuation
- 1 to 3 words maximum

Examples:
"I want to learn friction" -> friction
"Teach me Newton's laws" -> Newton's laws
"I want help with algebra equations" -> algebra equations
"""

    topic = summarize_text_with_groq(
        text=sentence,
        prompt=prompt
    )

    return topic.strip()


# -----------------------------
# Study Plan Generator
# -----------------------------
def generate_study_plan_with_subtopics(
    student_sentence: str,
    student_profile: dict | None = None,
    explicit_topic: str | None = None
) -> str:
    """
    Generates a step-by-step natural language study plan.
    """

    # 🔑 Decide topic source
    topic = explicit_topic.strip() if explicit_topic else extract_topic_from_sentence(student_sentence)

    # Student profile hint
    profile_hint = ""
    if student_profile:
        for k, v in student_profile.items():
            profile_hint += f"- {k}: {v}\n"

    prompt = f"""
You are a friendly and experienced school teacher.

The student wants to learn: "{topic}"

Create a clear step-by-step study plan in plain text.

STRICT RULES:
- Assume the student is a beginner
- First explain how the student should START
- Then list subtopics in learning order
- Briefly explain each subtopic
- Do NOT jump to advanced topics early
- Do NOT use numbering like 1., 2., 3.
- Do NOT use markdown or bullet symbols
- Write naturally like a teacher talking to a student
- End by explaining what the student will be able to do after finishing

Student Profile:
{profile_hint}
"""

    response = summarize_text_with_groq(
        text=topic,
        prompt=prompt
    )
    print("=== study plan ===", response)
    return response.strip()

from studentAgent.student_agent import StudentAgent
from studentProfileDetails.agents.studyPlane import extract_topic_from_sentence

def plan_aware_chat(
    student_agent: StudentAgent,
    query: str,
    existing_plan: str | None,
    class_name: str,
    subject: str,
    student_profile: dict
) -> str:
    """
    Handles plan-aware chat: 
    - Uses study plan if question topic exists in plan
    - Otherwise, falls back to normal teacher chat
    """
    use_plan = False

    if existing_plan:
        question_topic = extract_topic_from_sentence(query).lower()
        if question_topic and question_topic in existing_plan.lower():
            use_plan = True

    if use_plan:
        prompt = f"""
You are a teacher strictly following a step-by-step study plan.

STUDY PLAN:
{existing_plan}

RULES:
- Answer ONLY what is required
- Do NOT introduce future topics
- Explain only the current topic in detail
- Be student-friendly
- Assume student is at the beginning

Student question:
{query}
"""
    else:
        prompt = query

    response = student_agent.ask(
        query=prompt,
        class_name=class_name,
        subject=subject,
        student_profile=student_profile
    )

    return response

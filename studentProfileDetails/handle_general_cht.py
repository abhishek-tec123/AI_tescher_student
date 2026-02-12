import re
from studentProfileDetails.generate_response_with_groq import generate_response_with_groq

def is_greeting(query: str) -> bool:
    q = query.lower().strip()
    patterns = [
        r"^hi\b",
        r"^hello\b",
        r"^hey\b",
        r"^good (morning|afternoon|evening)\b",
    ]
    return any(re.search(p, q) for p in patterns)


def is_general_chat(query: str) -> bool:
    q = query.lower().strip()
    patterns = [
        r"\bmy name is\b",
        r"\bi am\b",
        r"\bi'm\b",
        r"\bhow are you\b",
        r"\bwhat is my name\b",
        r"\bwhat's my name\b",
        r"\btell me about\b",
        r"\bdo you remember\b",
    ]
    return any(re.search(p, q) for p in patterns)

# -------------------------------------------------
# Context Builder
# -------------------------------------------------
def build_context_text(context):
    if not context:
        return None

    text = "Previous conversation:\n"
    for turn in context:
        query = turn.get("query", "")
        response_data = turn.get("response", "")

        if isinstance(response_data, dict):
            response_text = response_data.get("response", "")
        else:
            response_text = response_data

        text += f"Q: {query}\nA: {response_text}\n"

    return text
# -------------------------------------------------
# Greeting Handler
# -------------------------------------------------
def handle_greeting_chat(*, payload, student_manager, profile):
    response = generate_response_with_groq(
        query=payload.query,
        system_prompt=(
            "You are a friendly student assistant.\n"
            "Respond warmly and briefly to greetings.\n"
            "Do not ask academic questions unless the student does."
        ),
    )

    conversation_id = student_manager.add_conversation(
        student_id=payload.student_id,
        subject=payload.subject,
        query=payload.query,
        response=response,
        confusion_type="NO_CONFUSION",
        evaluation=None,
    )

    return {
        "response": response,
        "profile": profile,
        "evaluation": None,
        "conversation_id": str(conversation_id),
    }
# -------------------------------------------------
# General (Non-academic) Chat Handler – LLM ONLY
# -------------------------------------------------
def handle_general_chat_llm(
    *, payload, student_manager, profile, context
):
    context_text = build_context_text(context)

    response = generate_response_with_groq(
        query=payload.query,
        context=context_text,
        system_prompt=(
            "You are a friendly student assistant.\n"
            "Rules:\n"
            "- Answer naturally and briefly\n"
            "- Use conversation history for personal info\n"
            "- Do NOT mention systems, databases, or tools\n"
            "- Do NOT teach unless asked\n"
        ),
    )

    conversation_id = student_manager.add_conversation(
        student_id=payload.student_id,
        subject=payload.subject,
        query=payload.query,
        response=response,
        confusion_type="NO_CONFUSION",
        evaluation=None,
    )

    return {
        "response": response,
        "profile": profile,
        "evaluation": None,
        "conversation_id": str(conversation_id),
    }


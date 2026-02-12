from studentProfileDetails.summrizeStdConv import summarize_text_with_groq

def generate_notes(
    topic: str,
    chat_history: list[dict[str, str]] | None = None,
    student_profile: dict | None = None
) -> str:
    history_text = ""
    if chat_history:
        for turn in chat_history:
            history_text += f"Student: {turn['query']}\nTeacher: {turn['response']}\n"

    profile_hint = ""
    if student_profile:
        for k, v in student_profile.items():
            profile_hint += f"- {k}: {v}\n"

    prompt = f"""
You are a teacher writing clean study notes.

RULES:
- Bullet points only using "-"
- No numbering
- No markdown
- Beginner friendly
- Short clear points
- No emojis
- No extra topics

TOPIC:
{topic}

CHAT CONTEXT:
{history_text if history_text else "None"}

STUDENT PROFILE:
{profile_hint}
"""

    response = summarize_text_with_groq(
        text=topic,
        prompt=prompt
    )
    print(response)
    return response.strip()

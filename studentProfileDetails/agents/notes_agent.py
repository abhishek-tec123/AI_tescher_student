from studentProfileDetails.summrizeStdConv import summarize_text_with_groq

def generate_notes(
    topic: str,
    chat_history: list[dict[str, str]] | None = None,
    student_profile: dict | None = None
) -> str:
    history_text = ""
    topic_relevant_history = []
    
    if chat_history:
        # Filter history to focus on topic-relevant conversations
        topic_keywords = topic.lower().split()
        
        for turn in chat_history:
            item_text = f"{turn.get('query', '')} {turn.get('response', '')}".lower()
            # Check if any topic keywords appear in the conversation
            if any(keyword in item_text for keyword in topic_keywords if len(keyword) > 2):
                topic_relevant_history.append(turn)
        
        # Use topic-relevant history if available, otherwise use all history
        history_to_use = topic_relevant_history if topic_relevant_history else chat_history
        
        for turn in history_to_use:
            history_text += f"Student: {turn['query']}\nTeacher: {turn['response']}\n"
        
        if topic_relevant_history:
            print(f"📝 Using {len(topic_relevant_history)} topic-relevant conversations for notes out of {len(chat_history)} total")

    profile_hint = ""
    if student_profile:
        for k, v in student_profile.items():
            profile_hint += f"- {k}: {v}\n"

    prompt = f"""
You are an intelligent teacher creating comprehensive study notes based on student learning conversations.

RULES:
- Bullet points only using "-"
- No numbering
- No markdown
- Beginner friendly but comprehensive
- Short clear points that build understanding
- No emojis
- Focus strictly on the requested topic
- Use insights from student conversations to address common confusion points

TOPIC:
{topic}

STUDENT LEARNING CONVERSATIONS:
{history_text if history_text else "No previous conversations about this topic"}

STUDENT LEARNING PROFILE:
{profile_hint}

INSTRUCTIONS:
- Create notes that address concepts the student has discussed
- Include examples that might clarify confusion points from conversations
- Structure points logically based on how the student learned the topic
- Keep explanations simple but thorough
"""

    response = summarize_text_with_groq(
        text=topic,
        prompt=prompt
    )
    print(response)
    return response.strip()

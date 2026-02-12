import re
from studentProfileDetails.learning_progress import (
    normalize_student_preference,
    update_progress_and_regression,
)
from studentProfileDetails.agents.mainAgent import diagnosis_chat
from studentProfileDetails.agents.quiz_generator import generate_quiz_from_history
from studentProfileDetails.agents.studyPlane import generate_study_plan_with_subtopics
from studentProfileDetails.agents.evaluation_agent import evaluate_response
from studentProfileDetails.handle_general_cht import is_greeting, handle_greeting_chat, handle_general_chat_llm, is_general_chat
# -------------------------------------------------
# Main Chat Intent Handler
# -------------------------------------------------

def handle_chat_intent(
    *,
    student_agent,
    student_manager,
    payload,
    profile,
    context,
):
    # -----------------------------------------
    # Greeting
    # -----------------------------------------
    if is_greeting(payload.query):
        return handle_greeting_chat(
            payload=payload,
            student_manager=student_manager,
            profile=profile,
        )

    # -----------------------------------------
    # General / Personal Chat (NO VECTOR DB)
    # -----------------------------------------
    if is_general_chat(payload.query):
        return handle_general_chat_llm(
            payload=payload,
            student_manager=student_manager,
            profile=profile,
            context=context,
        )

    # -----------------------------------------
    # Update progression BEFORE academic response
    # -----------------------------------------
    profile = update_progress_and_regression(
        student_manager,
        payload.student_id,
        payload.subject,
        profile,
    )
    print("Student Profile : ", profile)
    # -----------------------------------------
    # Prepare academic history
    # -----------------------------------------
    history_context = [
        f"Q: {turn['query']}\nA: {turn['response']}"
        for turn in context
    ]

    # -----------------------------------------
    # Academic Tutor Flow (Vector DB + Agent)
    # -----------------------------------------
    chat = diagnosis_chat(
        student_agent,
        payload.query,
        payload.class_name,
        payload.subject,
        profile,
        context=history_context,
    )

    response = chat["response"]
    confusion_type = chat.get("confusion_type")

    # -----------------------------------------
    # Evaluate academic response
    # -----------------------------------------
    evaluation = evaluate_response(
        query=payload.query,
        response=response,
        subject=payload.subject,
        profile=profile,
        confusion_type=confusion_type,
    )

    # -----------------------------------------
    # Persist profile
    # -----------------------------------------
    student_manager.update_subject_preference(
        payload.student_id,
        payload.subject,
        {
            "confusion_counter": profile["confusion_counter"],
            "common_mistakes": profile["common_mistakes"],
            "learning_style": profile["learning_style"],
            "level": profile["level"],
            "tone": profile["tone"],
            "response_length": profile["response_length"],
            "include_example": profile["include_example"],
        },
    )

    # -----------------------------------------
    # Store conversation
    # -----------------------------------------
    conversation_id = student_manager.add_conversation(
        student_id=payload.student_id,
        subject=payload.subject,
        query=payload.query,
        response=response,
        confusion_type=confusion_type,
        evaluation=evaluation,
    )

    # -----------------------------------------
    # Update progression AFTER conversation
    # -----------------------------------------
    profile = update_progress_and_regression(
        student_manager,
        payload.student_id,
        payload.subject,
        profile,
    )

    # -----------------------------------------
    # Reload normalized profile
    # -----------------------------------------
    profile = normalize_student_preference(
        student_manager.get_or_create_subject_preference(
            payload.student_id, payload.subject
        )
    )

    return {
        "response": response,
        "profile": profile,
        "evaluation": evaluation,
        "conversation_id": str(conversation_id),
    }


# -------------------------------------------------
# Quiz Intent
# -------------------------------------------------

def handle_quiz_intent(*, student_manager, payload, topic):
    history = student_manager.get_conversation_history(
        payload.student_id,
        payload.subject,
        limit=20,
    )

    return generate_quiz_from_history(
        history=history,
        subject=payload.subject,
        topic=topic,
        num_questions=5,
    )

# -------------------------------------------------
# Study Plan Intent
# -------------------------------------------------

def handle_study_plan_intent(*, payload, profile, topic):
    plan_text = generate_study_plan_with_subtopics(
        student_sentence=payload.query,
        student_profile=profile,
        explicit_topic=topic,
    )

    return {
        "study_plan": plan_text,
        "subject": payload.subject,
        "topic": topic,
    }

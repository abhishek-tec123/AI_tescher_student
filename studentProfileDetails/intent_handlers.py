from studentProfileDetails.learning_progress import normalize_student_preference, update_progress_and_regression
from studentProfileDetails.agents.mainAgent import diagnosis_chat
from studentProfileDetails.agents.quiz_generator import generate_quiz_from_history
from studentProfileDetails.agents.studyPlane import generate_study_plan_with_subtopics

from studentProfileDetails.agents.evaluation_agent import evaluate_response

def handle_chat_intent(
    *,
    student_agent,
    student_manager,
    payload,
    profile,
    context  # session-based, user-specific context
):
    # -----------------------------------------
    # Update progression BEFORE response
    # -----------------------------------------
    profile = update_progress_and_regression(
        student_manager,
        payload.student_id,
        payload.subject,
        profile
    )

    # -----------------------------------------
    # Prepare session history for the tutor
    # Only include previous queries and responses
    # -----------------------------------------
    history_context = [f"Q: {turn['query']}\nA: {turn['response']}" for turn in context]

    # -----------------------------------------
    # Generate response (Tutor model) with session context
    # -----------------------------------------
    chat = diagnosis_chat(
        student_agent,
        payload.query,
        payload.class_name,
        payload.subject,
        profile,
        context=history_context  # Pass previous conversation
    )

    response = chat["response"]
    confusion_type = chat.get("confusion_type")

    # -----------------------------------------
    # 🔍 Evaluate response (Evaluator model)
    # -----------------------------------------
    evaluation = evaluate_response(
        query=payload.query,
        response=response,
        subject=payload.subject,
        profile=profile,
        confusion_type=confusion_type
    )

    quality_scores = evaluation.get("scores")
    overall_score = evaluation.get("overall")

    # -----------------------------------------
    # Persist updated profile
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
        }
    )

    # -----------------------------------------
    # Store conversation + evaluation in persistent DB
    # -----------------------------------------
    student_manager.add_conversation(
        student_id=payload.student_id,
        subject=payload.subject,
        query=payload.query,
        response=response,
        confusion_type=confusion_type,
        evaluation=evaluation
    )

    # -----------------------------------------
    # Update progression AFTER conversation
    # -----------------------------------------
    profile = update_progress_and_regression(
        student_manager,
        payload.student_id,
        payload.subject,
        profile
    )

    # -----------------------------------------
    # Reload fresh profile
    # -----------------------------------------
    profile = normalize_student_preference(
        student_manager.get_or_create_subject_preference(
            payload.student_id, payload.subject
        )
    )

    # -----------------------------------------
    # Return response + profile + evaluation
    # -----------------------------------------
    return {
        "response": response,
        "profile": profile,
        "evaluation": evaluation
    }


def handle_quiz_intent(
    *,
    student_manager,
    payload,
    topic
):
    history = student_manager.get_conversation_history(
        payload.student_id,
        payload.subject,
        limit=20
    )

    quiz_result = generate_quiz_from_history(
        history=history,
        subject=payload.subject,
        topic=topic,
        num_questions=5,
    )

    return quiz_result

def handle_study_plan_intent(
    *,
    payload,
    profile,
    topic
):
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

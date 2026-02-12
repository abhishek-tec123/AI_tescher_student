from fastapi.responses import JSONResponse
from studentProfileDetails.learning_progress import normalize_student_preference
from studentProfileDetails.quizHelper import create_quiz_session, get_current_question, handle_quiz_mode
from studentProfileDetails.intent_handlers import handle_chat_intent, handle_study_plan_intent
from studentProfileDetails.agents.mainAgent import detect_intent_and_topic
from studentProfileDetails.agents.quiz_generator import generate_quiz_from_history
from studentProfileDetails.agents.notes_agent import generate_notes

conversation_id = None

def queryRouter(
    *,
    payload,
    student_agent,
    student_manager,
    context_store
):
    # Ensure student exists
    if not student_manager.students.find_one({"_id": payload.student_id}):
        return JSONResponse(
            status_code=404,
            content={"error": "Student not found. Please create student first."}
        )

    # Initialize context
    if payload.student_id not in context_store:
        context_store[payload.student_id] = []

    session_context = context_store[payload.student_id]

    # -----------------------------
    # QUIZ MODE OVERRIDE
    # -----------------------------
    quiz_response = handle_quiz_mode(
        student_id=payload.student_id,
        query=payload.query
    )

    if quiz_response:
        return quiz_response

    # -----------------------------
    # NORMAL MODE
    # -----------------------------
    profile = normalize_student_preference(
        student_manager.get_or_create_subject_preference(
            payload.student_id, payload.subject
        )
    )

    intent_result = detect_intent_and_topic(payload.query)
    intent = intent_result["intent"]
    topic = intent_result.get("topic")
    query = intent_result.get("query")

    response = None
    evaluation = None

    if intent == "CHAT":
        result = handle_chat_intent(
            student_agent=student_agent,
            student_manager=student_manager,
            payload=payload,
            profile=profile,
            context=session_context
        )
        response = result["response"]
        profile = result["profile"]
        evaluation = result["evaluation"]
        conversation_id = result.get("conversation_id")

        session_context.append({
            "query": payload.query,
            "response": response
        })

        context_store[payload.student_id] = session_context[-10:]

    elif intent == "QUIZ":
        quiz_data = generate_quiz_from_history(
            history=session_context,
            subject=payload.subject,
            topic=topic,
            num_questions=5
        )

        if not quiz_data["quiz"]:
            response = "Sorry, I couldn't generate a quiz right now."
        else:
            create_quiz_session(payload.student_id, quiz_data)
            response = {
                "message": "Quiz started!",
                "question": get_current_question(payload.student_id)
            }

    elif intent == "STUDY_PLAN":
        response = handle_study_plan_intent(
            payload=payload,
            profile=profile,
            topic=topic
        )

    elif intent == "NOTES":
        notes = generate_notes(
            topic=topic,
            chat_history=session_context,
            student_profile=profile
        )

        response = {
            "topic": topic,
            "notes": notes
        }

        session_context.append({
            "query": payload.query,
            "response": notes
        })

        context_store[payload.student_id] = session_context[-10:]

    return JSONResponse(
        content={
            "query": query,
            "intent": intent,
            "response": response,
            "profile": profile,
            "quality_scores": evaluation,
            "conversation_id": conversation_id,
            "context_history": context_store[payload.student_id]
        }
    )

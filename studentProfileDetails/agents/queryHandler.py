from fastapi.responses import JSONResponse
from studentProfileDetails.learning_progress import normalize_student_preference
from studentProfileDetails.quizHelper import create_quiz_session, get_current_question, handle_quiz_mode
from studentProfileDetails.intent_handlers import handle_chat_intent, handle_study_plan_intent
from studentProfileDetails.agents.mainAgent import detect_intent_and_topic
from studentProfileDetails.agents.quiz_generator import generate_quiz_from_history
from studentProfileDetails.agents.notes_agent import generate_notes
from studentProfileDetails.summrizeStdConv import update_running_summary


def queryRouter(
    *,
    payload,
    student_agent,
    student_manager,
    context_store
):

    conversation_id = None  # ✅ local variable (thread-safe)
    context_summary = None

    # Ensure student exists
    if not student_manager.students.find_one({"student_id": payload.student_id}):
        return JSONResponse(
            status_code=404,
            content={"error": "Student not found. Please create student first."}
        )

    # Initialize context if not exists
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

    response = None

    # =============================
    # CHAT (🔥 summary only here)
    # =============================
    if intent == "CHAT":
        result = handle_chat_intent(
            student_agent=student_agent,
            student_manager=student_manager,
            payload=payload,
            profile=profile,
            context=session_context
        )

        response = result["response"]
        conversation_id = result.get("conversation_id")

        new_entry = {
            "conversation_id": str(conversation_id) if conversation_id else None,
            "query": payload.query,
            "response": response
        }

        session_context.append(new_entry)

        # Keep only last 10 raw messages
        context_store[payload.student_id] = session_context[-10:]

        # 🔥 Incremental summary update (CHAT only)
        update_running_summary(
            student_id=payload.student_id,
            subject=payload.subject,
            new_entry=new_entry,
            student_manager=student_manager
        )

    # =============================
    # QUIZ
    # =============================
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

    # =============================
    # STUDY PLAN
    # =============================
    elif intent == "STUDY_PLAN":
        response = handle_study_plan_intent(
            payload=payload,
            profile=profile,
            topic=topic
        )

    # =============================
    # NOTES (🚫 no summary update)
    # =============================
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

    # 🔥 Fetch updated summary from MongoDB
    student_doc = student_manager.students.find_one(
        {"student_id": payload.student_id},
        {"conversation_summary": 1}
    )

    if student_doc:
        context_summary = (
            student_doc.get("conversation_summary", {})
            .get(payload.subject)
        )

    return JSONResponse(
        content={
            "query": payload.query,
            "response": response,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "context_history": context_store[payload.student_id],
            "context_summary": context_summary
        }
    )

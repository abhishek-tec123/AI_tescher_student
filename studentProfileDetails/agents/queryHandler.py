from fastapi.responses import JSONResponse
from studentProfileDetails.learning_progress import normalize_student_preference
from studentProfileDetails.quizHelper import create_quiz_session, get_current_question, handle_quiz_mode
from studentProfileDetails.intent_handlers import handle_chat_intent, handle_study_plan_intent
from studentProfileDetails.agents.mainAgent import detect_intent_and_topic
from studentProfileDetails.agents.quiz_generator import generate_quiz_from_history
from studentProfileDetails.agents.notes_agent import generate_notes
from studentProfileDetails.summrizeStdConv import update_running_summary
import time


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
        query=payload.query,
        student_manager=student_manager
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
        # Fetch stored conversation history from MongoDB
        stored_history = student_manager.get_chat_history_by_agent(
            student_id=payload.student_id,
            subject=payload.subject,
            limit=20  # Get more history for better quiz generation
        )
        
        # Combine session context with stored history
        # Convert stored history to the format expected by quiz generator
        formatted_stored_history = []
        for item in stored_history:
            formatted_stored_history.append({
                "query": item.get("query", ""),
                "response": item.get("response", "")
            })
        
        # Combine session context (most recent) with stored history
        combined_history = formatted_stored_history + session_context
        
        quiz_data = generate_quiz_from_history(
            history=combined_history,
            subject=payload.subject,
            topic=topic,
            num_questions=5
        )

        if not quiz_data["quiz"]:
            response = "Sorry, I couldn't generate a quiz right now."
        else:
            create_quiz_session(payload.student_id, quiz_data)
            
            # Record quiz start in conversation history
            quiz_start_entry = {
                "query": payload.query,
                "response": f"Started quiz about {topic or payload.subject} with {len(quiz_data['quiz'])} questions",
                "quiz_metadata": {
                    "topic": topic,
                    "subject": payload.subject,
                    "question_count": len(quiz_data["quiz"]),
                    "quiz_id": f"quiz_{payload.student_id}_{int(time.time())}"
                }
            }
            
            # Store quiz start in conversation history
            student_manager.add_conversation(
                student_id=payload.student_id,
                subject=payload.subject,
                query=quiz_start_entry["query"],
                response=quiz_start_entry["response"],
                additional_data=quiz_start_entry.get("quiz_metadata", {})
            )
            
            response = {
                "message": "Quiz started!",
                "question": get_current_question(payload.student_id),
                "quiz_metadata": {
                    "topic": topic,
                    "subject": payload.subject,
                    "question_count": len(quiz_data["quiz"]),
                    "history_used": len(combined_history)
                }
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
        # Fetch stored conversation history from MongoDB
        stored_history = student_manager.get_chat_history_by_agent(
            student_id=payload.student_id,
            subject=payload.subject,
            limit=20  # Get more history for better notes generation
        )
        
        # Combine session context with stored history
        # Convert stored history to the format expected by notes generator
        formatted_stored_history = []
        for item in stored_history:
            formatted_stored_history.append({
                "query": item.get("query", ""),
                "response": item.get("response", "")
            })
        
        # Combine session context (most recent) with stored history
        combined_history = formatted_stored_history + session_context
        
        notes = generate_notes(
            topic=topic,
            chat_history=combined_history,
            student_profile=profile
        )

        response = {
            "topic": topic,
            "notes": notes,
            "metadata": {
                "history_used": len(combined_history),
                "stored_history": len(formatted_stored_history),
                "session_context": len(session_context)
            }
        }

        # Record notes generation in conversation history
        student_manager.add_conversation(
            student_id=payload.student_id,
            subject=payload.subject,
            query=payload.query,
            response=f"Generated notes about {topic}",
            additional_data={
                "notes_action": "generated",
                "topic": topic,
                "history_sources": len(combined_history)
            }
        )

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

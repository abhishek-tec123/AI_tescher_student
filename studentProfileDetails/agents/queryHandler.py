from fastapi.responses import JSONResponse
from studentProfileDetails.learning_progress import normalize_student_preference
from studentProfileDetails.quizHelper import create_quiz_session, get_current_question, handle_quiz_mode
from studentProfileDetails.intent_handlers import handle_chat_intent, handle_study_plan_intent
from studentProfileDetails.agents.mainAgent import detect_intent_and_topic
from studentProfileDetails.agents.quiz_generator import generate_quiz_from_history
from studentProfileDetails.agents.notes_agent import generate_notes
from studentProfileDetails.summrizeStdConv import update_running_summary
from studentProfileDetails.utils.agent_utils import get_dynamic_agent_id_for_subject
import time
import threading

# Simple in-memory cache for student preferences
student_preference_cache = {}
student_existence_cache = {}
cache_lock = threading.Lock()

def get_cached_preference(student_id, subject, student_manager):
    """Get student preference with caching for faster response."""
    cache_key = f"{student_id}_{subject}"
    
    with cache_lock:
        if cache_key in student_preference_cache:
            cached_pref, timestamp = student_preference_cache[cache_key]
            # Cache for 5 minutes
            if time.time() - timestamp < 300:
                print(f"🎯 Using cached preference for {cache_key}")
                return cached_pref
    
    # If not in cache or expired, fetch from database
    print(f"📂 Fetching preference from database for {cache_key}")
    preference = student_manager.get_or_create_subject_preference(student_id, subject)
    
    # Update cache
    with cache_lock:
        student_preference_cache[cache_key] = (preference, time.time())
    
    return preference

def check_student_exists_cached(student_id, student_manager):
    """Check if student exists with caching."""
    with cache_lock:
        if student_id in student_existence_cache:
            cached_exists, timestamp = student_existence_cache[student_id]
            # Cache for 10 minutes
            if time.time() - timestamp < 600:
                print(f"🎯 Using cached existence check for {student_id}")
                return cached_exists
    
    # If not in cache or expired, check database
    print(f"📂 Checking student existence in database for {student_id}")
    exists = student_manager.students.find_one({"student_id": student_id}) is not None
    
    # Update cache
    with cache_lock:
        student_existence_cache[student_id] = (exists, time.time())
    
    return exists

def update_performance_background(student_manager, student_id, subject, query, response, evolution_scores):
    """Background function to update performance metrics asynchronously."""
    try:
        agent_id = get_dynamic_agent_id_for_subject(student_manager, student_id, subject)
        if agent_id:
            student_manager.add_conversation(
                student_id=student_id,
                subject=subject,
                query=query,
                response=response,
                evaluation=evolution_scores,
                quality_scores=evolution_scores,
                feedback=evolution_scores.get("feedback", "like"),
                confusion_type=evolution_scores.get("confusion_type", "NO_CONFUSION"),
                additional_data={
                    "subject_agent_id": agent_id
                }
            )
            print(f"🔄 Background performance update completed for agent: {agent_id}")
            
            # Clear preference cache when student data is updated
            with cache_lock:
                cache_key = f"{student_id}_{subject}"
                if cache_key in student_preference_cache:
                    del student_preference_cache[cache_key]
                    print(f"🗑️ Cleared preference cache for {cache_key}")
        else:
            print(f"⚠️ Background update skipped - Agent not found for subject '{subject}'")
    except Exception as e:
        print(f"❌ Background performance update failed: {e}")

def queryRouter(
    *,
    payload,
    student_agent,
    student_manager,
    context_store
):

    conversation_id = None  # ✅ local variable (thread-safe)
    context_summary = None
    evolution_scores = {}

    # Ensure student exists (with caching)
    if not check_student_exists_cached(payload.student_id, student_manager):
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
        get_cached_preference(
            payload.student_id, payload.subject, student_manager
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
        evolution_scores = result.get("evaluation", {})

        new_entry = {
            "conversation_id": str(conversation_id) if conversation_id else None,
            "query": payload.query,
            "response": response,
            "evolution": evolution_scores
        }

        session_context.append(new_entry)

        # Keep only last 10 raw messages
        context_store[payload.student_id] = session_context[-10:]

        # � Start background summary update for faster response
        def update_summary_background():
            try:
                update_running_summary(
                    student_id=payload.student_id,
                    subject=payload.subject,
                    new_entry=new_entry,
                    student_manager=student_manager
                )
                print(f"🔄 Background summary update completed for: {payload.student_id}")
            except Exception as e:
                print(f"❌ Background summary update failed: {e}")
        
        summary_thread = threading.Thread(target=update_summary_background, daemon=True)
        summary_thread.start()
        print(f"🚀 Summary update started in background for faster response")

    # =============================
    # QUIZ
    # =============================
    elif intent == "QUIZ":
        # Fetch stored conversation history from MongoDB
        stored_history = student_manager.get_chat_history_by_agent(
            student_id=payload.student_id,
            subject=payload.subject,
            limit=20  # Get all available history for better quiz generation
        )
        
        # Combine session context with stored history
        # Convert stored history to the format expected by quiz generator
        formatted_stored_history = []
        for item in stored_history:
            formatted_stored_history.append({
                "query": item.get("query", ""),
                "response": item.get("response", ""),
                "evolution": item.get("evaluation", {})
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
            create_quiz_session(payload.student_id, quiz_data, payload.subject)
            
            # Record quiz start in conversation history
            first_question = quiz_data['quiz'][0] if quiz_data['quiz'] else None
            quiz_start_response = f"Started quiz about {topic or payload.subject} with {len(quiz_data['quiz'])} questions"
            
            if first_question:
                quiz_start_response += f"\n\nQ1: {first_question['question']}\nOptions: A) {first_question['options'][0]}, B) {first_question['options'][1]}, C) {first_question['options'][2]}, D) {first_question['options'][3]}"
            
            quiz_start_entry = {
                "query": payload.query,
                "response": quiz_start_response,
                "quiz_metadata": {
                    "topic": topic,
                    "subject": payload.subject,
                    "question_count": len(quiz_data["quiz"]),
                    "quiz_id": f"quiz_{payload.student_id}_{int(time.time())}"
                }
            }
            
            # 🚀 Start background conversation storage for quiz
            def store_quiz_background():
                try:
                    # Get agent ID for performance tracking
                    agent_id = get_dynamic_agent_id_for_subject(student_manager, payload.student_id, payload.subject)
                    
                    if agent_id:
                        student_manager.add_conversation(
                            student_id=payload.student_id,
                            subject=payload.subject,
                            query=quiz_start_entry["query"],
                            response=quiz_start_entry["response"],
                            additional_data={
                                **quiz_start_entry.get("quiz_metadata", {}),
                                "subject_agent_id": agent_id,  # Add agent ID for performance tracking
                                "quiz_session": True,
                                "quality_scores": {
                                    "overall_score": 80.0,  # Default score for quiz start
                                    "engagement": 85.0,
                                    "participation": 90.0
                                }
                            }
                        )
                        print(f"🔄 Background quiz storage completed for: {payload.student_id}")
                    else:
                        print(f"⚠️ Quiz storage skipped - Agent not found")
                except Exception as e:
                    print(f"❌ Background quiz storage failed: {e}")
            
            quiz_thread = threading.Thread(target=store_quiz_background, daemon=True)
            quiz_thread.start()
            print(f"🚀 Quiz storage started in background for faster response")
            
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
        
        # 🚀 Start background conversation storage for study plan
        def store_study_plan_background():
            try:
                student_manager.add_conversation(
                    student_id=payload.student_id,
                    subject=payload.subject,
                    query=payload.query,
                    response=response.get("study_plan", ""),  # Store actual study plan content
                    additional_data={
                        "study_plan_action": "generated",
                        "topic": topic,
                        "study_plan": response.get("study_plan", "")
                    }
                )
                print(f"🔄 Background study plan storage completed for: {payload.student_id}")
            except Exception as e:
                print(f"❌ Background study plan storage failed: {e}")
        
        study_plan_thread = threading.Thread(target=store_study_plan_background, daemon=True)
        study_plan_thread.start()
        print(f"🚀 Study plan storage started in background for faster response")

    # =============================
    # NOTES (🚫 no summary update)
    # =============================
    elif intent == "NOTES":
        # Fetch stored conversation history from MongoDB
        stored_history = student_manager.get_chat_history_by_agent(
            student_id=payload.student_id,
            subject=payload.subject,
            limit=20  # Get all available history for better notes generation
        )
        
        # Combine session context with stored history
        # Convert stored history to the format expected by notes generator
        formatted_stored_history = []
        for item in stored_history:
            formatted_stored_history.append({
                "query": item.get("query", ""),
                "response": item.get("response", ""),
                "evolution": item.get("evaluation", {})
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

        # 🚀 Start background conversation storage for notes
        def store_notes_background():
            try:
                student_manager.add_conversation(
                    student_id=payload.student_id,
                    subject=payload.subject,
                    query=payload.query,
                    response=notes,  # Store actual notes content
                    additional_data={
                        "notes_action": "generated",
                        "topic": topic,
                        "history_sources": len(combined_history)
                    }
                )
                print(f"🔄 Background notes storage completed for: {payload.student_id}")
            except Exception as e:
                print(f"❌ Background notes storage failed: {e}")
        
        notes_thread = threading.Thread(target=store_notes_background, daemon=True)
        notes_thread.start()
        print(f"🚀 Notes storage started in background for faster response")

        session_context.append({
            "query": payload.query,
            "response": notes
        })

        context_store[payload.student_id] = session_context[-10:]

    # � Skip synchronous summary fetch for faster response
    # Summary is now updated in background, so we'll use cached data or None
    context_summary = None  # Will be updated in background
    
    # Optional: You could cache the previous summary in memory if needed
    # context_summary = context_summary_cache.get(f"{payload.student_id}_{payload.subject}")

    return JSONResponse(
        content={
            "query": payload.query,
            "response": response,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "evolution": evolution_scores,
            "context_history": context_store[payload.student_id],
            "context_summary": context_summary
        }
    )

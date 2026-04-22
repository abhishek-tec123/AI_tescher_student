import re
import threading
from studentProfileDetails.learning_progress import (
    normalize_student_preference,
    update_progress_and_regression,
)
from studentProfileDetails.agents.mainAgent import diagnosis_chat
from studentProfileDetails.agents.quiz_generator import generate_quiz_from_history
from studentProfileDetails.agents.studyPlane import generate_study_plan_with_subtopics
from studentProfileDetails.agents.evaluation_agent import evaluate_response
from studentProfileDetails.agents.vector_performance_updater import update_vector_performance
from studentProfileDetails.utils.agent_utils import get_dynamic_agent_id_for_subject  # ✅ Import dynamic agent ID mapping
from studentProfileDetails.handle_general_cht import is_greeting, handle_greeting_chat, handle_general_chat_llm, is_general_chat
from studentProfileDetails.dbutils import ConversationManager, PreferenceManager
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
    preference_manager,  # Add preference_manager parameter
    chat_session_id=None,  # Add chat_session_id parameter
):
    # Import language detector
    from studentProfileDetails.language_detector import detect_language
    
    # Detect language from query or use explicit preference
    explicit_language = getattr(payload, 'language', None)
    if explicit_language and explicit_language != "auto":
        detected_language = explicit_language
        print(f"🌐 Using explicit language from request: {detected_language}")
    else:
        # Auto-detect from query
        detected_language = detect_language(payload.query, use_llm_fallback=True)
        print(f"🌐 Auto-detected language in handle_chat_intent: {detected_language}")
    
    # Store in profile for continuity
    profile["last_detected_language"] = detected_language
    # -----------------------------------------
    # Greeting
    # -----------------------------------------
    if is_greeting(payload.query):
        return handle_greeting_chat(
            payload=payload,
            student_manager=student_manager,
            profile=profile,
            chat_session_id=chat_session_id,
            language=detected_language
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
            chat_session_id=chat_session_id,
            language=detected_language
        )

    # -----------------------------------------
    # Academic Tutor Flow (Vector DB + Agent) - PRIORITY #1
    # -----------------------------------------
    # Get subject_agent_id for agent introduction
    subject_agent_id = get_dynamic_agent_id_for_subject(student_manager, payload.student_id, payload.subject)
    
    # Prepare academic history
    history_context = [
        f"Q: {turn['query']}\nA: {turn['response']}"
        for turn in context
    ]
    
    chat = diagnosis_chat(
        student_agent,
        payload.query,
        payload.class_name,
        payload.subject,
        profile,
        context=history_context,
        subject_agent_id=subject_agent_id,
        language=detected_language
    )

    response = chat["response"]
    confusion_type = chat.get("confusion_type")
    rl_metadata = chat.get("rl_metadata", {})

    # -----------------------------------------
    # STORE CONVERSATION IMMEDIATELY for conversation_id
    # -----------------------------------------
    conversation_manager = ConversationManager()
    
    # Store conversation immediately to get conversation_id
    conversation_id = conversation_manager.add_conversation(
        student_id=payload.student_id,
        subject=payload.subject,
        query=payload.query,
        response=response,  # Store actual response
        feedback="neutral",  # Default feedback
        confusion_type=confusion_type or "NO_CONFUSION",
        evaluation=None,
        additional_data={},
        chat_session_id=chat_session_id  # Add chat_session_id
    )
    
    print(f"📝 Conversation stored immediately with ID: {conversation_id}")
    
    # -----------------------------------------
    # IMMEDIATE RESPONSE PRIORITY: Return LLM response first
    # -----------------------------------------
    
    # Return immediate response with original profile (faster!)
    try:
        context_summary = conversation_manager.get_subject_summary(payload.student_id, payload.subject)
    except Exception as e:
        print(f"⚠️ Failed to fetch existing summary in handle_chat_intent: {e}")
        context_summary = None
    
    immediate_result = {
        "response": response,
        "profile": profile,  # Return original profile for speed
        "evaluation": {"status": "processing"},  # Placeholder evaluation
        "conversation_id": conversation_id,  # Now has actual ID
        "context_summary": context_summary,  # Add context summary to response
        "detected_language": detected_language,  # Include detected language
    }

    # -----------------------------------------
    # BACKGROUND PROCESSING: Handle all non-critical operations
    # -----------------------------------------
    def background_processing():
        try:
            # 1️⃣ Update progression (moved to background for speed)
            updated_profile = update_progress_and_regression(
                student_manager,
                payload.student_id,
                payload.subject,
                profile,
                preference_manager
            )
            print("📊 Background profile update completed")
            
            # 2️⃣ Update conversation with additional data
            agent_id = get_dynamic_agent_id_for_subject(student_manager, payload.student_id, payload.subject)
            
            # Prepare additional data - evaluation and agent_id go directly to conversation level
            conversation_updates = {}
            if agent_id:
                conversation_updates["subject_agent_id"] = agent_id
            if rl_metadata:
                conversation_updates["rl_metadata"] = rl_metadata
            if chat_session_id:
                conversation_updates["chat_session_id"] = chat_session_id
            
            # Update the existing conversation with evaluation and agent data
            if conversation_updates:
                conversation_manager.update_conversation(
                    conversation_id=conversation_id,
                    additional_data=conversation_updates
                )
            
            if agent_id:
                print(f"📝 Background conversation updated with agent: {agent_id}")
            else:
                print(f"⚠️ Background conversation updated - Agent not found for subject '{payload.subject}'")
            
            # 3️⃣ Evaluate academic response (moved to background)
            evaluation = evaluate_response(
                query=payload.query,
                response=response,
                subject=payload.subject,
                profile=updated_profile,
            )
            print("🧠 Background evaluation completed")
            
            # 4️⃣ Store evaluation scores in conversation
            if evaluation:
                conversation_manager.update_conversation(
                    conversation_id=conversation_id,
                    additional_data={"evaluation": evaluation}
                )
                print(f"📊 Evaluation scores stored for conversation: {conversation_id}")
            
            # Performance tracking (moved to background)
            if agent_id:
                performance_update_result = update_vector_performance(
                    subject_agent_id=agent_id,
                    quality_scores=evaluation,
                    feedback=evaluation.get("feedback", "like") if isinstance(evaluation, dict) else "like",
                    confusion_type=confusion_type,
                    student_id=payload.student_id
                )
                print(f"🔥 PERFORMANCE UPDATE TRIGGERED")
                print(f"   - Agent ID: {agent_id}")
                print(f"   - Quality Scores: {evaluation}")
                print(f"   - Student ID: {payload.student_id}")
                print(f"   - Performance Update Result: {performance_update_result}")
            
            # Update conversation summary in background
            from studentProfileDetails.summrizeStdConv import update_running_summary
            new_entry = {
                "query": payload.query,
                "response": response,
                "evolution": evaluation
            }
            update_running_summary(
                student_id=payload.student_id,
                subject=payload.subject,
                new_entry=new_entry,
                student_manager=student_manager,
                conversation_manager=conversation_manager  # Add missing parameter
            )
            print("📝 Background summary update completed")
            
            # Update student profile with new preferences (moved to background)
            try:
                # Use existing preference_manager or create new one if needed (thread safety)
                pm = preference_manager if preference_manager is not None else PreferenceManager()
                
                pm.update_subject_preference(
                    student_id=payload.student_id,
                    subject=payload.subject,
                    updates={
                        "learning_style": updated_profile["learning_style"],
                        "level": updated_profile["level"],
                        "tone": updated_profile["tone"],
                        "response_length": updated_profile["response_length"],
                        "include_example": updated_profile["include_example"],
                        "last_detected_language": detected_language,  # Store detected language
                    },
                )
                print("💾 Background profile persistence completed")
            except Exception as e:
                print(f"❌ Background profile persistence failed: {e}")
                import traceback
                traceback.print_exc()
            
            # Second progression update (non-critical)
            final_profile = update_progress_and_regression(
                student_manager,
                payload.student_id,
                payload.subject,
                updated_profile,
                preference_manager=pm,
            )
            print("📈 Background final progression update completed")
            
            print("✅ All background processing completed successfully")
            
        except Exception as e:
            print(f"❌ Background processing failed: {e}")
    
    # Start background processing for non-critical operations
    background_thread = threading.Thread(target=background_processing, daemon=True)
    background_thread.start()
    print(f"🚀 Non-critical operations moved to background")
    
    return immediate_result


# -------------------------------------------------
# Quiz Intent
# -------------------------------------------------

def handle_quiz_intent(*, student_manager, payload, topic):
    # Use ConversationManager for conversation history
    conversation_manager = ConversationManager()
    history = conversation_manager.get_conversation_history(
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

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
from studentProfileDetails.utils.agent_utils import get_dynamic_agent_id_for_subject  # ✅ Import dynamic agent ID mapping
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
        subject_agent_id=subject_agent_id
    )

    response = chat["response"]
    confusion_type = chat.get("confusion_type")
    rl_metadata = chat.get("rl_metadata", {})

    # -----------------------------------------
    # Return immediate response to user
    # -----------------------------------------
    immediate_result = {
        "response": response,
        "profile": profile,  # Return current profile, will be updated in background
        "evaluation": None,  # Will be populated in background
        "conversation_id": None,  # Will be populated in background
    }

    # -----------------------------------------
    # Background processing for all database operations
    # -----------------------------------------
    def background_processing():
        try:
            # Update progression BEFORE academic response
            updated_profile = update_progress_and_regression(
                student_manager,
                payload.student_id,
                payload.subject,
                profile,
            )
            print("📊 Background profile update completed")
            
            # Evaluate academic response
            evaluation = evaluate_response(
                query=payload.query,
                response=response,
                subject=payload.subject,
                profile=updated_profile,
                confusion_type=confusion_type,
            )
            print("🧠 Background evaluation completed")

            # Persist profile
            student_manager.update_subject_preference(
                payload.student_id,
                payload.subject,
                {
                    "confusion_counter": updated_profile["confusion_counter"],
                    "common_mistakes": updated_profile["common_mistakes"],
                    "learning_style": updated_profile["learning_style"],
                    "level": updated_profile["level"],
                    "tone": updated_profile["tone"],
                    "response_length": updated_profile["response_length"],
                    "include_example": updated_profile["include_example"],
                },
            )
            print("💾 Background profile persistence completed")
            
            # Store conversation
            agent_id = get_dynamic_agent_id_for_subject(student_manager, payload.student_id, payload.subject)
            if agent_id:
                conversation_id = student_manager.add_conversation(
                    student_id=payload.student_id,
                    subject=payload.subject,
                    query=payload.query,
                    response=response,
                    confusion_type=confusion_type,
                    evaluation=evaluation,
                    quality_scores=evaluation,  # ✅ Add quality_scores for performance tracking
                    feedback=evaluation.get("feedback", "like") if isinstance(evaluation, dict) else "like",  # ✅ Add feedback
                    additional_data={
                        "rl_metadata": rl_metadata,
                        "subject_agent_id": agent_id  # ✅ Use dynamic agent ID mapping
                    }
                )
            else:
                conversation_id = student_manager.add_conversation(
                    student_id=payload.student_id,
                    subject=payload.subject,
                    query=payload.query,
                    response=response,
                    confusion_type=confusion_type,
                    evaluation=evaluation,
                    additional_data={"rl_metadata": rl_metadata}
                )
                print(f"⚠️ Agent not found for subject '{payload.subject}'. Performance tracking skipped.")
            
            print(f"🔄 Background conversation storage completed: {conversation_id}")
            
            # Second progression update
            final_profile = update_progress_and_regression(
                student_manager,
                payload.student_id,
                payload.subject,
                updated_profile,
            )
            print("📈 Background final progression update completed")
            
            # Reload normalized profile
            normalized_profile = normalize_student_preference(
                student_manager.get_or_create_subject_preference(
                    payload.student_id, payload.subject
                )
            )
            print("✅ All background processing completed successfully")
            
        except Exception as e:
            print(f"❌ Background processing failed: {e}")
    
    # Start background processing for faster response
    background_thread = threading.Thread(target=background_processing, daemon=True)
    background_thread.start()
    print(f"🚀 All database operations moved to background for faster response")
    
    return immediate_result


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

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, sys, json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from concept_diagnosis_agent import detect_intent_and_topic
from db_utils import StudentManager
from studentAgent.student_agent import StudentAgent

from learning_progress import normalize_student_preference
from intent_handlers import handle_chat_intent, handle_quiz_intent, handle_study_plan_intent

app = FastAPI(title="Student Learning API")

# -----------------------------
# Global instances
# -----------------------------
student_agent: StudentAgent | None = None
student_manager: StudentManager | None = None

# Session-based, user-specific context dictionary
# Key: student_id, Value: list of {"query": ..., "response": ...}
context_store: dict[str, list[dict[str, str]]] = {}

# -----------------------------
# Schemas
# -----------------------------
class AskRequest(BaseModel):
    student_id: str
    subject: str
    class_name: str
    query: str

# -----------------------------
# Startup
# -----------------------------
@app.on_event("startup")
def startup_event():
    global student_agent, student_manager
    student_agent = StudentAgent()
    student_manager = StudentManager()
    student_manager.initialize_db_collection()

# -----------------------------
# POST /student/intent-based-agent
# -----------------------------
@app.post("/student/intent-based-agent")
def ask(payload: AskRequest):
    global context_store

    # Ensure student exists
    student_manager.create_student(
        payload.student_id, {"class": payload.class_name}
    )

    # Load or initialize session context for this student
    if payload.student_id not in context_store:
        context_store[payload.student_id] = []

    session_context = context_store[payload.student_id]

    # Normalize student profile
    profile = normalize_student_preference(
        student_manager.get_or_create_subject_preference(
            payload.student_id, payload.subject
        )
    )
    print(json.dumps(profile, indent=3))
    print("--------------------------------")

    # Detect intent and topic
    intent_result = detect_intent_and_topic(payload.query)
    intent = intent_result["intent"]
    topic = intent_result.get("topic")

    response = None
    evaluation = None

    # -----------------------------
    # Handle intents
    # -----------------------------
    if intent == "CHAT":
        # Pass session context to chat handler
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

        # Update session context with the latest query-response
        session_context.append({
            "query": payload.query,
            "response": response
        })

        # Optional: limit session context to last 10 turns
        context_store[payload.student_id] = session_context[-10:]

    elif intent == "QUIZ":
        response = handle_quiz_intent(
            student_manager=student_manager,
            payload=payload,
            topic=topic
        )

    elif intent == "STUDY_PLAN":
        response = handle_study_plan_intent(
            payload=payload,
            profile=profile,
            topic=topic
        )

    # -----------------------------
    # Return response
    # -----------------------------
    return JSONResponse(
        content={
            "intent": intent,
            "response": response,
            "profile": profile,
            "quality_scores": evaluation,
            "context_history": context_store[payload.student_id]  # user-specific session context
        }
    )

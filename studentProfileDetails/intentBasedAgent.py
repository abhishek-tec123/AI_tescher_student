import os, sys
from datetime import datetime
import json
from fastapi.responses import JSONResponse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI
from pydantic import BaseModel

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
    student_manager.create_student(
        payload.student_id, {"class": payload.class_name}
    )

    profile = normalize_student_preference(
        student_manager.get_or_create_subject_preference(
            payload.student_id, payload.subject
        )
    )

    intent_result = detect_intent_and_topic(payload.query)
    intent = intent_result["intent"]
    topic = intent_result.get("topic")

    response = None
    evaluation = None

    if intent == "CHAT":
        result = handle_chat_intent(
            student_agent=student_agent,
            student_manager=student_manager,
            payload=payload,
            profile=profile
        )
        response = result["response"]
        profile = result["profile"]
        evaluation = result["evaluation"]

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

    return JSONResponse(
        content=json.loads(json.dumps({
            "intent": intent,
            "response": response,
            "profile": profile,
            "quality_scores": evaluation,
        }, indent=3))
    )



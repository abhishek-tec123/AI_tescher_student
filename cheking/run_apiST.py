import os, sys, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal

from db_utils import StudentManager  # Updated StudentManager with all methods
from studentAgent.student_agent import StudentAgent

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


class FeedbackRequest(BaseModel):
    student_id: str
    subject: str
    feedback: Literal["like", "dislike", "neutral"]
    conversation_id: Optional[str] = None  # optional

class HistoryRequest(BaseModel):
    student_id: str
    subject: str
    limit: int = 10
# -----------------------------
# Startup event
# -----------------------------
@app.on_event("startup")
def startup_event():
    global student_agent, student_manager
    student_agent = StudentAgent()
    student_manager = StudentManager()
    student_manager.initialize_db_collection()


# -----------------------------
# POST /student/learning-plan
# -----------------------------
@app.post("/student/learning-plan")
def ask(payload: AskRequest):
    if not student_manager or not student_agent:
        raise HTTPException(status_code=500, detail="Services not initialized")

    # Ensure student exists
    student_manager.create_student(
        student_id=payload.student_id,
        student_details={"class": payload.class_name}
    )

    # Get or create subject preference
    subject_pref = student_manager.get_or_create_subject_preference(
        payload.student_id, payload.subject
    )

    # Print for debugging
    print(json.dumps(subject_pref, indent=3))

    # Generate AI response using the student's preferences
    response = student_agent.ask(
        query=payload.query,
        class_name=payload.class_name,
        subject=payload.subject,
        student_profile=subject_pref
    )

    # Store conversation and get the conversation ID
    conversation_id = student_manager.add_conversation(
        student_id=payload.student_id,
        subject=payload.subject,
        query=payload.query,
        response=response
    )

    # Add conversation_id to metadata (already done in add_conversation)
    # Return it in the response
    return {
        "response": response,
        "feedback": "neutral",
        "conversation_id": str(conversation_id)  # Convert ObjectId to string
    }

# -----------------------------
# POST /student/feedback
# -----------------------------
@app.post("/student/feedback")
def feedback(payload: FeedbackRequest):
    if not student_manager:
        raise HTTPException(status_code=500, detail="StudentManager not initialized")

    # If conversation_id is not provided, get the last conversation id from metadata
    if payload.conversation_id is None:
        doc = student_manager.students.find_one(
            {"_id": payload.student_id},
            {f"metadata.last_conversation_id.{payload.subject}": 1}
        )

        if not doc:
            raise HTTPException(status_code=404, detail="Student not found")

        last_conv_id = doc.get("metadata", {}).get("last_conversation_id", {}).get(payload.subject)
        if not last_conv_id:
            raise HTTPException(status_code=404, detail="No conversation found for this subject")

        payload.conversation_id = str(last_conv_id)  # Convert ObjectId to string

    # Update feedback in MongoDB
    updated = student_manager.update_feedback(
        student_id=payload.student_id,
        subject=payload.subject,
        feedback=payload.feedback,
        conversation_id=payload.conversation_id
    )

    if updated == 0:
        raise HTTPException(status_code=404, detail="Failed to update feedback")

    return {
        "status": "success",
        "feedback": payload.feedback,
        "conversation_id": payload.conversation_id
    }

# -----------------------------
# POST /subjet/history
# -----------------------------
@app.post("/student/history")
def get_history(payload: HistoryRequest):
    history = student_manager.get_conversation_history(
        student_id=payload.student_id,
        subject=payload.subject,
        limit=payload.limit
    )

    return {
        "student_id": payload.student_id,
        "subject": payload.subject,
        "count": len(history),
        "history": history
    }

# -----------------------------
# POST /student/summary
# -----------------------------
class ConversationSummaryRequest(BaseModel):
    student_id: str
    subject: str
    limit: Optional[int] = None
    prompt: Optional[str] = None


@app.post("/student/conversation/summary")
def generate_summary(payload: ConversationSummaryRequest):
    try:
        summary = student_manager.summarize_and_store_conversation(
            student_id=payload.student_id,
            subject=payload.subject,
            limit=payload.limit,
            prompt=payload.prompt or "Summarize the conversation for quick revision."
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "student_id": payload.student_id,
        "subject": payload.subject,
        "summary": summary
    }

# ---------------------------------------------------------------
from quiz_generator import generate_quiz_from_history
# ---------------------------------------------------------------

class QuizRequest(BaseModel):
    student_id: str
    subject: str
    limit: Optional[int] = 10
    num_questions: Optional[int] = 5

@app.post("/student/quiz")
def generate_quiz(payload: QuizRequest):
    # 1️⃣ Get conversation history
    history = student_manager.get_conversation_history(
        student_id=payload.student_id,
        subject=payload.subject,
        limit=payload.limit
    )

    # 2️⃣ Generate quiz
    quiz = generate_quiz_from_history(
        history=history,
        subject=payload.subject,
        num_questions=payload.num_questions
    )

    return quiz

from studyPlane import generate_study_plan_with_subtopics

class StudyPlanRequest(BaseModel):
    student_id: str
    subject: str
    query: str

# -----------------------------
# POST /student/study-plan
# -----------------------------
@app.post("/student/study-plan")
def generate_study_plan(payload: StudyPlanRequest):
    if not student_manager:
        raise HTTPException(status_code=500, detail="StudentManager not initialized")

    # Ensure student exists
    student_manager.create_student(
        student_id=payload.student_id,
        student_details={"class": "Unknown"}
    )

    # Get subject preferences (used to personalize plan)
    subject_pref = student_manager.get_or_create_subject_preference(
        payload.student_id,
        payload.subject
    )

    # Generate study plan
    plan_text = generate_study_plan_with_subtopics(
        student_sentence=payload.query,
        student_profile=subject_pref
    )

    return {
        "subject": payload.subject,
        "study_plan": plan_text
    }

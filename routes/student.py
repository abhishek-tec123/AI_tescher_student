from fastapi import APIRouter, Request, Depends, HTTPException
from studentProfileDetails.agents.queryHandler import queryRouter
from studentProfileDetails.db_utils import StudentManager
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, List

class CreateStudentRequest(BaseModel):
    name: str
    email: EmailStr
    class_name: str
    subject_agent: Optional[List[Dict[str, str]]] = None

class AskRequest(BaseModel):
    student_id: str
    subject: str
    class_name: str
    query: str

class UpdateStudent(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    class_name: Optional[str] = None
    subject_agent: Optional[List[Dict[str, str]]] = None

router = APIRouter()

context_store: dict[str, list[dict[str, str]]] = {}

@router.post("/agent-query")
def ask(payload: AskRequest, request: Request):
    return queryRouter(
        payload=payload,
        student_agent=request.app.state.student_agent,
        student_manager=request.app.state.student_manager,
        context_store=context_store
    )

@router.post("/create-student")
def create_student(
    payload: CreateStudentRequest,
    student_manager: StudentManager = Depends()
):
    student_id = student_manager.create_student(
        name=payload.name,
        email=payload.email,
        class_name=payload.class_name,
        subject_agent=payload.subject_agent
    )

    return {
        "message": "Student created successfully",
        "student": {
            "student_id": student_id,
            "name": payload.name,
            "email": payload.email,
            "class": payload.class_name,
            "subject_agent": payload.subject_agent or {}
        }
    }

@router.get("/student-list")
def get_students(
    student_manager: StudentManager = Depends()
):
    students = student_manager.list_students()

    return {
        "total": len(students),
        "students": students
    }

@router.get("/{student_id}")
def get_student(
    student_id: str,
    student_manager: StudentManager = Depends()
):
    student = student_manager.get_student(student_id)

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return {
        "id": student["_id"],
        "name": student["student_details"]["name"],
        "email": student["student_details"]["email"],
        "class_name": student["student_details"]["class"],
        "subject_agent": student["student_details"]["subject_agent"],
        "created_at": student["metadata"]["created_at"]
    }

@router.put("/{student_id}")
def update_student(
    student_id: str,
    payload: UpdateStudent,
    student_manager: StudentManager = Depends()
):
    result = student_manager.update_student(student_id, payload)

    if not result or result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    return {"message": "Student updated successfully"}

@router.delete("/{student_id}")
def delete_student(student_id: str):
    manager = StudentManager()  # ✅ create instance
    result = manager.delete_student(student_id)  # now self is provided

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    return {"message": "Student deleted successfully"}

from studentProfileDetails.feedback_handler import record_feedback, FeedbackRequest
@router.post("/feedback")
def submit_feedback(
    payload: FeedbackRequest,
    student_manager: StudentManager = Depends()
):
    return record_feedback(
        conversation_id=payload.conversation_id,
        feedback=payload.feedback,
        student_manager=student_manager
    )

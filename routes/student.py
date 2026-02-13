from fastapi import APIRouter, Request, Depends, HTTPException
from studentProfileDetails.agents.queryHandler import queryRouter
from studentProfileDetails.db_utils import StudentManager
from studentProfileDetails.auth.dependencies import get_current_user, require_role
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
    
class ChatHistoryItem(BaseModel):
    student_id: str
    query: str
    response: str
    evaluation: Optional[Dict] = {}
router = APIRouter()

context_store: dict[str, list[dict[str, str]]] = {}

@router.post("/agent-query")
def ask(payload: AskRequest, request: Request, current_user: dict = Depends(get_current_user)):
    # Ensure student can only access their own data
    if current_user["role"] == "student" and current_user["user_id"] != payload.student_id:
        raise HTTPException(status_code=403, detail="Access denied: You can only query as yourself")
    
    return queryRouter(
        payload=payload,
        student_agent=request.app.state.student_agent,
        student_manager=request.app.state.student_manager,
        context_store=context_store
    )

@router.post("/create-student")
def create_student(
    payload: CreateStudentRequest,
    student_manager: StudentManager = Depends(),
    current_user: dict = Depends(require_role("admin"))
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
    student_manager: StudentManager = Depends(),
    current_user: dict = Depends(get_current_user)
):
    # Students can only see themselves, admins can see all
    if current_user["role"] == "student":
        students = [student_manager.get_student(current_user["user_id"])]
        if students[0]:
            students = [{
                "student_id": students[0]["student_id"],
                "name": students[0]["student_details"]["name"],
                "email": students[0]["student_details"]["email"],
                "class": students[0]["student_details"]["class"],
                "subject_agent": students[0]["student_details"]["subject_agent"]
            }]
        else:
            students = []
    else:
        students = student_manager.list_students()

    return {
        "total": len(students),
        "students": students
    }

@router.get("/{student_id}")
def get_student(
    student_id: str,
    student_manager: StudentManager = Depends(),
    current_user: dict = Depends(get_current_user)
):
    # Students can only access their own data
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied: You can only access your own data")
    
    student = student_manager.get_student(student_id)

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Decrypt password (only if stored encrypted)
    password = None
    if "auth" in student and "password_hash" in student["auth"]:
        from studentProfileDetails.auth.AESPasswordUtils import decrypt_password
        try:
            password = decrypt_password(student["auth"]["password_hash"])
        except Exception:
            password = None  # fail-safe

    return {
        "student_id": student["student_id"],
        "name": student["student_details"]["name"],
        "email": student["student_details"]["email"],
        "class_name": student["student_details"]["class"],
        "subject_agent": student["student_details"]["subject_agent"],
        "created_at": student["metadata"]["created_at"],
        "password": password  # ⚠️ Only for internal/testing, not for production
    }

@router.put("/{student_id}")
def update_student(
    student_id: str,
    payload: UpdateStudent,
    student_manager: StudentManager = Depends(),
    current_user: dict = Depends(get_current_user)
):
    # Students can only update their own data
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied: You can only update your own data")
    
    result = student_manager.update_student(student_id, payload)

    if not result or result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    return {"message": "Student updated successfully"}

@router.delete("/{student_id}")
def delete_student(
    student_id: str,
    current_user: dict = Depends(require_role("admin"))
):
    manager = StudentManager()  # ✅ create instance
    result = manager.delete_student(student_id)  # now self is provided

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    return {"message": "Student deleted successfully"}

@router.get("/{student_id}/history/{subject}", response_model=List[ChatHistoryItem])
def get_chat_history(
    student_id: str,
    subject: str,
    limit: Optional[int] = None,
    student_manager: StudentManager = Depends(),
    current_user: dict = Depends(get_current_user)
):
    """
    Get chat history for a specific student and subject(agent).
    """

    # 🔐 Students can only access their own history
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied")

    history = student_manager.get_chat_history_by_agent(
        student_id=student_id,
        subject=subject,
        limit=limit
    )

    if not history:
        return []

    return history


from studentProfileDetails.feedback_handler import record_feedback, FeedbackRequest
@router.post("/feedback")
def submit_feedback(
    payload: FeedbackRequest,
    student_manager: StudentManager = Depends(),
    current_user: dict = Depends(get_current_user)
):
    return record_feedback(
        conversation_id=payload.conversation_id,
        feedback=payload.feedback,
        student_manager=student_manager
    )

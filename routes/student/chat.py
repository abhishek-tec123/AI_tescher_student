"""
Student chat routes
Handles agent queries, chat history, and conversation management
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from studentProfileDetails.agents.queryHandler import queryRouter
from studentProfileDetails.dbutils import StudentManager, ConversationManager
from studentProfileDetails.dependencies import StudentManagerDep, get_conversation_manager
from studentProfileDetails.auth.dependencies import get_current_user
from pydantic import BaseModel
from typing import Optional, List, Dict

router = APIRouter()

context_store: dict[str, list[dict[str, str]]] = {}

class AskRequest(BaseModel):
    student_id: str
    subject: str
    class_name: str
    query: str

class ChatHistoryItem(BaseModel):
    student_id: str
    query: str
    response: str
    evaluation: Optional[Dict] = {}

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

@router.get("/{student_id}/history/{subject}", response_model=List[ChatHistoryItem])
def get_chat_history(
    student_id: str,
    subject: str,
    limit: Optional[int] = None,
    student_manager: StudentManager = StudentManagerDep,
    conversation_manager: ConversationManager = Depends(get_conversation_manager),
    current_user: dict = Depends(get_current_user)
):
    """
    Get chat history for a specific student and subject(agent).
    """

    # 🔐 Students can only access their own history
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied")

    history = conversation_manager.get_chat_history_by_agent(
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
    student_manager: StudentManager = StudentManagerDep,
    current_user: dict = Depends(get_current_user)
):
    return record_feedback(
        conversation_id=payload.conversation_id,
        feedback=payload.feedback,
        student_manager=student_manager
    )

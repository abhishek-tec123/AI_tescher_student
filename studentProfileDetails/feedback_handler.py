from fastapi import HTTPException, status
from studentProfileDetails.db_utils import StudentManager

from pydantic import BaseModel, Field
from typing import Literal


class FeedbackRequest(BaseModel):
    conversation_id: str = Field(..., description="Conversation ObjectId as string")
    feedback: Literal["like", "dislike"]

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "6985c0b0404996a4bf4891a3",
                "feedback": "like"
            }
        }

def record_feedback(
    *,
    conversation_id: str,
    feedback: str,
    student_manager: StudentManager
) -> dict:

    matched = student_manager.update_feedback_by_conversation_id(
        conversation_id=conversation_id,
        feedback=feedback
    )

    if matched == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    return {
        "message": "Feedback updated successfully",
        "conversation_id": conversation_id,
        "feedback": feedback
    }

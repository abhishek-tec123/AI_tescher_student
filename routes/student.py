from fastapi import APIRouter, Request
from studentProfileDetails.agents.queryHandler import queryRouter
from pydantic import BaseModel

class AskRequest(BaseModel):
    student_id: str
    subject: str
    class_name: str
    query: str

router = APIRouter()

context_store: dict[str, list[dict[str, str]]] = {}

@router.post("/intent-based-agent")
def ask(payload: AskRequest, request: Request):
    return queryRouter(
        payload=payload,
        student_agent=request.app.state.student_agent,
        student_manager=request.app.state.student_manager,
        context_store=context_store
    )

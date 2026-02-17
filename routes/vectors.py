from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException, Depends
from typing import List, Optional
from fastapi.responses import JSONResponse
import os
from pymongo import MongoClient

from Teacher_AI_Agent.dbFun.createVector import create_vectors_service
from Teacher_AI_Agent.dbFun.searchChunk import search_and_generate
from Teacher_AI_Agent.dbFun.dbstatus import check_db_status
from Teacher_AI_Agent.dbFun.classes_and_subject import (
    list_all_classes,
    get_subjects_by_class,
)
from Teacher_AI_Agent.dbFun.collections import list_all_collections, get_all_agents_of_class
from pydantic import BaseModel

router = APIRouter()

class SearchRequest(BaseModel):
    query: str
    class_: str
    subject: str
# -------------------------------------------------
# Health / Env / DB Meta
# -------------------------------------------------
@router.get("/status")
def health():
    return {"status": "ok"}

@router.get("/env_info")
def env_info(request: Request):
    return {
        "mongodb_uri_set": bool(os.environ.get("MONGODB_URI")),
        "groq_api_key_set": bool(os.environ.get("GROQ_API_KEY")),
        "embedding_model_loaded": hasattr(
            request.app.state, "embedding_model"
        ),
    }

@router.get("/db_status/{class_}/{subject}")
def db_status(class_: str, subject: str):
    return check_db_status(class_, subject)

# -------------------------------------------------
# Vector Creation & Search
# -------------------------------------------------
@router.post("/create_vectors")
async def create_vectors(
    request: Request,
    class_: str = Form(...),
    subject: str = Form(...),

    agent_type: str | None = Form(None),
    agent_name: str | None = Form(None),
    description: str | None = Form(None),
    teaching_tone: str | None = Form(None),

    files: Optional[List[UploadFile]] = File(None)

):
    agent_metadata = {
        "agent_type": agent_type,
        "agent_name": agent_name,
        "description": description,
        "teaching_tone": teaching_tone,
    }

    # remove None values
    agent_metadata = {k: v for k, v in agent_metadata.items() if v is not None}

    return await create_vectors_service(
        class_=class_,
        subject=subject,
        files=files,
        embedding_model=request.app.state.embedding_model,
        agent_metadata=agent_metadata or None
    )


@router.post("/search")
def search(payload: SearchRequest, request: Request):
    return search_and_generate(
        query=payload.query,
        class_=payload.class_,
        subject=payload.subject,
        embedding_model=request.app.state.embedding_model,
    )

# -------------------------------------------------
# Classes / Subjects / Collections
# -------------------------------------------------
@router.get("/classes")
def classes():
    return list_all_classes()

@router.get("/subjects")
def subjects(selected_class: str):
    return get_subjects_by_class(selected_class)

@router.get("/all_collections")
def collections():
    return list_all_collections()

class ClassRequest(BaseModel):
    class_name: str

@router.post("/agent_of_class")
def agent(request: ClassRequest):
    data = get_all_agents_of_class(request.class_name)
    return JSONResponse(content=data)

# -------------------------------------------------
# Get Agent by Subject Agent ID and update agent data
# -------------------------------------------------
from Teacher_AI_Agent.dbFun.update_vectors import update_agent_data, delete_agent_data
from Teacher_AI_Agent.dbFun.get_agent_data import get_agent_data
from studentProfileDetails.db_utils import StudentManager
from studentProfileDetails.auth.dependencies import get_current_user

@router.get("/{subject_agent_id}")
async def get_agent(subject_agent_id: str):
    return get_agent_data(subject_agent_id)

@router.put("/{subject_agent_id}")
async def update_agent(
    request: Request,
    subject_agent_id: str,
    class_: str | None = Form(None),
    subject: str | None = Form(None),
    agent_type: str | None = Form(None),
    agent_name: str | None = Form(None),
    description: str | None = Form(None),
    teaching_tone: str | None = Form(None),
    files: Optional[List[UploadFile]] = None,
):
    return await update_agent_data(
        subject_agent_id=subject_agent_id,
        class_=class_,
        subject=subject,
        agent_type=agent_type,
        agent_name=agent_name,
        description=description,
        teaching_tone=teaching_tone,
        files=files,
        embedding_model=request.app.state.embedding_model,
        create_vectors_service=request.app.state.create_vectors_service
    )

@router.delete("/{subject_agent_id}")
async def delete_agent(subject_agent_id: str):
    result = await delete_agent_data(subject_agent_id)

    if not result["deleted"]:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "message": f"Agent {subject_agent_id} deleted successfully.",
        "deleted_chunks": result["deleted_chunks"]
    }

# -------------------------------------------------
# Student Subject Management
# -------------------------------------------------
@router.get("/student/{student_id}/subjects")
def get_student_subjects(
    student_id: str,
    student_manager: StudentManager = Depends(),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all subjects from a student's subject_agent array.
    Students can only access their own subjects, admins can access any student's subjects.
    """
    # Students can only access their own data
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied: You can only access your own data")
    
    student = student_manager.get_student(student_id)
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Extract subjects from subject_agent array
    subject_agent = student.get("student_details", {}).get("subject_agent", [])
    
    if not subject_agent:
        return {"subjects": []}
    
    # Handle both array of objects and array of strings formats
    subjects = []
    if isinstance(subject_agent, list):
        for item in subject_agent:
            subject_name = ""
            if isinstance(item, dict):
                subject_name = item.get("subject", "")
            elif isinstance(item, str):
                subject_name = item
            
            if subject_name:
                # Try to get description and subject_agent_id from database
                description = ""
                subject_agent_id = ""
                try:
                    from Teacher_AI_Agent.dbFun.collections import get_all_agents_of_class
                    # Get student's class to find the right database
                    student_class = student.get("student_details", {}).get("class", "")
                    if student_class:
                        agents_response = get_all_agents_of_class(student_class)
                        if agents_response.get("status") == "success":
                            agents = agents_response.get("agents", [])
                            for agent in agents:
                                if agent.get("subject") == subject_name:
                                    description = agent.get("description", "")
                                    subject_agent_id = agent.get("subject_agent_id", "")
                                    break
                except Exception:
                    # If we can't get description, continue with empty string
                    pass
                
                subjects.append({
                    "name": subject_name,
                    "description": description,
                    "subject_agent_id": subject_agent_id
                })
    
    return {"subjects": subjects}
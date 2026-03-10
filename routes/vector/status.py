"""
Vector status routes
Handles database status, environment info, and collection metadata
"""

from fastapi import APIRouter, Request
import os

router = APIRouter()

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
    from Teacher_AI_Agent.dbFun.dbstatus import check_db_status
    
    return check_db_status(class_, subject)

# -------------------------------------------------
# Classes / Subjects / Collections
# -------------------------------------------------
@router.get("/classes")
def classes():
    from Teacher_AI_Agent.dbFun.classes_and_subject import list_all_classes
    
    return list_all_classes()

@router.get("/subjects")
def subjects(selected_class: str):
    from Teacher_AI_Agent.dbFun.classes_and_subject import get_subjects_by_class
    
    return get_subjects_by_class(selected_class)

@router.get("/all_collections")
def collections():
    from Teacher_AI_Agent.dbFun.collections import list_all_collections
    
    return list_all_collections()

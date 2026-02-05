from fastapi import APIRouter, UploadFile, File, Form, Request
from typing import List
import os

from Teacher_AI_Agent.dbFun.createVector import create_vectors_service
from Teacher_AI_Agent.dbFun.searchChunk import search_and_generate
from Teacher_AI_Agent.dbFun.dbstatus import check_db_status
from Teacher_AI_Agent.dbFun.classes_and_subject import (
    list_all_classes,
    get_subjects_by_class,
)
from Teacher_AI_Agent.dbFun.collections import list_all_collections
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
    files: List[UploadFile] = File(...),
):
    return await create_vectors_service(
        class_=class_,
        subject=subject,
        files=files,
        embedding_model=request.app.state.embedding_model,
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

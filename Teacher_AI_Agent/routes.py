from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from pydantic import BaseModel
from typing import List
from embaddings.VectorStoreInAtls import create_vector_and_store_in_atlas
from SimilaritySearch import retrieve_and_generate_llm_response
from langchain_huggingface import HuggingFaceEmbeddings
import logging
import os
import tempfile
from fastapi.middleware.cors import CORSMiddleware
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from model_cache import model_cache

# -----------------------------
# Logging Setup
# -----------------------------
logging.basicConfig(
    level=logging.WARNING,  # silence most logs
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# App logger
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

# Allow sentence-transformers logs through
st_logger = logging.getLogger("sentence_transformers")
st_logger.setLevel(logging.INFO)

# -----------------------------
# FastAPI App Setup
# -----------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
embedding_model = None

@app.on_event("startup")
async def startup_event():
    global embedding_model
    logger.info("Loading embedding model on startup...")
    embedding_model = model_cache.get_embedding_model(EMBED_MODEL_NAME)
    logger.info("Embedding model loaded and ready.")
    logger.info("🚀 TutorAI API started successfully.")

# Expose explicit initializer for parent app to call sequentially
async def initialize():
    global embedding_model
    if embedding_model is None:
        embedding_model = model_cache.get_embedding_model(EMBED_MODEL_NAME)

app.state.initialize = initialize

MONGODB_URI = os.environ.get("MONGODB_URI")

# -----------------------------
# Route Constants
# -----------------------------
HEALTH_ROUTE = "/status"
ENV_INFO_ROUTE = "/env_info"
DB_STATUS_ROUTE = "/db_status/{class_}/{subject}"
CREATE_VECTORS_ROUTE = "/create_vectors"
SEARCH_ROUTE = "/search"
ALL_COLLECTIONS_ROUTE = "/all_collections"

# -----------------------------
# Validation Error Handler
# -----------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    def sanitize_error(err):
        if "ctx" in err:
            for key, value in err["ctx"].items():
                if isinstance(value, bytes):
                    err["ctx"][key] = "<binary data>"
        return err

    cleaned_errors = [sanitize_error(err) for err in exc.errors()]

    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(cleaned_errors)},
    )

# -----------------------------
# Request Models
# -----------------------------
class VectorRequest(BaseModel):
    file_paths: List[str]
    class_: str
    subject: str

class SearchRequest(BaseModel):
    query: str
    class_: str
    subject: str

# -----------------------------
# Utility: Map class & subject
# -----------------------------
def map_to_db_and_collection(class_: str, subject: str):
    db_name = class_.strip()
    collection_name = subject.strip()
    return db_name, collection_name

# -----------------------------
# Routes
# -----------------------------
@app.get(ENV_INFO_ROUTE)
def get_environment_info():
    return {
        "mongodb_uri_set": bool(os.environ.get("MONGODB_URI")),
        "groq_api_key_set": bool(os.environ.get("GROQ_API_KEY")),
        "db_name": os.environ.get("DB_NAME", "Not set"),
        "collection_name": os.environ.get("COLLECTION_NAME", "Not set"),
        "embedding_model_loaded": embedding_model is not None
    }

@app.get(DB_STATUS_ROUTE)
def check_database_status(class_: str, subject: str):
    try:
        from pymongo import MongoClient
        db_name, collection_name = map_to_db_and_collection(class_, subject)
        client = MongoClient(MONGODB_URI)

        db_exists = db_name in client.list_database_names()
        if not db_exists:
            return {
                "status": "error",
                "message": f"Database '{db_name}' does not exist",
                "available_databases": client.list_database_names()
            }

        collection_exists = collection_name in client[db_name].list_collection_names()
        if not collection_exists:
            return {
                "status": "error",
                "message": f"Collection '{collection_name}' does not exist in database '{db_name}'",
                "available_collections": client[db_name].list_collection_names()
            }

        doc_count = client[db_name][collection_name].count_documents({})
        return {
            "status": "success",
            "database": db_name,
            "collection": collection_name,
            "document_count": doc_count,
            "available_databases": client.list_database_names(),
            "available_collections": client[db_name].list_collection_names()
        }
    except Exception as e:
        logger.error(f"❌ Error checking database status: {e}")
        return {
            "status": "error",
            "message": f"Failed to check database status: {str(e)}"
        }

@app.post(CREATE_VECTORS_ROUTE)
async def create_vectors(
    class_: str = Form(...),
    subject: str = Form(...),
    files: List[UploadFile] = File(...)
):
    try:
        db_name, collection_name = map_to_db_and_collection(class_, subject)
        file_inputs, original_filenames = [], []

        for file in files:
            suffix = os.path.splitext(file.filename)[-1] or ".tmp"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                file_inputs.append(tmp.name)
                original_filenames.append(file.filename)

        summary = create_vector_and_store_in_atlas(
            file_inputs=file_inputs,
            db_name=db_name,
            collection_name=collection_name,
            embedding_model=embedding_model,
            original_filenames=original_filenames
        )

        logger.info("✅ New vector store created successfully.")
        return {
            "status": "success",
            "message": f"Vectors created and stored in MongoDB Atlas → {db_name}.{collection_name}",
            "summary": summary
        }
    except Exception as e:
        logger.error(f"❌ Error in /create_vectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post(SEARCH_ROUTE)
def search_and_respond(request: SearchRequest):
    try:
        db_name, collection_name = map_to_db_and_collection(request.class_, request.subject)
        response = retrieve_and_generate_llm_response(
            query=request.query,
            db_name=db_name,
            collection_name=collection_name,
            embedding_model=embedding_model
        )
        logger.info("✅ Search completed successfully.")
        return {"status": "success", "response": response}
    except Exception as e:
        logger.error(f"❌ Error in /search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from pymongo import MongoClient

@app.get(ALL_COLLECTIONS_ROUTE)
def list_all_collections():
    try:
        client = MongoClient(MONGODB_URI)
        cluster_info = {}

        for db_name in client.list_database_names():
            if db_name in ["admin", "local", "config"]:
                continue
            db = client[db_name]
            collections = db.list_collection_names()
            cluster_info[db_name] = collections

        return {
            "status": "success",
            "databases": cluster_info
        }
    except Exception as e:
        logger.error(f"❌ Error fetching collections: {e}")
        return {
            "status": "error",
            "message": f"Failed to fetch collections: {str(e)}"
        }

@app.get("/classes")
def list_all_classes():
    """
    Returns a list of all available classes (database names).
    """
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGODB_URI)

        # Get all database names except system DBs
        db_names = [
            db_name for db_name in client.list_database_names()
            if db_name not in ["admin", "local", "config"]
        ]

        return {
            "status": "success",
            "classes": db_names
        }

    except Exception as e:
        logger.error(f"❌ Error fetching classes: {e}")
        return {
            "status": "error",
            "message": f"Failed to fetch classes: {str(e)}"
        }

# -----------------------------
# Get Subjects by Selected Class
# -----------------------------
@app.get("/subjects")
def get_subjects_by_class(selected_class: str):
    """
    Returns subjects for a given class from MongoDB.
    Example:
      GET /subjects?selected_class=class10
    """
    try:
        client = MongoClient(MONGODB_URI)
        cluster_info = {}

        # Build the map of all DBs and their collections
        for db_name in client.list_database_names():
            if db_name in ["admin", "local", "config"]:
                continue
            db = client[db_name]
            collections = db.list_collection_names()
            cluster_info[db_name] = collections

        # Lookup requested class
        subjects = cluster_info.get(selected_class)
        if not subjects:
            return {
                "status": "error",
                "message": f"No subjects found for class '{selected_class}'.",
                "available_classes": list(cluster_info.keys())
            }

        return {
            "status": "success",
            "class": selected_class,
            "subjects": subjects
        }

    except Exception as e:
        logger.error(f"❌ Error fetching subjects: {e}")
        return {
            "status": "error",
            "message": f"Failed to fetch subjects: {str(e)}"
        }

@app.get(HEALTH_ROUTE)
def health_check():
    routes_info = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            routes_info.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name,
            })
    return {
        "status": "ok",
        "routes": routes_info
    }
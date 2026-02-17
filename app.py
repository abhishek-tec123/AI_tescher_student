from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from routes.startup import startup_event
from routes import vectors, admin, student, auth
from Teacher_AI_Agent.dbFun.createVector import create_vectors_service
app = FastAPI(title="Student Learning API")

app.state.create_vectors_service = create_vectors_service

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -------------------------------------------------
# Startup
# -------------------------------------------------
@app.on_event("startup")
async def on_startup():
    await startup_event(app)

# -------------------------------------------------
# API v1 Router
# -------------------------------------------------
api_v1_router = APIRouter(prefix="/api/v1")

# Authentication routes (no auth required)
api_v1_router.include_router(
    auth.router, 
    prefix="/auth", 
    tags=["Authentication"]
)

# Student routes (auth required)
api_v1_router.include_router(
    student.router, 
    prefix="/student", 
    tags=["Student"]
)

# Admin routes (auth required)
api_v1_router.include_router(
    admin.router, 
    prefix="/admin", 
    tags=["Admin"]
)

# Vector routes (auth required)
api_v1_router.include_router(
    vectors.router, 
    prefix="/vectors", 
    tags=["Vectors"]
)

app.include_router(api_v1_router)

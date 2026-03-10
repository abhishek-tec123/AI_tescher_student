from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from routes.performance.middleware import PerformanceMonitoringMiddleware
from datetime import datetime
import os

from routes.core.startup import startup_event
from routes.admin import admin_router
from routes.student import student_router
from routes.vector import vector_router
from routes.auth import auth_router
from routes.performance import performance_router
from routes.activity import activity_router
from routes.core import core_router
from routes.topics import topics_router
from Teacher_AI_Agent.dbFun.createVector import create_vectors_service
app = FastAPI(title="Student Learning API")

app.state.create_vectors_service = create_vectors_service

origins = [
    "https://tecorb.in",       # production
    "http://localhost:8080",   # local dev
    "http://127.0.0.1:8080"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add performance monitoring middleware
# app.add_middleware(PerformanceMonitoringMiddleware)
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
    auth_router, 
    prefix="/auth", 
    tags=["Authentication"]
)

# Student routes (auth required)
api_v1_router.include_router(
    student_router, 
    prefix="/student", 
    tags=["Student"]
)

# Admin routes (auth required)
api_v1_router.include_router(
    admin_router, 
    prefix="/admin", 
    tags=["Admin"]
)

# Vector routes (auth required)
api_v1_router.include_router(
    vector_router, 
    prefix="/vectors", 
    tags=["Vectors"]
)

# Performance routes (auth required)
api_v1_router.include_router(
    performance_router, 
    prefix="/performance", 
    tags=["Performance"]
)

# Activity tracking routes (auth required)
api_v1_router.include_router(
    activity_router, 
    prefix="/activity", 
    tags=["Activity Tracking"]
)

# Core routes (health checks, etc.)
api_v1_router.include_router(
    core_router, 
    prefix="/core", 
    tags=["Core"]
)

# Topics routes (auth required)
api_v1_router.include_router(
    topics_router, 
    prefix="/topics", 
    tags=["Topics"]
)

app.include_router(api_v1_router)

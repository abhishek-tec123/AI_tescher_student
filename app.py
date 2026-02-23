from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from routes.performance_middleware import PerformanceMonitoringMiddleware
from datetime import datetime
import os

from routes.startup import startup_event
from routes import vectors, admin, student, auth, agent_performance, all_agents_performance
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

# Add performance monitoring middleware
app.add_middleware(PerformanceMonitoringMiddleware)
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

# Agent Performance routes (auth required)
api_v1_router.include_router(
    agent_performance.router, 
    prefix="/performance", 
    tags=["Agent Performance"]
)

# All Agents Performance routes (auth required)
api_v1_router.include_router(
    all_agents_performance.router, 
    prefix="/performance", 
    tags=["All Agents Performance"]
)

app.include_router(api_v1_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check database connection
        from pymongo import MongoClient
        from routes.performance_cache import performance_cache
        
        client = MongoClient(os.environ.get("MONGODB_URI"))
        client.admin.command('ping')
        db_status = "healthy"
        client.close()
    except Exception:
        db_status = "unhealthy"
    
    # Check cache status
    cache_stats = performance_cache.get_cache_stats()
    cache_status = "healthy" if cache_stats.get("available") else "unhealthy"
    
    # Get middleware stats
    middleware_instance = None
    for middleware in app.user_middleware:
        if hasattr(middleware.cls, '__name__') and 'PerformanceMonitoringMiddleware' in middleware.cls.__name__:
            middleware_instance = middleware
            break
    
    stats = {}
    if middleware_instance:
        # This is a simplified approach - in production you'd want a better way to access stats
        stats = {"requests_processed": "N/A", "avg_response_time": "N/A"}
    
    return {
        "status": "healthy" if db_status == "healthy" and cache_status == "healthy" else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": db_status,
            "cache": cache_status,
            "api": "healthy"
        },
        "performance": stats,
        "cache_stats": cache_stats
    }

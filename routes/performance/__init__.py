"""
Performance routes module
Contains all performance monitoring, analytics, caching, and middleware
"""

from .monitoring import router as monitoring_router
from .analytics import router as analytics_router

# Aggregate all performance routers
performance_router = monitoring_router
performance_router.include_router(analytics_router, prefix="/analytics")

__all__ = ["performance_router"]

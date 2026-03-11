"""
Core routes module
Contains startup configuration and health check endpoints
"""

from .health import router as health_router

# Export the core router
core_router = health_router

__all__ = ["core_router"]

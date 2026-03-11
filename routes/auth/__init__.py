"""
Authentication routes module
Contains all authentication and authorization endpoints
"""

from .authentication import router as authentication_router
from .authorization import router as authorization_router

# Aggregate all auth routers
auth_router = authentication_router
auth_router.include_router(authorization_router)

__all__ = ["auth_router"]

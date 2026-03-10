"""
Student routes module
Contains all student-related endpoints for profiles, chat, and progress tracking
"""

from .profile import router as profile_router
from .chat import router as chat_router
from .progress import router as progress_router

# Aggregate all student routers without prefixes to maintain original paths
student_router = profile_router
student_router.include_router(chat_router)
student_router.include_router(progress_router)

__all__ = ["student_router"]

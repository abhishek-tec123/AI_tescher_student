"""
Activity routes module
Contains all activity tracking endpoints
"""

from .tracking import router as tracking_router

# Export the activity router
activity_router = tracking_router

__all__ = ["activity_router"]

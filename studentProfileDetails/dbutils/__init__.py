"""
Modular Database Utilities for Student Profile Management

This package provides organized database operations for:
- Database connections and configuration
- Student management and profiles
- Conversation history and chat operations
- Bookmark management
- Learning preferences and progress tracking
- Authentication and security

Example usage:
    from studentProfileDetails.dbutils import StudentManager, ConversationManager
    from studentProfileDetails.dbutils.database import get_database_connection
"""

from .database import DatabaseConnection
from .student_manager import StudentManager
from .conversation_manager import ConversationManager
from .bookmark_manager import BookmarkManager
from .preference_manager import PreferenceManager
from .auth_manager import AuthManager

__all__ = [
    'DatabaseConnection',
    'StudentManager', 
    'ConversationManager',
    'BookmarkManager',
    'PreferenceManager',
    'AuthManager'
]

__version__ = "1.0.0"

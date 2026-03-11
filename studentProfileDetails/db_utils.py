"""
Backward Compatibility Wrapper for Database Utilities

This file provides backward compatibility while delegating to the new modular dbutils package.
All functionality is now organized into separate modules within the dbutils package.

For new code, prefer importing directly from the dbutils modules:
    from studentProfileDetails.dbutils import StudentManager
    from studentProfileDetails.dbutils.student_manager import StudentManager
    from studentProfileDetails.dbutils.conversation_manager import ConversationManager
    etc.

This wrapper maintains compatibility with existing imports.
"""

# Import all classes and functions from the new modular structure
from .dbutils import (
    DatabaseConnection,
    StudentManager,
    ConversationManager,
    BookmarkManager,
    PreferenceManager,
    AuthManager,
    ChatSessionManager
)

# Import constants and utilities
from .dbutils.database import (
    MONGO_URI,
    DB_NAME,
    COLLECTION_NAME,
    DEFAULT_SUBJECT_PREFERENCE,
    DEFAULT_CORE_MEMORY,
    generate_student_id,
    normalize_student_preference,
    get_database_connection
)

# Re-export everything for backward compatibility
__all__ = [
    'DatabaseConnection',
    'StudentManager',
    'ConversationManager', 
    'BookmarkManager',
    'PreferenceManager',
    'AuthManager',
    'ChatSessionManager',
    'MONGO_URI',
    'DB_NAME',
    'COLLECTION_NAME',
    'DEFAULT_SUBJECT_PREFERENCE',
    'DEFAULT_CORE_MEMORY',
    'generate_student_id',
    'normalize_student_preference',
    'get_database_connection'
]

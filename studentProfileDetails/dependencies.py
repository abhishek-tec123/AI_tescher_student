"""
FastAPI Dependency Providers

This module provides dependency injection functions for FastAPI routes.
"""

from fastapi import Depends
from studentProfileDetails.dbutils import (
    StudentManager,
    ConversationManager,
    BookmarkManager,
    PreferenceManager,
    AuthManager,
    ChatSessionManager
)


def get_student_manager() -> StudentManager:
    """Dependency provider for StudentManager."""
    return StudentManager()


def get_conversation_manager() -> ConversationManager:
    """Dependency provider for ConversationManager."""
    return ConversationManager()


def get_bookmark_manager() -> BookmarkManager:
    """Dependency provider for BookmarkManager."""
    return BookmarkManager()


def get_preference_manager() -> PreferenceManager:
    """Dependency provider for PreferenceManager."""
    return PreferenceManager()


def get_auth_manager() -> AuthManager:
    """Dependency provider for AuthManager."""
    return AuthManager()


def get_chat_session_manager() -> ChatSessionManager:
    """Dependency provider for ChatSessionManager."""
    return ChatSessionManager()


# Create dependency instances for use in routes
StudentManagerDep = Depends(get_student_manager)
ConversationManagerDep = Depends(get_conversation_manager)
BookmarkManagerDep = Depends(get_bookmark_manager)
PreferenceManagerDep = Depends(get_preference_manager)
AuthManagerDep = Depends(get_auth_manager)
ChatSessionManagerDep = Depends(get_chat_session_manager)

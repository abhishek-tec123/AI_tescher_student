"""
Database Infrastructure Module

Provides core database connection management, configuration,
and shared utilities for all database operations.
"""

from pymongo import MongoClient, errors
from datetime import datetime
from typing import Optional, Dict, Any
import os
import random
import string
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
MONGO_URI = os.environ.get("MONGODB_URI")
DB_NAME = "teacher_ai"
COLLECTION_NAME = "students"

# Default configurations
DEFAULT_SUBJECT_PREFERENCE = {
    "level": "basic",
    "tone": "friendly",
    "learning_style": "step-by-step",
    "response_length": "long",
    "include_example": True,
    "common_mistakes": [],
    "confusion_counter": {},
    "quiz_score_history": [],
    "consecutive_low_scores": 0,
    "consecutive_perfect_scores": 0
}

DEFAULT_CORE_MEMORY = {
    "self_description": "",
    "study_preferences": "",
    "motivation_statement": "",
    "background_context": "",
    "current_focus_struggle": ""
}


def generate_student_id():
    """Generate a unique student ID with random suffix."""
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"std_{random_part}"


def normalize_student_preference(pref: dict) -> dict:
    """Normalize student preference data with default values."""
    defaults = {
        "level": "basic",
        "tone": "friendly",
        "include_example": False,
        "learning_style": "step-by-step",
        "confidence_level": "medium",
        "common_mistakes": []
    }

    for key, value in defaults.items():
        if key not in pref or pref[key] is None:
            pref[key] = value

    # Fix common_mistakes if stored as string
    if isinstance(pref.get("common_mistakes"), str):
        pref["common_mistakes"] = []

    return pref


class DatabaseConnection:
    """
    Core database connection manager.
    
    Handles MongoDB connection setup, collection management,
    and provides base database operations shared across modules.
    """
    
    def __init__(self, mongo_uri: str = None, db_name: str = None):
        """Initialize database connection with optional custom parameters."""
        self.mongo_uri = mongo_uri or MONGO_URI
        self.db_name = db_name or DB_NAME
        self.client = None
        self.db = None
        self._connect()
    
    def _connect(self):
        """Establish MongoDB connection."""
        try:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {e}")
    
    def get_collection(self, collection_name: str):
        """Get a MongoDB collection."""
        if self.db is None:
            raise ConnectionError("Database not connected")
        return self.db[collection_name]
    
    def get_students_collection(self):
        """Get the students collection."""
        return self.get_collection(COLLECTION_NAME)
    
    def initialize_db_collection(self):
        """Initialize database and collection if they don't exist."""
        if self.db_name not in self.client.list_database_names():
            print(f"Database '{self.db_name}' will be created on first insert.")
        else:
            print(f"Database '{self.db_name}' exists.")

        if COLLECTION_NAME not in self.db.list_collection_names():
            print(f"Collection '{COLLECTION_NAME}' does not exist. Creating...")
            students = self.get_students_collection()
            temp_id = students.insert_one({"_temp": True}).inserted_id
            students.delete_one({"_id": temp_id})
            print(f"Collection '{COLLECTION_NAME}' created.")
        else:
            print(f"Collection '{COLLECTION_NAME}' exists.")
    
    def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup."""
        self.close()


# Global database connection instance
_db_connection = None

def get_database_connection() -> DatabaseConnection:
    """Get or create global database connection instance."""
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
    return _db_connection


def with_database_connection(func):
    """Decorator to provide database connection to functions."""
    def wrapper(*args, **kwargs):
        db = get_database_connection()
        try:
            return func(db, *args, **kwargs)
        finally:
            # Don't close here as we're using a shared connection
            pass
    return wrapper

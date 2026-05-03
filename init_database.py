#!/usr/bin/env python3
"""
Idempotent MongoDB database initialization script.

Creates the database, all required collections, indexes, and a default admin user
if none exists. Safe to run multiple times.

Usage:
    python init_database.py
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient, errors
from bson import ObjectId

load_dotenv()

MONGO_URI = os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DB_NAME", "tutor_ai")

# Collections to ensure exist
COLLECTIONS = [
    "students",
    "admins",
    "bookmarks",
    "activity_logs",
    "shared_knowledge",
    "agent_performance_summary",
    "agent_performance_logs",
]


def ensure_collection(db, collection_name: str):
    """Create a collection if it doesn't exist using a temp doc."""
    if collection_name in db.list_collection_names():
        print(f"  ✅ Collection '{collection_name}' already exists.")
        return

    print(f"  🆕 Creating collection '{collection_name}'...")
    collection = db[collection_name]
    temp_id = collection.insert_one({"_temp": True}).inserted_id
    collection.delete_one({"_id": temp_id})
    print(f"  ✅ Collection '{collection_name}' created.")


def create_indexes(db):
    """Create indexes for performance."""
    print("\n📇 Creating indexes...")

    # students indexes
    db["students"].create_index("student_id", unique=True)
    db["students"].create_index("student_details.email")
    print("  ✅ students: student_id (unique), student_details.email")

    # admins indexes
    db["admins"].create_index("admin_id", unique=True)
    db["admins"].create_index("email", unique=True)
    print("  ✅ admins: admin_id (unique), email (unique)")

    # bookmarks indexes
    db["bookmarks"].create_index("student_id")
    print("  ✅ bookmarks: student_id")

    # activity_logs indexes (already created by ActivityTracker init, but ensure here too)
    db["activity_logs"].create_index([("timestamp", -1)])
    db["activity_logs"].create_index([("activity_type", 1)])
    db["activity_logs"].create_index([("target_id", 1)])
    print("  ✅ activity_logs: timestamp, activity_type, target_id")

    # shared_knowledge indexes
    db["shared_knowledge"].create_index("subject_agent_id")
    print("  ✅ shared_knowledge: subject_agent_id")

    # agent_performance_summary indexes
    db["agent_performance_summary"].create_index("subject_agent_id", unique=True)
    print("  ✅ agent_performance_summary: subject_agent_id (unique)")

    # agent_performance_logs indexes
    db["agent_performance_logs"].create_index("agent_id")
    db["agent_performance_logs"].create_index([("timestamp", -1)])
    print("  ✅ agent_performance_logs: agent_id, timestamp")


def seed_default_admin(db):
    """Create a default admin if the admins collection is empty."""
    admins = db["admins"]
    if admins.count_documents({}) > 0:
        print("\nℹ️  Admin users already exist. Skipping default admin creation.")
        return

    print("\n👤 Creating default admin user...")

    try:
        # Reuse the project's password hashing
        from studentProfileDetails.auth.password_utils import get_password_hash
        from studentProfileDetails.managers.admin_manager import AdminManager
    except ImportError as e:
        print(f"  ⚠️  Could not import AdminManager ({e}). Creating admin manually.")
        # Fallback manual creation with bcrypt
        try:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            password_hash = pwd_context.hash("Admin123!")
        except ImportError:
            print("  ❌ passlib not available. Cannot create admin.")
            return

        admin_doc = {
            "_id": ObjectId(),
            "admin_id": str(ObjectId()),
            "name": "Default Admin",
            "email": "admin@teacherai.com",
            "auth": {
                "password_hash": password_hash,
                "is_active": True,
                "last_login": None,
                "role": "admin"
            },
            "permissions": ["all"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        admins.insert_one(admin_doc)
        print("  ✅ Default admin created (manual fallback).")
        print(f"     Email: admin@teacherai.com")
        print(f"     Password: Admin123!")
        return

    admin_manager = AdminManager()
    try:
        admin_id, password = admin_manager.create_admin(
            name="Default Admin",
            email="admin@teacherai.com",
            password="Admin123!",
            permissions=["all"]
        )
        print("  ✅ Default admin created successfully.")
        print(f"     Email: admin@teacherai.com")
        print(f"     Password: Admin123!")
        print(f"     Admin ID: {admin_id}")
        print("  ⚠️  IMPORTANT: Change the default admin password immediately after first login!")
    except Exception as e:
        print(f"  ❌ Error creating default admin: {e}")
    finally:
        admin_manager.close()


def initialize_database():
    """Main initialization routine."""
    print("=" * 60)
    print("  TUTOR_AI DATABASE INITIALIZATION")
    print("=" * 60)

    if not MONGO_URI:
        print("❌ MONGODB_URI environment variable is not set.")
        sys.exit(1)

    print(f"\n🌐 MongoDB URI: {MONGO_URI[:30]}...")
    print(f"🗄️  Database: {DB_NAME}")

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        print("✅ MongoDB connection successful.")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)

    db = client[DB_NAME]

    print(f"\n📦 Ensuring collections exist in '{DB_NAME}'...")
    for coll_name in COLLECTIONS:
        ensure_collection(db, coll_name)

    create_indexes(db)
    seed_default_admin(db)

    client.close()

    print("\n" + "=" * 60)
    print("  INITIALIZATION COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print("\nYou can now start the application and log in as:")
    print("   Email: admin@teacherai.com")
    print("   Password: Admin123!")
    print()


if __name__ == "__main__":
    initialize_database()

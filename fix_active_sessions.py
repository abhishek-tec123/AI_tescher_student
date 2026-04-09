"""
Fix active_chat_sessions to point to latest sess_* sessions.
Removes old chat_* references.
"""

import os
import sys
from datetime import datetime

_root_dir = os.path.dirname(os.path.abspath(__file__))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from studentProfileDetails.dbutils import ChatSessionManager


def fix_active_sessions(student_id: str):
    """Update active_chat_sessions to point to latest sess_* per subject."""
    session_manager = ChatSessionManager()
    
    doc = session_manager.students.find_one(
        {"student_id": student_id},
        {"chat_sessions": 1, "active_chat_sessions": 1}
    )
    
    if not doc:
        print(f"❌ Student not found: {student_id}")
        return
    
    chat_sessions = doc.get("chat_sessions", {})
    active_sessions = doc.get("active_chat_sessions", {})
    
    print(f"\n📊 Student: {student_id}")
    print(f"   Total sessions: {len(chat_sessions)}")
    print(f"   Current active sessions: {active_sessions}")
    
    # Group sessions by subject
    sessions_by_subject = {}
    for sid, data in chat_sessions.items():
        subject = data.get("subject")
        if not subject:
            continue
        if subject not in sessions_by_subject:
            sessions_by_subject[subject] = []
        sessions_by_subject[subject].append({
            "session_id": sid,
            "updated_at": data.get("updated_at"),
            "title": data.get("title")
        })
    
    # Find latest session per subject
    updates = {}
    for subject, sessions in sessions_by_subject.items():
        # Sort by updated_at (newest first)
        sessions.sort(key=lambda x: x.get("updated_at") or datetime.min, reverse=True)
        latest = sessions[0]
        
        current_active = active_sessions.get(subject)
        
        if current_active != latest["session_id"]:
            print(f"\n🔄 {subject}:")
            print(f"   Current: {current_active}")
            print(f"   New:     {latest['session_id']} ({latest['title']})")
            updates[f"active_chat_sessions.{subject}"] = latest["session_id"]
    
    # Also remove any chat_* entries from active sessions
    for subject, sid in active_sessions.items():
        if sid.startswith("chat_"):
            print(f"\n🗑️  Removing old format: {subject} → {sid}")
            # Will be replaced above or unset
            if subject not in sessions_by_subject:
                updates[f"active_chat_sessions.{subject}"] = ""
    
    if updates:
        # Separate set and unset operations
        set_updates = {k: v for k, v in updates.items() if v != ""}
        unset_updates = {k: "" for k, v in updates.items() if v == ""}
        
        update_doc = {}
        if set_updates:
            update_doc["$set"] = set_updates
        if unset_updates:
            update_doc["$unset"] = unset_updates
        
        result = session_manager.students.update_one(
            {"student_id": student_id},
            update_doc
        )
        
        if result.modified_count > 0:
            print(f"\n✅ Active sessions updated")
        else:
            print(f"\n⚠️  No changes made")
    else:
        print(f"\n✅ All active sessions already correct")
    
    # Show final state
    final_doc = session_manager.students.find_one(
        {"student_id": student_id},
        {"active_chat_sessions": 1}
    )
    print(f"\n📋 Final active_chat_sessions:")
    for subject, sid in final_doc.get("active_chat_sessions", {}).items():
        print(f"   {subject}: {sid}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--student-id", default="std_EA9MG")
    args = parser.parse_args()
    fix_active_sessions(args.student_id)

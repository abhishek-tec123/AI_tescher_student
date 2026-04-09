"""
Cleanup old chat_* format sessions that are duplicates of sess_* sessions.
"""

import os
import sys
from datetime import datetime

# Add paths for imports
_root_dir = os.path.dirname(os.path.abspath(__file__))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from studentProfileDetails.dbutils import ChatSessionManager


def cleanup_old_sessions(student_id: str):
    """Remove chat_* sessions that have corresponding sess_* sessions."""
    session_manager = ChatSessionManager()
    
    # Get student document
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
    print(f"   Total chat sessions: {len(chat_sessions)}")
    
    # Find chat_* sessions
    old_sessions = [sid for sid in chat_sessions.keys() if sid.startswith("chat_")]
    new_sessions = [sid for sid in chat_sessions.keys() if sid.startswith("sess_")]
    
    print(f"   Old format (chat_*): {len(old_sessions)}")
    print(f"   New format (sess_*): {len(new_sessions)}")
    
    removed = 0
    for old_sid in old_sessions:
        old_data = chat_sessions[old_sid]
        subject = old_data.get("subject")
        title = old_data.get("title")
        
        # Check if there's a corresponding new session with same subject/title
        has_new_version = False
        for new_sid in new_sessions:
            new_data = chat_sessions[new_sid]
            if new_data.get("subject") == subject:
                # Same subject - likely a duplicate
                has_new_version = True
                break
        
        # Also check if this old session has 0 messages (empty)
        message_count = old_data.get("message_count", 0)
        
        if has_new_version or message_count == 0:
            print(f"\n🗑️  Removing: {old_sid}")
            print(f"   Title: {title}")
            print(f"   Subject: {subject}")
            print(f"   Messages: {message_count}")
            print(f"   Reason: {'Has new version' if has_new_version else 'Empty session'}")
            
            # Remove the old session
            result = session_manager.students.update_one(
                {"student_id": student_id},
                {"$unset": {f"chat_sessions.{old_sid}": ""}}
            )
            
            # Also remove from active_chat_sessions if present
            for subj, active_sid in list(active_sessions.items()):
                if active_sid == old_sid:
                    session_manager.students.update_one(
                        {"student_id": student_id},
                        {"$unset": {f"active_chat_sessions.{subj}": ""}}
                    )
                    print(f"   Removed from active_chat_sessions.{subj}")
            
            if result.modified_count > 0:
                removed += 1
                print(f"   ✅ Removed successfully")
            else:
                print(f"   ❌ Failed to remove")
    
    print(f"\n📈 Summary:")
    print(f"   Removed {removed} old sessions")
    print(f"   Kept {len(new_sessions)} new format sessions")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup old chat_* sessions")
    parser.add_argument("--student-id", default="std_EA9MG", help="Student ID to cleanup")
    
    args = parser.parse_args()
    cleanup_old_sessions(args.student_id)

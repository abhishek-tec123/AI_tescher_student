"""
Sync existing chat sessions from conversation history.

This script creates chat session entries in MongoDB for conversations
that have chat_session_id but no corresponding chat_sessions entry.
"""

import os
import sys
from datetime import datetime

# Add paths for imports
_root_dir = os.path.dirname(os.path.abspath(__file__))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from studentProfileDetails.dbutils import ChatSessionManager, StudentManager


def sync_chat_sessions_for_student(student_id: str):
    """Sync all chat sessions for a student from their conversation history."""
    session_manager = ChatSessionManager()
    student_manager = StudentManager()
    
    # Get student document
    student = student_manager.get_student(student_id)
    if not student:
        print(f"❌ Student not found: {student_id}")
        return {"error": "Student not found"}
    
    conversation_history = student.get("conversation_history", {})
    existing_chat_sessions = student.get("chat_sessions", {})
    
    print(f"\n📊 Student: {student_id}")
    print(f"   Subjects with conversations: {list(conversation_history.keys())}")
    print(f"   Existing chat sessions: {list(existing_chat_sessions.keys())}")
    
    # Group conversations by chat_session_id
    sessions_data = {}
    
    for subject, history in conversation_history.items():
        for convo in history:
            chat_session_id = convo.get("chat_session_id")
            if not chat_session_id:
                continue
            
            if chat_session_id not in sessions_data:
                sessions_data[chat_session_id] = {
                    "conversations": [],
                    "subject": subject,
                    "agent_id": convo.get("agent_id"),
                    "topic_name": convo.get("topic_name")
                }
            
            sessions_data[chat_session_id]["conversations"].append(convo)
    
    print(f"\n📁 Found {len(sessions_data)} unique chat sessions in conversation history")
    
    synced_count = 0
    created_count = 0
    skipped_count = 0
    
    for chat_session_id, data in sessions_data.items():
        # Check if already exists
        if chat_session_id in existing_chat_sessions:
            print(f"\n⏭️  Session already exists: {chat_session_id}")
            skipped_count += 1
            continue
        
        # Sort conversations by timestamp
        conversations = sorted(
            data["conversations"],
            key=lambda x: x.get("timestamp", datetime.min),
            reverse=True
        )
        
        if not conversations:
            continue
        
        # Get the most recent conversation for session info
        latest = conversations[0]
        earliest = conversations[-1]
        
        # Get last two messages (if available)
        last_messages = []
        for conv in conversations[:2]:
            ts = conv.get("timestamp")
            last_messages.append({
                "query": conv.get("query", ""),
                "response": conv.get("response", "")[:200],
                "timestamp": ts.isoformat() if ts else None
            })
        
        # Prepare session data
        session_data = {
            "title": data.get("topic_name") or f"New {data['subject']} Chat",
            "subject": data["subject"],
            "agent_type": "subject" if data.get("agent_id") else "general",
            "agent_name": data["subject"],
            "agent_id": data.get("agent_id"),
            "message_count": len(conversations),
            "last_query": latest.get("query", ""),
            "last_response": latest.get("response", "")[:200],
            "last_messages": last_messages,
            "created_at": earliest.get("timestamp", datetime.utcnow()),
            "updated_at": latest.get("timestamp", datetime.utcnow()),
            "chat_session_id": chat_session_id
        }
        
        # Create chat session in MongoDB
        result = session_manager.students.update_one(
            {"student_id": student_id},
            {
                "$set": {
                    f"chat_sessions.{chat_session_id}": session_data
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"\n✅ Created chat session: {chat_session_id}")
            print(f"   Title: {session_data['title']}")
            print(f"   Subject: {session_data['subject']}")
            print(f"   Messages: {session_data['message_count']}")
            created_count += 1
        else:
            print(f"\n⚠️  Failed to create session: {chat_session_id}")
        
        synced_count += 1
    
    # Update active_chat_sessions
    for chat_session_id, data in sessions_data.items():
        subject = data["subject"]
        # Only set as active if not already set
        active_sessions = student.get("active_chat_sessions", {})
        if subject not in active_sessions:
            session_manager.students.update_one(
                {"student_id": student_id},
                {"$set": {f"active_chat_sessions.{subject}": chat_session_id}}
            )
            print(f"   Set active session for {subject}: {chat_session_id}")
    
    print(f"\n📈 Summary for {student_id}:")
    print(f"   Total sessions found: {synced_count}")
    print(f"   Created: {created_count}")
    print(f"   Skipped (already exist): {skipped_count}")
    
    return {
        "synced": synced_count,
        "created": created_count,
        "skipped": skipped_count,
        "student_id": student_id
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync chat sessions from conversation history")
    parser.add_argument("--student-id", default="std_EA9MG", help="Student ID to sync")
    parser.add_argument("--all", action="store_true", help="Sync all students")
    
    args = parser.parse_args()
    
    if args.all:
        # Sync all students
        student_manager = StudentManager()
        students = student_manager.students.find({}, {"student_id": 1})
        for student in students:
            sync_chat_sessions_for_student(student["student_id"])
    else:
        # Sync specific student
        sync_chat_sessions_for_student(args.student_id)

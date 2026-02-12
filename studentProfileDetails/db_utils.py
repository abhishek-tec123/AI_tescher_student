from pymongo import MongoClient, errors
from datetime import datetime
from typing import Optional
from bson import ObjectId
import os
import uuid
from dotenv import load_dotenv
load_dotenv()

MONGO_URI = os.environ.get("MONGODB_URI")
DB_NAME = "teacher_ai"
COLLECTION_NAME = "students"

# ---------------------------
# Subject preferences: all keys stored in DB. New subject gets these defaults; then updated from queries.
# No confidence_level. All updatable keys: level, learning_style, response_length, include_example (+ common_mistakes, confusion_counter).
# ---------------------------
DEFAULT_SUBJECT_PREFERENCE = {
    "level": "basic",
    "tone": "friendly",
    "learning_style": "step-by-step",
    "response_length": "long",
    "include_example": True,
    "common_mistakes": [],
    "confusion_counter": {},
}
DEFAULT_CORE_MEMORY = {
    "self_description": "",
    "study_preferences": "",
    "motivation_statement": "",
    "background_context": "",
    "current_focus_struggle": ""
}

import random
import string
def generate_student_id():
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"std_{random_part}"

class StudentManager:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.students = self.db[COLLECTION_NAME]

    # ---------------------------
    # Initialize DB and Collection
    # ---------------------------
    def initialize_db_collection(self):
        if DB_NAME not in self.client.list_database_names():
            print(f"Database '{DB_NAME}' will be created on first insert.")
        else:
            print(f"Database '{DB_NAME}' exists.")

        if COLLECTION_NAME not in self.db.list_collection_names():
            print(f"Collection '{COLLECTION_NAME}' does not exist. Creating...")
            temp_id = self.students.insert_one({"_temp": True}).inserted_id
            self.students.delete_one({"_id": temp_id})
            print(f"Collection '{COLLECTION_NAME}' created.")
        else:
            print(f"Collection '{COLLECTION_NAME}' exists.")

    # ---------------------------
    # Create New Student
    # ---------------------------
    def create_student(self, name: str, email: str, class_name: str, subject_agent: dict | None = None) -> str:
        student_id = generate_student_id()

        student_doc = {
            "_id": student_id,
            "student_details": {
                "name": name,
                "email": email,
                "class": class_name,
                "subject_agent": subject_agent or {}
            },
            "student_core_memory": DEFAULT_CORE_MEMORY.copy(),
            "conversation_summary": {},
            "conversation_history": {},
            "subject_preferences": {},
            "metadata": {
                "created_at": datetime.utcnow(),
                "last_active": None,
                "last_conversation_id": {}
            }
        }

        self.students.insert_one(student_doc)

        return student_id

    def get_student(self, student_id: str):
        return self.students.find_one({"_id": student_id})

    def update_student(self, student_id: str, payload):
        update_data = {}

        data = payload.dict(exclude_none=True)

        if "name" in data:
            update_data["student_details.name"] = data["name"]

        if "email" in data:
            update_data["student_details.email"] = data["email"]

        if "class_name" in data:
            update_data["student_details.class"] = data["class_name"]

        if "subject_agent" in data:
            update_data["student_details.subject_agent"] = data["subject_agent"]

        if not update_data:
            return None

        result = self.students.update_one(
            {"_id": student_id},
            {"$set": update_data}
        )

        return result
    
    def delete_student(self, student_id: str):
        result = self.students.delete_one({"_id": student_id})
        return result

    # ---------------------------
    # Update Subject Preference
    # ---------------------------
    def update_subject_preference(self, student_id: str, subject: str, updates: dict) -> int:
        """
        Update only specific subject preferences (partial update).
        """
        if not updates:
            return 0

        update_fields = {
            f"subject_preferences.{subject}.{k}": v
            for k, v in updates.items()
        }

        result = self.students.update_one(
            {"_id": student_id},
            {"$set": update_fields}
        )

        return result.modified_count


    # ---------------------------
    # Get or Create Subject Preference
    # ---------------------------
    def get_or_create_subject_preference(self, student_id: str, subject: str) -> dict:
        doc = self.students.find_one({"_id": student_id}, {"subject_preferences": 1})

        if not doc:
            print(f"Student '{student_id}' not found. Creating student first.")
            self.create_student(student_id, {"class": "Unknown"})
            doc = self.students.find_one({"_id": student_id}, {"subject_preferences": 1})

        subject_preferences = doc.get("subject_preferences", {})

        if subject not in subject_preferences:
            print(f"Subject '{subject}' not found for student '{student_id}'. Creating with canonical schema.")

            default_subject_pref = dict(DEFAULT_SUBJECT_PREFERENCE)

            self.students.update_one(
                {"_id": student_id},
                {"$set": {f"subject_preferences.{subject}": default_subject_pref}}
            )
            subject_preferences[subject] = default_subject_pref

        # Always return full schema: merge with defaults so old docs (e.g. missing response_length) get canonical shape
        merged = {**DEFAULT_SUBJECT_PREFERENCE, **subject_preferences[subject]}
        return merged

    # ---------------------------
    # Add Conversation with quality score
    # ---------------------------
    from bson import ObjectId
    from datetime import datetime
    from typing import Optional, Dict

    def add_conversation(
        self,
        student_id: str,
        subject: str,
        query: str,
        response: str,
        feedback: str = "neutral",
        confusion_type: str = "NO_CONFUSION",
        evaluation: Optional[Dict] = None,
        quality_scores: Optional[Dict] = None   # ✅ NEW (optional)
    ) -> ObjectId:

        if feedback not in {"like", "dislike", "neutral"}:
            feedback = "neutral"

        conversation_id = ObjectId()
        timestamp = datetime.utcnow()

        # Base conversation document
        conversation_doc = {
            "_id": conversation_id,
            "query": query,
            "response": response,
            "feedback": feedback,
            "confusion_type": confusion_type,
            "timestamp": timestamp
        }

        # Optional fields
        if evaluation is not None:
            conversation_doc["evaluation"] = evaluation

        if quality_scores is not None:
            conversation_doc["quality_scores"] = quality_scores

        self.students.update_one(
            {"_id": student_id},
            {
                "$push": {
                    f"conversation_history.{subject}": {
                        "$each": [conversation_doc],
                        "$sort": {"timestamp": -1},
                        "$slice": 10   # keep last 10
                    }
                },
                "$set": {
                    "metadata.last_active": timestamp,
                    f"metadata.last_conversation_id.{subject}": conversation_id
                }
            },
            upsert=True
        )

        return conversation_id

    def list_students(self) -> list:
        """
        Returns simplified student list.
        If subject_agent not present → return null.
        """

        students = self.students.find(
            {},
            {
                "_id": 1,
                "student_details.name": 1,
                "student_details.email": 1,
                "student_details.class": 1,
                "student_details.subject_agent": 1
            }
        )

        result = []

        for student in students:
            details = student.get("student_details", {})

            subject_agent = details.get("subject_agent", None)

            result.append({
                "student_id": student.get("_id"),
                "name": details.get("name"),
                "email": details.get("email"),
                "class": details.get("class"),
                "subject_agent": subject_agent if subject_agent else None
            })

        return result

    # ---------------------------
    # Update Feedback
    # ---------------------------
    from bson import ObjectId
    def find_conversation_subject(self, conversation_id: ObjectId) -> str | None:
        doc = self.students.find_one(
            {
                "$or": [
                    {f"conversation_history.{subject}._id": conversation_id}
                    for subject in ["Science", "Math"]  # or dynamic list
                ]
            },
            {"conversation_history": 1}
        )

        if not doc:
            return None

        for subject, conversations in doc.get("conversation_history", {}).items():
            for c in conversations:
                if c["_id"] == conversation_id:
                    return subject

        return None

    def update_feedback_by_conversation_id(
        self,
        conversation_id: str,
        feedback: str
    ) -> int:

        conversation_id = ObjectId(conversation_id)

        subject = self.find_conversation_subject(conversation_id)
        if not subject:
            return 0

        result = self.students.update_one(
            {
                f"conversation_history.{subject}._id": conversation_id
            },
            {
                "$set": {
                    f"conversation_history.{subject}.$.feedback": feedback
                }
            }
        )

        return result.modified_count

    # ---------------------------
    # Update Subject Summary
    # ---------------------------
    def update_subject_summary(self, student_id: str, subject: str, summary: str) -> int:
        result = self.students.update_one(
            {"_id": student_id},
            {"$set": {f"conversation_summary.{subject}": summary}}
        )
        return result.modified_count
    
    # ---------------------------
    # Update Subject Preference
    # ---------------------------
    def update_subject_preference(self, student_id: str, subject: str, preference: dict) -> int:
        result = self.students.update_one(
            {"_id": student_id},
            {"$set": {f"subject_preferences.{subject}": preference}}
        )
        return result.modified_count
    # ---------------------------
    # Fetch Subject Summary
    # ---------------------------
    def get_subject_summary(self, student_id: str, subject: str) -> Optional[str]:
        doc = self.students.find_one(
            {"_id": student_id},
            {f"conversation_summary.{subject}": 1}
        )
        return doc.get("conversation_summary", {}).get(subject) if doc else None

    # ---------------------------
    # Get Conversation History by Subject
    # ---------------------------
    def get_conversation_history(
        self,
        student_id: str,
        subject: str,
        limit: Optional[int] = None
    ):
        doc = self.students.find_one(
            {"_id": student_id},
            {f"conversation_history.{subject}": 1}
        )

        if not doc:
            return []

        history = doc.get("conversation_history", {}).get(subject, [])

        # Sort by latest first
        history = sorted(
            history,
            key=lambda x: x.get("timestamp", datetime.min),
            reverse=True
        )

        # Apply limit ONLY if provided
        if limit is not None:
            history = history[:limit]

        # Serialize Mongo types (include confusion_type for progressive/degressive tracking)
        return [
            {
                "_id": str(h["_id"]),
                "query": h.get("query", ""),
                "response": h.get("response", ""),
                "feedback": h.get("feedback", "neutral"),
                "confusion_type": h.get("confusion_type", "NO_CONFUSION"),
                "timestamp": h["timestamp"].isoformat() if h.get("timestamp") else None
            }
            for h in history
        ]

    # -----------------------------------------------------------------------------------------------
    def summarize_and_store_conversation(
        self,
        student_id: str,
        subject: str,
        limit: Optional[int] = None,
        prompt: str = "Summarize the conversation clearly for revision."
    ) -> str:
        """
        Fetch conversation history → summarize → store in conversation_summary
        """

        history = self.get_conversation_history(
            student_id=student_id,
            subject=subject,
            limit=limit
        )

        if not history:
            raise ValueError("No conversation history available")

        # Extract text
        text_blocks = []
        for item in history:
            if item.get("query"):
                text_blocks.append(f"Q: {item['query']}")
            if item.get("response"):
                text_blocks.append(f"A: {item['response']}")

        combined_text = "\n\n".join(text_blocks)

        # Import summarizer
        from summrizeStdConv import summarize_text_with_groq  # ⚠️ update import path

        summary = summarize_text_with_groq(
            text=combined_text,
            prompt=prompt
        )

        # Store summary in MongoDB
        self.students.update_one(
            {"_id": student_id},
            {
                "$set": {
                    f"conversation_summary.{subject}": summary,
                    "metadata.last_active": datetime.utcnow()
                }
            }
        )

        return summary

    # ---------------------------
    # Close connection
    # ---------------------------
    def close(self):
        self.client.close()

def normalize_student_preference(pref: dict) -> dict:
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


# # ---------------------------
# # Optional: Example main for testing
# # ---------------------------
# if __name__ == "__main__":
#     # Create sample students
#     student_manager.create_student("stu_1001", {"name": "Alice", "age": 16, "class": "10A"})
#     student_manager.create_student("stu_1002", {"name": "Bob", "age": 17, "class": "11B"})
#     student_manager.close()

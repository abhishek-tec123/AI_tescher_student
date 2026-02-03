from pymongo import MongoClient, errors
from datetime import datetime
from typing import Optional
from bson import ObjectId
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

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
    def create_student(self, student_id: str, student_details: dict):
        student_doc = {
            "_id": student_id,
            "student_details": student_details,
            "conversation_summary": {},
            "conversation_history": {},
            "subject_preferences": {},  # each subject (Science, Math, ...) created on first use with DEFAULT_SUBJECT_PREFERENCE; keys updated from user queries
            "metadata": {
                "created_at": datetime.utcnow(),
                "last_active": None,
                "last_conversation_id": {}
            }
        }

        try:
            self.students.insert_one(student_doc)
            print(f"Student '{student_id}' created with default preferences.")
        except errors.DuplicateKeyError:
            # Student already exists, do nothing
            pass
    
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
    # Add Conversation
    # ---------------------------
    def add_conversation(
        self,
        student_id: str,
        subject: str,
        query: str,
        response: str,
        feedback: str = "neutral",
        confusion_type: str = "NO_CONFUSION",
        evaluation: dict = None
    ) -> ObjectId:

        if feedback not in {"like", "dislike", "neutral"}:
            feedback = "neutral"

        conversation_id = ObjectId()
        timestamp = datetime.utcnow()

        self.students.update_one(
            {"_id": student_id},
            {
                "$push": {
                    f"conversation_history.{subject}": {
                        "$each": [
                            {
                                "_id": conversation_id,
                                "query": query,
                                "response": response,
                                "feedback": feedback,
                                "confusion_type": confusion_type,
                                "evaluation": evaluation,
                                "timestamp": timestamp
                            }
                        ],
                        "$sort": {"timestamp": -1},
                        "$slice": 10   # ✅ KEEP ONLY LAST 10
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

    # ---------------------------
    # Update Feedback
    # ---------------------------
    def update_feedback(self, student_id: str, subject: str, feedback: str, conversation_id: Optional[str] = None) -> int:
        if feedback not in {"like", "dislike", "neutral"}:
            return 0

        if conversation_id is None:
            doc = self.students.find_one(
                {"_id": student_id},
                {f"metadata.last_conversation_id.{subject}": 1}
            )
            if not doc:
                return 0
            conversation_id = doc.get("metadata", {}).get("last_conversation_id", {}).get(subject)
            if not conversation_id:
                return 0

        result = self.students.update_one(
            {
                "_id": student_id,
                f"conversation_history.{subject}._id": ObjectId(conversation_id)
            },
            {
                "$set": {f"conversation_history.{subject}.$.feedback": feedback}
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

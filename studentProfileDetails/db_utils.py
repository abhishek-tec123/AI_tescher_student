from pymongo import MongoClient, errors
from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId
import os
import uuid
from dotenv import load_dotenv
from .auth.password_utils import get_password_hash, verify_password, generate_default_password
from .auth.AESPasswordUtils import encrypt_password

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
    # Create New Student with Authentication
    # ---------------------------
    def create_student_with_auth(
        self,
        name: str,
        email: str,
        class_name: str,
        password: Optional[str] = None,
        subject_agent: dict | None = None
    ) -> tuple[str, str]:

        student_id = generate_student_id()
        
        # Generate password if not provided
        if password is None:
            password = generate_default_password()
        
        # password_hash = get_password_hash(password) #----- this is for bycrypt
        encrypted_password = encrypt_password(password)

        student_doc = {
            # Let MongoDB auto-generate _id (ObjectId)
            "student_id": student_id,  # <-- separate custom ID

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
            "auth": {
                # "password_hash": password_hash,#----- this is for bycrypt
                "password_hash": encrypted_password,#----- this is for both way hashing
                "is_active": True,
                "last_login": None,
                "role": "student"
            },
            "metadata": {
                "created_at": datetime.utcnow(),
                "last_active": None,
                "last_conversation_id": {}
            }
        }

        self.students.insert_one(student_doc)

        return student_id, password

    # ---------------------------
    # Authentication Methods
    # ---------------------------
    def authenticate_user(self, email: str, password: str) -> Optional[dict]:
        student = self.students.find_one({
            "student_details.email": email,
            "auth.is_active": True
        })

        if not student:
            return None

        stored_value = student["auth"]["password_hash"]

        from studentProfileDetails.auth.AESPasswordUtils import decrypt_password

        is_valid = False

        # ---- Try bcrypt first ----
        try:
            is_valid = verify_password(password, stored_value)
        except Exception:
            # Not a bcrypt hash → try AES
            try:
                decrypted = decrypt_password(stored_value)
                if password == decrypted:
                    is_valid = True
            except Exception:
                is_valid = False

        if not is_valid:
            return None

        # Update last login
        self.students.update_one(
            {"student_id": student["student_id"]},
            {"$set": {"auth.last_login": datetime.utcnow()}}
        )

        return {
            "user_id": student["student_id"],
            "email": student["student_details"]["email"],
            "name": student["student_details"]["name"],
            "class": student["student_details"]["class"],
            "role": student["auth"]["role"],
            "is_active": student["auth"]["is_active"]
        }

    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        student = self.students.find_one({"student_details.email": email})
        if not student:
            return None
        
        return {
            "user_id": student["student_id"],
            "email": student["student_details"]["email"],
            "name": student["student_details"]["name"],
            "role": student["auth"]["role"],
            "is_active": student["auth"]["is_active"],
            "last_login": student["auth"].get("last_login"),
            "created_at": student["metadata"]["created_at"]
        }
    
    # def update_password(self, student_id: str, new_password: str) -> bool: #---------------this function for on way bycrypt algo---------------
    #     """Update user password."""
    #     password_hash = get_password_hash(new_password)
    #     result = self.students.update_one(
    #         {"student_id": student_id},
    #         {"$set": {"auth.password_hash": password_hash}}
    #     )
    #     return result.modified_count > 0
    def update_password(self, student_id: str, new_password: str) -> bool: #---------------this function for on way AES algo---------------
        encrypted_password = encrypt_password(new_password)
        result = self.students.update_one(
            {"student_id": student_id},
            {"$set": {"auth.password_hash": encrypted_password}}
        )
        return result.modified_count > 0
    def admin_update_std_password(self, student_id: str, encrypted_password: str) -> bool:
        result = self.students.update_one(
            {"student_id": student_id},
            {"$set": {"auth.password_hash": encrypted_password}}
        )
        return result.modified_count > 0

    def create_student(
        self,
        name: str,
        email: str,
        class_name: str,
        subject_agent: dict | None = None
    ) -> str:

        student_id = generate_student_id()

        student_doc = {
            # Let MongoDB auto-generate _id (ObjectId)
            "student_id": student_id,  # <-- separate custom ID

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
        return self.students.find_one({"student_id": student_id})

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
        # Handle password update
        if "password" in data:
            new_password = data["password"]
            update_data["auth.password_hash"] = encrypt_password(new_password)  # ✅ same key

        if not update_data:
            return None

        result = self.students.update_one(
            {"student_id": student_id},   # ✅ FIXED HERE
            {"$set": update_data}
        )

        return result
    
    def delete_student(self, student_id: str):
        result = self.students.delete_one({"student_id": student_id})
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
        # 🔹 Find student using student_id (NOT _id)
        doc = self.students.find_one(
            {"student_id": student_id},
            {"subject_preferences": 1}
        )

        # 🔹 If student doesn't exist → raise error
        if not doc:
            raise ValueError(f"Student '{student_id}' not found.")

        subject_preferences = doc.get("subject_preferences", {})

        # 🔹 If subject preference doesn't exist → create default
        if subject not in subject_preferences:
            default_subject_pref = dict(DEFAULT_SUBJECT_PREFERENCE)

            self.students.update_one(
                {"student_id": student_id},
                {"$set": {f"subject_preferences.{subject}": default_subject_pref}}
            )

            subject_preferences[subject] = default_subject_pref

        # 🔹 Always return canonical schema
        merged = {
            **DEFAULT_SUBJECT_PREFERENCE,
            **subject_preferences[subject]
        }

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
        quality_scores: Optional[Dict] = None,
        additional_data: Optional[Dict] = None
    ) -> str:
        """
        Adds a conversation entry for a student and subject.
        Automatically summarizes when history reaches 10 entries.
        Returns conversation_id (string).
        """

        if feedback not in {"like", "dislike", "neutral"}:
            feedback = "neutral"

        conversation_id = ObjectId()
        timestamp = datetime.utcnow()

        # -------------------------------
        # Build conversation document
        # -------------------------------
        conversation_doc = {
            "_id": conversation_id,
            "conversation_id": str(conversation_id),  # explicit field for API usage
            "query": query,
            "response": response,
            "feedback": feedback,
            "confusion_type": confusion_type,
            "timestamp": timestamp
        }

        if evaluation is not None:
            conversation_doc["evaluation"] = evaluation

        if quality_scores is not None:
            conversation_doc["quality_scores"] = quality_scores

        if additional_data is not None:
            conversation_doc.update(additional_data)

        # -------------------------------
        # Push conversation to history
        # -------------------------------
        self.students.update_one(
            {"student_id": student_id},
            {
                "$push": {
                    f"conversation_history.{subject}": {
                        "$each": [conversation_doc],
                        "$sort": {"timestamp": -1},
                        "$slice": 10  # keep last 10 only
                    }
                },
                "$set": {
                    "metadata.last_active": timestamp,
                    f"metadata.last_conversation_id.{subject}": str(conversation_id)
                }
            },
            upsert=True
        )

        # -------------------------------
        # Fetch updated history length
        # -------------------------------
        doc = self.students.find_one(
            {"student_id": student_id},
            {f"conversation_history.{subject}": 1}
        )

        history = doc.get("conversation_history", {}).get(subject, [])

        # -------------------------------
        # Auto-generate summary when 10 reached
        # -------------------------------
        if len(history) == 10:
            try:
                self.summarize_and_store_conversation(
                    student_id=student_id,
                    subject=subject,
                    limit=10
                )
            except Exception as e:
                print(f"Summary generation failed: {e}")

        return str(conversation_id)

    def list_students(self) -> list:
        """
        Returns simplified student list.
        If subject_agent not present → return null.
        """

        students = self.students.find(
            {},
            {
                "_id": 0,  # Exclude MongoDB _id
                "student_id": 1,  # Include custom student_id
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
                "student_id": student.get("student_id"),
                "name": details.get("name"),
                "email": details.get("email"),
                "class": details.get("class"),
                "subject_agent": subject_agent if subject_agent else None
            })

        return result

    # ---------------------------
    # Update Feedback
    # ---------------------------
    def update_feedback_by_conversation_id(
        self,
        conversation_id: str,
        feedback: str
    ) -> int:

        conversation_id = ObjectId(conversation_id)

        # Get all subject keys from ALL documents (not just one)
        sample_docs = self.students.find(
            {"conversation_history": {"$exists": True}},
            {"conversation_history": 1}
        )

        subjects = set()

        for doc in sample_docs:
            subjects.update(doc.get("conversation_history", {}).keys())
        if not subjects:
            return 0

        for subject in subjects:
            # Find the conversation to get quality_scores and rl_metadata
            doc = self.students.find_one(
                {f"conversation_history.{subject}._id": conversation_id},
                {f"conversation_history.{subject}.$": 1}
            )
            
            if doc and doc.get("conversation_history", {}).get(subject):
                conv = doc["conversation_history"][subject][0]
                quality_scores = conv.get("quality_scores", {})
                
                # Calculate RL Reward
                reward = 0.0
                if feedback == "like":
                    reward += 1.0
                elif feedback == "dislike":
                    reward -= 1.0
                    
                if quality_scores:
                    rag_relevance = quality_scores.get("rag_relevance", 0) / 100.0
                    completeness = quality_scores.get("answer_completeness", 0) / 100.0
                    hallucination = quality_scores.get("hallucination_risk", 0) / 100.0
                    reward += (rag_relevance * 0.2) + (completeness * 0.2) - (hallucination * 0.1)
                
                reward = round(reward, 3)

                # Update feedback and reward
                result = self.students.update_one(
                    {f"conversation_history.{subject}._id": conversation_id},
                    {
                        "$set": {
                            f"conversation_history.{subject}.$.feedback": feedback,
                            f"conversation_history.{subject}.$.rl_metadata.reward": reward
                        }
                    }
                )

                if result.modified_count > 0:
                    return 1

        return 0

    # ---------------------------
    # Update Subject Summary
    # ---------------------------
    def update_subject_summary(self, student_id: str, subject: str, summary: str) -> int:
        result = self.students.update_one(
            {"student_id": student_id},
            {"$set": {f"conversation_summary.{subject}": summary}}
        )
        return result.modified_count
    
    # ---------------------------
    # Update Subject Preference
    # ---------------------------
    def update_subject_preference(self, student_id: str, subject: str, preference: dict) -> int:
        result = self.students.update_one(
            {"student_id": student_id},
            {"$set": {f"subject_preferences.{subject}": preference}}
        )
        return result.modified_count
    # ---------------------------
    # Fetch Subject Summary
    # ---------------------------
    def get_subject_summary(self, student_id: str, subject: str) -> Optional[str]:
        doc = self.students.find_one(
            {"student_id": student_id},
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
            {"student_id": student_id},
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
        from studentProfileDetails.summrizeStdConv import summarize_text_with_groq  # ✅ Fixed import path

        summary = summarize_text_with_groq(
            text=combined_text,
            prompt=prompt
        )

        # Store summary in MongoDB
        self.students.update_one(
            {"student_id": student_id},
            {
                "$set": {
                    f"conversation_summary.{subject}": summary,
                    "metadata.last_active": datetime.utcnow()
                }
            }
        )

        return summary

    # ---------------------------
    # Get Chat History for Specific Agent (Subject)
    # ---------------------------
    def get_chat_history_by_agent(
        self,
        student_id: str,
        subject: str,
        limit: Optional[int] = None
    ) -> list[Dict[str, Any]]:
        """
        Returns chat history for a specific student and subject(agent).

        Output format:
        [
            {
                "student_id": "std_XXXX",
                "query": "...",
                "response": "...",
                "evaluation": {...}
            }
        ]
        """

        # 🔹 Fetch only required subject history
        doc = self.students.find_one(
            {"student_id": student_id},
            {f"conversation_history.{subject}": 1}
        )

        if not doc:
            return []

        history = doc.get("conversation_history", {}).get(subject, [])

        if not history:
            return []

        # 🔹 Apply limit if provided
        if limit:
            history = history[:limit]

        # 🔹 Format response
        formatted_history = []
        for convo in history:
            formatted_history.append({
                "student_id": student_id,
                "query": convo.get("query"),
                "response": convo.get("response"),
                "evaluation": convo.get("evaluation", {})
            })

        return formatted_history

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

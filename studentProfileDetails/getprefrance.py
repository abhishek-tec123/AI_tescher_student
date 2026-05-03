import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


class subjectPrefrance:
    def __init__(self):
        self.mongo_uri = os.environ.get("MONGODB_URI")
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[os.environ.get("DB_NAME", "tutor_ai")]
        self.students = self.db["students"]

    # Get subject preference only
    def get_subject_preference(self, student_id: str, subject: str) -> dict:
        student = self.students.find_one(
            {"_id": student_id},
            {"subject_preferences": 1, "_id": 0}
        )

        if not student:
            raise ValueError("Student not found")

        return student.get("subject_preferences", {}).get(subject, {})

# import json
# # Initialize
# STprefrance = subjectPrefrance()

# # Get subject preference
# subject_pref = STprefrance.get_subject_preference(
#     student_id="stu_1001",
#     subject="Science"
# )

# # Pretty-print as JSON
# print("Subject Preference:")
# print(json.dumps(subject_pref, indent=3))

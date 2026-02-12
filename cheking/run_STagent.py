# import os
# import sys
# import json

# # Ensure parent path is available
# sys.path.append(
#     os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# )

# from getprefrance import subjectPrefrance


# def fetch_std_subject_preference(student_id: str, subject: str) -> dict:

#     STprefrance = subjectPrefrance()

#     subject_pref = STprefrance.get_subject_preference(
#         student_id=student_id,
#         subject=subject
#     )

#     print(f"Subject Preference for {subject}:")
#     print(json.dumps(subject_pref, indent=3))

#     return subject_pref

# from studentAgent.student_agent import StudentAgent

# # 1️⃣ Fetch preference
# student_id = "stu_1001"
# subject = "Science"

# subject_pref = fetch_std_subject_preference(student_id, subject)

# # 2️⃣ Initialize StudentAgent separately
# stagent = StudentAgent()

# # 3️⃣ Ask a query using fetched preference
# response = stagent.ask(
#     query="Give me a plan to learn about Reactions",
#     class_name="10th",
#     subject=subject,
#     student_profile=subject_pref  # use fetched preference
# )





from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import sys

# Ensure parent path is available
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from getprefrance import subjectPrefrance
from studentAgent.student_agent import StudentAgent

app = FastAPI(title="Student Learning API")

# -------------------------------------------------
# Global Agent (loaded once at startup)
# -------------------------------------------------
student_agent: StudentAgent | None = None


# -----------------------------
# Request Schema
# -----------------------------
class STagentRequest(BaseModel):
    student_id: str
    subject: str
    class_name: str
    query: str


# -----------------------------
# Startup Event
# -----------------------------
@app.on_event("startup")
def startup_event():
    global student_agent
    print("🚀 Preloading StudentAgent and RetrieverAgent...")
    student_agent = StudentAgent()
    print("✅ StudentAgent loaded successfully")


# -----------------------------
# Helper Function
# -----------------------------
def fetch_std_subject_preference(student_id: str, subject: str) -> dict:
    st_preference = subjectPrefrance()
    return st_preference.get_subject_preference(
        student_id=student_id,
        subject=subject
    )


# -----------------------------
# API Endpoint
# -----------------------------
@app.post("/student/learning-plan")
def get_learning_plan(payload: STagentRequest):
    if student_agent is None:
        raise HTTPException(status_code=500, detail="StudentAgent not initialized")

    try:
        # 1️⃣ Fetch subject preference
        subject_pref = fetch_std_subject_preference(
            student_id=payload.student_id,
            subject=payload.subject
        )

        # 2️⃣ Ask query (reuse preloaded agent)
        response = student_agent.ask(
            query=payload.query,
            class_name=payload.class_name,
            subject=payload.subject,
            student_profile=subject_pref
        )

        return {
            "student_id": payload.student_id,
            "subject": payload.subject,
            "preferences": subject_pref,
            "learning_plan": response
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

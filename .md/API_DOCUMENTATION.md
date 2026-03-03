# Create Teacher AI Agent API Documentation TXT
# Including ONLY REQUEST BODIES (No Responses)

from textwrap import dedent
import pypandoc

content = dedent("""
TEACHER AI AGENT – API DOCUMENTATION (REQUEST BODIES ONLY)
===========================================================

Base URL:
https://your-domain.com/api/v1


============================================================
1. AUTHENTICATION
============================================================

Authentication Header:
Authorization: Bearer <your-jwt-token>


1.1 Create Admin
----------------
POST /auth/create-admin

Request Body:
{
  "username": "admin",
  "password": "securepassword",
  "email": "admin@example.com"
}


1.2 Create Student with Auth
----------------------------
POST /auth/create-student-with-auth

Request Body:
{
  "username": "student1",
  "password": "password123",
  "email": "student@example.com",
  "name": "John Doe"
}


1.3 Change Password
-------------------
POST /auth/change-password

Request Body:
{
  "current_password": "oldpassword",
  "new_password": "newpassword"
}


============================================================
2. STUDENT MANAGEMENT
============================================================

2.1 Create Student
------------------
POST /student/create-student

Request Body:
{
  "name": "John Doe",
  "email": "john@example.com",
  "class": "10th Grade",
  "subjects": ["Math", "Science"]
}


2.2 Update Student
------------------
PUT /student/{student_id}

Request Body:
{
  "name": "John Smith",
  "preferences": {
    "learning_style": "auditory",
    "response_length": "long"
  }
}


2.3 Submit Feedback
-------------------
POST /student/feedback

Request Body:
{
  "student_id": "student123",
  "agent_id": "agent456",
  "rating": 5,
  "feedback": "Very helpful explanation"
}


============================================================
3. AGENT MANAGEMENT
============================================================

3.1 Create Agent
----------------
POST /vectors/create_vectors
Content-Type: multipart/form-data

Form Data:
subject: Biology
class_: 10th Grade
agent_name: Biology Tutor
description: Expert biology teacher
teaching_tone: friendly
global_prompt_enabled: true
global_rag_enabled: false
files: [PDF documents]


3.2 Update Agent
----------------
PUT /vectors/{subject_agent_id}
Content-Type: multipart/form-data

Form Data:
agent_name: Updated Biology Tutor
global_prompt_enabled: true
global_rag_enabled: true


3.3 Query Agent
---------------
POST /student/agent-query

Request Body:
{
  "query": "What is photosynthesis?",
  "agent_id": "agent123",
  "student_id": "student123"
}


============================================================
4. GLOBAL PROMPTS MANAGEMENT
============================================================

4.1 Create Global Prompt
------------------------
POST /admin/global-prompts/

Request Body:
{
  "name": "Respectful Communication",
  "content": "Always communicate respectfully with students. Use encouraging language.",
  "priority": 1,
  "version": "v1"
}


4.2 Enable Global Prompt
------------------------
POST /admin/global-prompts/{prompt_id}/enable


4.3 Disable Global Prompt
-------------------------
POST /admin/global-prompts/{prompt_id}/disable


4.4 Edit Global Prompt
----------------------
PUT /admin/global-prompts/{prompt_id}

Request Body:
{
  "name": "Updated Respectful Communication",
  "content": "Always communicate respectfully with students. Use encouraging and positive language.",
  "priority": 1,
  "version": "v2"
}


4.5 Delete Global Prompt
------------------------
DELETE /admin/global-prompts/{prompt_id}


============================================================
5. SHARED KNOWLEDGE MANAGEMENT
============================================================

5.1 Upload Shared Document
---------------------------
POST /admin/shared-knowledge/upload
Content-Type: multipart/form-data

Form Data:
document_name: Biology Basics
description: Fundamental biology concepts
file: [PDF file]


5.2 Enable Document for Agent
------------------------------
POST /admin/shared-knowledge/{document_id}/enable

Request Body:
{
  "agent_id": "agent123",
  "agent_name": "Biology Tutor",
  "class_name": "10th Grade",
  "subject": "Biology"
}


============================================================
6. ADMIN OPERATIONS
============================================================

6.1 Update Base Prompt
-----------------------
POST /admin/update-base-prompt

Request Body:
{
  "prompt": "You are an expert AI teacher with extensive knowledge..."
}


6.2 Update Agent Global Settings
---------------------------------
POST /admin/agents/{agent_id}/global-settings

Request Body:
{
  "global_prompt_enabled": true,
  "global_rag_enabled": false
}


============================================================
7. VECTOR / SEARCH OPERATIONS
============================================================

7.1 Search Documents
--------------------
POST /vectors/search

Request Body:
{
  "query": "photosynthesis process",
  "agent_id": "agent123",
  "top_k": 5
}

""")

output_path = "/mnt/data/Teacher_AI_Agent_API_Request_Bodies_Only.txt"

pypandoc.convert_text(
    content,
    'plain',
    format='md',
    outputfile=output_path,
    extra_args=['--standalone']
)

output_path

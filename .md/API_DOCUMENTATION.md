# TEACHER AI AGENT – COMPLETE API DOCUMENTATION
# All Routes with Request Bodies Categorized

Base URL:
https://your-domain.com/api/v1

Authentication Header:
Authorization: Bearer <your-jwt-token>

============================================================
1. AUTHENTICATION ROUTES
============================================================

1.1 User Login
---------------
POST /auth/login

Request Body:
{
  "email": "user@example.com",
  "password": "password123"
}

1.2 Token Refresh
-----------------
POST /auth/refresh

Request Body:
{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}

1.3 Change Password
-------------------
POST /auth/change-password

Request Body:
{
  "current_password": "oldpassword",
  "new_password": "newpassword"
}

1.4 Get Current User (No Body)
------------------------------
GET /auth/me

============================================================
2. STUDENT MANAGEMENT ROUTES
============================================================

2.1 Create Student
------------------
POST /student/create-student

Request Body:
{
  "name": "John Doe",
  "email": "student@example.com",
  "class_name": "Class10A",
  "subject_agent": [
    {
      "subject": "Math",
      "agent_id": "agent123"
    }
  ]
}

2.2 Update Student
------------------
PUT /student/{student_id}

Request Body:
{
  "name": "John Smith",
  "email": "john.smith@example.com",
  "class_name": "Class10B",
  "subject_agent": [
    {
      "subject": "Science",
      "agent_id": "agent456"
    }
  ]
}

2.3 Get Student Subjects (No Body)
----------------------------------
GET /student/{student_id}/subjects

2.4 Get Student List (No Body)
-------------------------------
GET /student/student-list

2.5 Get Student Details (No Body)
-----------------------------------
GET /student/{student_id}

2.6 Delete Student (No Body)
-----------------------------
DELETE /student/{student_id}

============================================================
3. CHAT & CONVERSATION ROUTES
============================================================

3.1 Agent Query
---------------
POST /student/agent-query

Request Body:
{
  "student_id": "student123",
  "subject": "Math",
  "class_name": "Class10A",
  "query": "What is quadratic equation?",
  "chat_session_id": "session456"
}

3.2 Get Chat History (No Body)
------------------------------
GET /student/{student_id}/history/{subject}?limit=10

3.3 Submit Feedback
------------------
POST /student/feedback

Request Body:
{
  "conversation_id": "conv123",
  "feedback": "Very helpful explanation",
  "rating": 5
}

============================================================
4. CHAT SESSIONS ROUTES
============================================================

4.1 Create Chat Session
-----------------------
POST /student/chat-sessions

Request Body:
{
  "student_id": "student123",
  "title": "Math Homework Help"
}

4.2 Update Chat Session
-----------------------
PUT /student/{student_id}/chat-sessions/{chat_session_id}

Request Body:
{
  "title": "Updated Session Title"
}

4.3 Get Chat Sessions (No Body)
-------------------------------
GET /student/{student_id}/chat-sessions

4.4 Get Chat Session (No Body)
------------------------------
GET /student/{student_id}/chat-sessions/{chat_session_id}

4.5 Delete Chat Session (No Body)
----------------------------------
DELETE /student/{student_id}/chat-sessions/{chat_session_id}

4.6 Get Active Chat Session (No Body)
--------------------------------------
GET /student/{student_id}/active-chat-session/{subject}

4.7 Set Active Chat Session (No Body)
--------------------------------------
POST /student/{student_id}/active-chat-session/{subject}

4.8 Clear Active Chat Session (No Body)
----------------------------------------
DELETE /student/{student_id}/active-chat-session/{subject}

4.9 Get Chat Session History (No Body)
--------------------------------------
GET /student/{student_id}/chat-sessions/{chat_session_id}/history?limit=50

============================================================
5. BOOKMARKS ROUTES
============================================================

5.1 Create Bookmark
-------------------
POST /student/{student_id}/bookmarks

Request Body:
{
  "conversation_id": "conv123",
  "subject": "Math",
  "personal_notes": "Important formula for exam"
}

5.2 Update Bookmark
-------------------
PUT /student/bookmarks/{bookmark_id}

Request Body:
{
  "personal_notes": "Updated notes with more details"
}

5.3 Get Bookmarks (No Body)
--------------------------
GET /student/{student_id}/bookmarks?page=1&limit=10

5.4 Delete Bookmark (No Body)
------------------------------
DELETE /student/bookmarks/{bookmark_id}

============================================================
6. STUDENT ACTIVITY ROUTES
============================================================

6.1 Get Recent Activity (No Body)
--------------------------------
GET /student/{student_id}/recent-activity?limit=6&hours_back=24

============================================================
7. VECTOR/AGENT MANAGEMENT ROUTES
============================================================

7.1 Create Agent/Vectors
------------------------
POST /vectors/create_vectors
Content-Type: multipart/form-data

Form Data:
subject: Biology
class_: 10th Grade
agent_type: teacher_agent
agent_name: Biology Tutor
description: Expert biology teacher
teaching_tone: friendly
global_prompt_enabled: true
global_rag_enabled: false
files: [PDF documents]

7.2 Update Agent
----------------
PUT /vectors/{subject_agent_id}
Content-Type: multipart/form-data

Form Data:
class_: 10th Grade
subject: Biology
agent_name: Updated Biology Tutor
description: Updated description
teaching_tone: professional
global_prompt_enabled: true
global_rag_enabled: true
files: [PDF documents]

7.3 Get Agent (No Body)
-----------------------
GET /vectors/{subject_agent_id}

7.4 Delete Agent (No Body)
--------------------------
DELETE /vectors/{subject_agent_id}

7.5 Get Agents of Class
------------------------
POST /vectors/agent_of_class

Request Body:
{
  "class_name": "Class10A"
}

7.6 Get Student Subjects (No Body)
-----------------------------------
GET /vectors/student/{student_id}/subjects

7.7 Enable Shared Document for Agent
-------------------------------------
POST /vectors/{subject_agent_id}/shared-documents/enable

Request Body:
{
  "agent_id": "agent123",
  "agent_name": "Biology Tutor",
  "class_name": "10th Grade",
  "subject": "Biology"
}

7.8 Disable Shared Document for Agent
--------------------------------------
POST /vectors/{subject_agent_id}/shared-documents/disable

Form Data:
document_id: doc123

7.9 Get Agent Shared Documents (No Body)
-----------------------------------------
GET /vectors/{subject_agent_id}/shared-documents

============================================================
8. VECTOR SEARCH ROUTES
============================================================

8.1 Search Documents
--------------------
POST /vectors/search

Request Body:
{
  "query": "photosynthesis process",
  "class_": "10th Grade",
  "subject": "Biology"
}

============================================================
9. ADMIN MANAGEMENT ROUTES
============================================================

9.1 List Admins (No Body)
--------------------------
GET /admin/list-admins

9.2 Get Dashboard Counts (No Body)
----------------------------------
GET /admin/dashboard-counts

9.3 Get Global RAG Knowledge (No Body)
---------------------------------------
GET /admin/global-rag-knowledge

9.4 Get Global Prompts (No Body)
---------------------------------
GET /admin/global-prompts

============================================================
10. ADMIN PROMPT MANAGEMENT ROUTES
============================================================

10.1 Update Base Prompt
------------------------
POST /admin/update-base-prompt

Request Body:
{
  "prompt": "You are an expert AI teacher with extensive knowledge..."
}

10.2 Get Current Base Prompt (No Body)
---------------------------------------
GET /admin/current-base-prompt

10.3 Enable Global RAG
----------------------
POST /admin/global-prompt/enable

Request Body:
{
  "content": "Additional context for all AI responses..."
}

10.4 Disable Global RAG (No Body)
----------------------------------
POST /admin/global-prompt/disable

10.5 Get Global RAG Status (No Body)
------------------------------------
GET /admin/global-prompt/status

============================================================
11. ADMIN GLOBAL PROMPTS ROUTES
============================================================

11.1 Create Global Prompt
-------------------------
POST /admin/global-prompts/

Request Body:
{
  "name": "Respectful Communication",
  "content": "Always communicate respectfully with students...",
  "priority": 1,
  "version": "v1"
}

11.2 List Global Prompts (No Body)
----------------------------------
GET /admin/global-prompts/

11.3 Get Global Prompt (No Body)
--------------------------------
GET /admin/global-prompts/{prompt_id}

11.4 Update Global Prompt
-------------------------
PUT /admin/global-prompts/{prompt_id}

Request Body:
{
  "name": "Updated Respectful Communication",
  "content": "Always communicate respectfully with students...",
  "priority": 1,
  "version": "v2"
}

11.5 Delete Global Prompt (No Body)
-----------------------------------
DELETE /admin/global-prompts/{prompt_id}

11.6 Enable Global Prompt (No Body)
------------------------------------
POST /admin/global-prompts/{prompt_id}/enable

11.7 Disable Global Prompt (No Body)
-------------------------------------
POST /admin/global-prompts/{prompt_id}/disable

11.8 Get Highest Priority Enabled Prompt (No Body)
--------------------------------------------------
GET /admin/global-prompts/enabled/highest-priority

============================================================
12. ADMIN SYSTEM MANAGEMENT ROUTES
============================================================

12.1 Upload Shared Document
--------------------------
POST /admin/system/shared-knowledge/upload
Content-Type: multipart/form-data

Form Data:
document_name: Biology Basics
description: Fundamental biology concepts
files: [PDF files]

12.2 List Shared Documents (No Body)
------------------------------------
GET /admin/system/shared-knowledge

12.3 Delete Shared Document (No Body)
-------------------------------------
DELETE /admin/system/shared-knowledge/{document_id}

12.4 Enable Document for Agent
------------------------------
POST /admin/system/shared-knowledge/{document_id}/enable

Request Body:
{
  "agent_id": "agent123",
  "agent_name": "Biology Tutor",
  "class_name": "10th Grade",
  "subject": "Biology"
}

12.5 Disable Document for Agent
-------------------------------
POST /admin/system/shared-knowledge/{document_id}/disable

Request Body:
{
  "agent_id": "agent123"
}

12.6 Get Agent Enabled Documents (No Body)
-----------------------------------------
GET /admin/system/shared-knowledge/agent/{agent_id}

12.7 Get Shared Document Metadata (No Body)
--------------------------------------------
GET /admin/system/shared-knowledge/{document_id}

12.8 Preview Shared Document (No Body)
-------------------------------------
GET /admin/system/shared-knowledge/{document_id}/preview

12.9 List Global RAG Knowledge (No Body)
-----------------------------------------
GET /admin/system/global-rag-knowledge

12.10 Update Agent Global Settings
---------------------------------
POST /admin/system/agents/{agent_id}/global-settings

Request Body:
{
  "agent_id": "agent123",
  "global_prompt_enabled": true,
  "global_rag_enabled": false
}

12.11 Get Agent Global Settings (No Body)
-----------------------------------------
GET /admin/system/agents/{agent_id}/global-settings

============================================================
13. PERFORMANCE ANALYTICS ROUTES
============================================================

13.1 Get All Agents Performance (No Body)
-----------------------------------------
GET /performance/all-agents-performance

13.2 Get Single Agent Performance (No Body)
-------------------------------------------
GET /performance/agent-performance/{agent_id}

============================================================
14. ACTIVITY TRACKING ROUTES
============================================================

14.1 Get Recent Activities (No Body)
--------------------------------------
GET /activity/recent?limit=50&activity_types=login,query&hours_back=24

14.2 Get Activity Stats (No Body)
----------------------------------
GET /activity/stats?days_back=7

14.3 Get Activity Types (No Body)
----------------------------------
GET /activity/activity-types

============================================================
15. TOPICS EXTRACTION ROUTES
============================================================

15.1 Extract Topics from Agent (No Body)
----------------------------------------
GET /topics/extract/{subject_agent_id}

15.2 Preview Topics Extraction (No Body)
-----------------------------------------
GET /topics/extract/{subject_agent_id}/preview

============================================================
16. CORE SERVICES ROUTES
============================================================

16.1 Health Check (No Body)
---------------------------
GET /core/health

============================================================
17. STUDENT DOCUMENTS PREVIEW ROUTES
============================================================

17.1 Get Student Agent Documents (No Body)
-------------------------------------------
GET /student/{student_id}/agents/{agent_id}/documents

17.2 Get Document Metadata (No Body)
------------------------------------
GET /student/{student_id}/agents/{agent_id}/documents/{document_id}

17.3 Preview Document (No Body)
------------------------------
GET /student/{student_id}/agents/{agent_id}/documents/{document_id}/preview

17.4 Get Storage Info (No Body)
--------------------------------
GET /student/{student_id}/documents/storage-info

17.5 Get Shared Document Metadata (No Body)
--------------------------------------------
GET /student/{student_id}/shared-documents/{document_id}

17.6 Preview Shared Document (No Body)
-------------------------------------
GET /student/{student_id}/shared-documents/{document_id}/preview

============================================================
REQUEST BODY CATEGORIES SUMMARY
============================================================

**JSON Request Bodies:**
- Authentication: Login, Token Refresh, Password Change
- Student Management: Create/Update Student, Agent Query, Feedback
- Chat Sessions: Create/Update Sessions
- Bookmarks: Create/Update Bookmarks
- Vector Management: Get Agents by Class, Enable/Disable Documents
- Admin: Base Prompt Updates, Global Prompts CRUD, Agent Settings
- Search: Document Search Queries

**Form Data Request Bodies (Multipart):**
- Vector Creation: Agent creation with file uploads
- Agent Updates: Agent modification with file uploads  
- Shared Knowledge: Document uploads with metadata

**No Request Body (GET/DELETE):**
- All data retrieval endpoints
- Delete operations
- Status and health checks

**Authentication Required:**
- All endpoints except /auth/login and /core/health
- Admin-only endpoints marked in Admin sections
- Student-only access to own data in Student sections

# Student Learning API Documentation

## Overview

This API provides a comprehensive learning management system with AI-powered teaching agents, student management, and performance analytics.

**Base URL**: `http://localhost:8000/api/v1`
**Authentication**: Bearer Token (JWT)
**Content-Type**: `application/json`

## Setup

### Environment Variables Required
```bash
MONGODB_URI=your_mongodb_connection_string
GROQ_API_KEY=your_groq_api_key
```

### Authentication
Most endpoints require a valid JWT token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

---

## 1. Authentication Routes (`/api/v1/auth`)

### POST `/auth/login`
Login user and return JWT tokens.

**Request Body:**
```json
{
  "email": "student@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "user_id": "student123",
    "email": "student@example.com",
    "role": "student",
    "name": "John Doe"
  }
}
```

---

### POST `/auth/refresh`
Refresh access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

---

### GET `/auth/me`
Get current user information.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "user_id": "student123",
  "email": "student@example.com",
  "role": "student",
  "name": "John Doe",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### POST `/auth/change-password`
Change current user's password.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "current_password": "oldpassword",
  "new_password": "newpassword123"
}
```

**Response:**
```json
{
  "message": "Password changed successfully"
}
```

---

### POST `/auth/create-student-with-auth`
Create a new student with authentication (Admin only).

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "name": "Jane Smith",
  "email": "jane@example.com",
  "password": "password123",
  "class_name": "Grade10",
  "subject_agent": [
    {"subject": "Mathematics", "subject_agent_id": "math_agent_001"}
  ]
}
```

**Response:**
```json
{
  "message": "Student created successfully",
  "student_id": "student456"
}
```

---

### POST `/auth/create-admin`
Create a new admin (Admin only).

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "name": "Admin User",
  "email": "admin@example.com",
  "password": "adminpass123"
}
```

**Response:**
```json
{
  "message": "Admin created successfully",
  "admin_id": "admin789"
}
```

---

### POST `/auth/admin/admin-reset-student-password/{student_id}`
Reset student password (Admin only).

**Headers:** `Authorization: Bearer <admin_token>`

**URL Parameters:**
- `student_id` (string): Student ID

**Request Body:**
```json
{
  "current_password": "admin_password",
  "new_password": "newstudentpass"
}
```

**Response:**
```json
{
  "message": "Student password reset successfully"
}
```

---

## 2. Student Management Routes (`/api/v1/student`)

### POST `/student/agent-query`
Query the AI teaching agent.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "student_id": "student123",
  "subject": "Mathematics",
  "class_name": "Grade10",
  "query": "What is the Pythagorean theorem?"
}
```

**Response:**
```json
{
  "response": "The Pythagorean theorem states that in a right triangle...",
  "conversation_id": "conv_123456",
  "agent_metadata": {
    "agent_name": "Math Tutor",
    "subject": "Mathematics"
  },
  "evaluation": {
    "relevance_score": 0.95,
    "confidence_score": 0.88
  }
}
```

---

### POST `/student/create-student`
Create a new student (Admin only).

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "name": "New Student",
  "email": "newstudent@example.com",
  "class_name": "Grade9",
  "subject_agent": [
    {"subject": "Science", "subject_agent_id": "science_agent_001"}
  ]
}
```

**Response:**
```json
{
  "message": "Student created successfully",
  "student": {
    "student_id": "student789",
    "name": "New Student",
    "email": "newstudent@example.com",
    "class": "Grade9",
    "subject_agent": [{"subject": "Science", "subject_agent_id": "science_agent_001"}]
  }
}
```

---

### GET `/student/student-list`
Get list of students.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "total": 2,
  "students": [
    {
      "student_id": "student123",
      "name": "John Doe",
      "email": "john@example.com",
      "class": "Grade10",
      "subject_agent": [{"subject": "Mathematics", "subject_agent_id": "math_agent_001"}]
    }
  ]
}
```

---

### GET `/student/{student_id}`
Get student details.

**Headers:** `Authorization: Bearer <token>`

**URL Parameters:**
- `student_id` (string): Student ID

**Response:**
```json
{
  "student_id": "student123",
  "name": "John Doe",
  "email": "john@example.com",
  "class_name": "Grade10",
  "subject_agent": [{"subject": "Mathematics", "subject_agent_id": "math_agent_001"}],
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### PUT `/student/{student_id}`
Update student information.

**Headers:** `Authorization: Bearer <token>`

**URL Parameters:**
- `student_id` (string): Student ID

**Request Body:**
```json
{
  "name": "John Smith",
  "email": "johnsmith@example.com"
}
```

**Response:**
```json
{
  "message": "Student updated successfully"
}
```

---

### DELETE `/student/{student_id}`
Delete student (Admin only).

**Headers:** `Authorization: Bearer <admin_token>`

**URL Parameters:**
- `student_id` (string): Student ID

**Response:**
```json
{
  "message": "Student deleted successfully"
}
```

---

### GET `/student/{student_id}/history/{subject}`
Get chat history for a student and subject.

**Headers:** `Authorization: Bearer <token>`

**URL Parameters:**
- `student_id` (string): Student ID
- `subject` (string): Subject name

**Query Parameters:**
- `limit` (optional, integer): Number of history items to return

**Response:**
```json
[
  {
    "student_id": "student123",
    "query": "What is algebra?",
    "response": "Algebra is a branch of mathematics...",
    "evaluation": {"relevance_score": 0.92}
  }
]
```

---

### POST `/student/feedback`
Submit feedback for a conversation.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "conversation_id": "conv_123456",
  "feedback": {
    "rating": 5,
    "comment": "Very helpful explanation!",
    "helpful": true
  }
}
```

**Response:**
```json
{
  "message": "Feedback recorded successfully",
  "feedback_id": "feedback_789"
}
```

---

## 3. Admin Routes (`/api/v1/admin`)

### POST `/admin/update-base-prompt`
Update the base prompt for AI agents (Admin only).

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "prompt": "You are a helpful AI tutor. Always provide clear explanations..."
}
```

**Response:**
```json
{
  "message": "Base prompt updated successfully"
}
```

---

### GET `/admin/current-base-prompt`
Get the current base prompt (Admin only).

**Headers:** `Authorization: Bearer <admin_token>`

**Response:**
```json
{
  "base_prompt": "You are a helpful AI tutor. Always provide clear explanations..."
}
```

---

### GET `/admin/list-admins`
List all admins (Admin only).

**Headers:** `Authorization: Bearer <admin_token>`

**Response:**
```json
{
  "total": 2,
  "admins": [
    {
      "admin_id": "admin001",
      "name": "Admin User",
      "email": "admin@example.com",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

## 4. Vector Management Routes (`/api/v1/vectors`)

### GET `/vectors/status`
Health check for vector service.

**Response:**
```json
{
  "status": "ok"
}
```

---

### GET `/vectors/env_info`
Get environment information.

**Response:**
```json
{
  "mongodb_uri_set": true,
  "groq_api_key_set": true,
  "embedding_model_loaded": true
}
```

---

### GET `/vectors/db_status/{class_}/{subject}`
Get database status for specific class and subject.

**URL Parameters:**
- `class_` (string): Class name
- `subject` (string): Subject name

**Response:**
```json
{
  "database_exists": true,
  "collection_exists": true,
  "document_count": 1250,
  "last_updated": "2024-01-15T10:30:00Z"
}
```

---

### POST `/vectors/create_vectors`
Create vector embeddings from uploaded files.

**Headers:** `Authorization: Bearer <token>`

**Request Body (multipart/form-data):**
- `class_` (string): Class name
- `subject` (string): Subject name
- `agent_type` (optional, string): Type of agent
- `agent_name` (optional, string): Name of agent
- `description` (optional, string): Agent description
- `teaching_tone` (optional, string): Teaching style
- `files` (optional, files): PDF/DOCX files to process

**Response:**
```json
{
  "message": "Vectors created successfully",
  "subject_agent_id": "math_agent_001",
  "processed_files": 5,
  "total_chunks": 125,
  "embedding_count": 125
}
```

---

### POST `/vectors/search`
Search vector database.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "query": "Pythagorean theorem",
  "class_": "Grade10",
  "subject": "Mathematics"
}
```

**Response:**
```json
{
  "results": [
    {
      "content": "The Pythagorean theorem states that...",
      "score": 0.95,
      "metadata": {
        "source": "math_textbook.pdf",
        "page": 45
      }
    }
  ],
  "total_results": 10
}
```

---

### GET `/vectors/classes`
Get all available classes.

**Response:**
```json
{
  "classes": ["Grade9", "Grade10", "Grade11", "Grade12"]
}
```

---

### GET `/vectors/subjects`
Get subjects for a specific class.

**Query Parameters:**
- `selected_class` (string): Class name

**Response:**
```json
{
  "subjects": ["Mathematics", "Science", "English", "History"]
}
```

---

### GET `/vectors/all_collections`
Get all vector collections.

**Response:**
```json
{
  "collections": [
    {
      "database": "Grade10",
      "collection": "Mathematics",
      "document_count": 1250
    }
  ]
}
```

---

### POST `/vectors/agent_of_class`
Get all agents for a specific class.

**Request Body:**
```json
{
  "class_name": "Grade10"
}
```

**Response:**
```json
{
  "status": "success",
  "agents": [
    {
      "subject_agent_id": "math_agent_001",
      "subject": "Mathematics",
      "agent_name": "Math Tutor",
      "description": "Mathematics teaching agent"
    }
  ]
}
```

---

### GET `/vectors/{subject_agent_id}`
Get agent details.

**URL Parameters:**
- `subject_agent_id` (string): Agent ID

**Response:**
```json
{
  "subject_agent_id": "math_agent_001",
  "agent_metadata": {
    "agent_name": "Math Tutor",
    "subject": "Mathematics",
    "class": "Grade10",
    "description": "Mathematics teaching agent"
  },
  "document_count": 125,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### PUT `/vectors/{subject_agent_id}`
Update agent information and files.

**Headers:** `Authorization: Bearer <token>`

**URL Parameters:**
- `subject_agent_id` (string): Agent ID

**Request Body (multipart/form-data):**
- `class_` (optional, string): Class name
- `subject` (optional, string): Subject name
- `agent_name` (optional, string): Agent name
- `description` (optional, string): Agent description
- `teaching_tone` (optional, string): Teaching style
- `files` (optional, files): New files to add

**Response:**
```json
{
  "message": "Agent updated successfully",
  "updated_fields": ["agent_name", "description"],
  "new_files_processed": 3
}
```

---

### DELETE `/vectors/{subject_agent_id}`
Delete an agent.

**Headers:** `Authorization: Bearer <token>`

**URL Parameters:**
- `subject_agent_id` (string): Agent ID

**Response:**
```json
{
  "message": "Agent math_agent_001 deleted successfully",
  "deleted_chunks": 125
}
```

---

### GET `/vectors/student/{student_id}/subjects`
Get subjects available to a student.

**Headers:** `Authorization: Bearer <token>`

**URL Parameters:**
- `student_id` (string): Student ID

**Response:**
```json
{
  "subjects": [
    {
      "name": "Mathematics",
      "description": "Mathematics teaching agent",
      "subject_agent_id": "math_agent_001"
    }
  ]
}
```

---

## 5. Agent Performance Routes (`/api/v1/agent-performance`)

### GET `/agent-performance/{agent_id}`
Get detailed performance metrics for an agent.

**Headers:** `Authorization: Bearer <token>`

**URL Parameters:**
- `agent_id` (string): Agent ID

**Query Parameters:**
- `days` (optional, integer): Number of days to analyze (default: 30)

**Response:**
```json
{
  "agent_id": "math_agent_001",
  "agent_metadata": {
    "agent_name": "Math Tutor",
    "subject": "Mathematics"
  },
  "performance_period": "Last 30 days",
  "total_conversations": 150,
  "metrics": {
    "overall_score": 85.2,
    "pedagogical_value": 88.5,
    "confidence_score": 82.1,
    "relevance_score": 90.3,
    "completeness_score": 79.8
  },
  "performance_level": "Good",
  "health_indicators": {
    "status": "healthy",
    "color": "green"
  },
  "recommendations": [
    "Consider adding more examples to explanations"
  ]
}
```

---

### GET `/agent-performance/overview`
Get performance overview for all agents.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `days` (optional, integer): Number of days to analyze (default: 30)

**Response:**
```json
[
  {
    "agent_id": "math_agent_001",
    "agent_name": "Math Tutor",
    "class_name": "Grade10",
    "subject": "Mathematics",
    "overall_score": 85.2,
    "performance_level": "Good",
    "total_conversations": 150,
    "health_status": "healthy",
    "last_updated": "2024-01-15T10:30:00Z"
  }
]
```

---

### GET `/agent-performance/health-check`
Get health check for agents needing attention.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `threshold_score` (optional, float): Performance threshold (default: 60)

**Response:**
```json
{
  "critical_agents": [
    {
      "agent_id": "science_agent_002",
      "agent_name": "Science Tutor",
      "overall_score": 45.3,
      "performance_level": "Critical"
    }
  ],
  "total_agents": 5,
  "critical_count": 1,
  "alert_summary": {
    "Excellent": 1,
    "Good": 2,
    "Average": 1,
    "Critical": 1
  },
  "last_checked": "2024-01-15T10:30:00Z"
}
```

---

### GET `/agent-performance/trends/{agent_id}`
Get trend analysis for an agent.

**Headers:** `Authorization: Bearer <token>`

**URL Parameters:**
- `agent_id` (string): Agent ID

**Query Parameters:**
- `days` (optional, integer): Number of days to analyze (default: 30)

**Response:**
```json
{
  "agent_id": "math_agent_001",
  "trend_analysis": {
    "direction": "up",
    "change_percentage": 12.5,
    "trend_strength": "strong"
  },
  "performance_history": [
    {
      "date": "2024-01-01",
      "score": 75.2,
      "conversations": 12
    }
  ],
  "recommendations": [
    "Performance is improving, maintain current approach"
  ],
  "analysis_period": "Last 30 days"
}
```

---

### GET `/agent-performance/compare`
Compare performance between multiple agents.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `agent_ids` (array): List of agent IDs to compare
- `days` (optional, integer): Number of days to analyze (default: 30)

**Response:**
```json
{
  "comparison_period": "Last 30 days",
  "agents_compared": 2,
  "comparison_data": [
    {
      "agent_id": "math_agent_001",
      "agent_name": "Math Tutor",
      "overall_score": 85.2,
      "rank": 1,
      "metrics": {
        "pedagogical_value": 88.5,
        "confidence_score": 82.1
      }
    }
  ],
  "best_performer": {
    "agent_id": "math_agent_001",
    "agent_name": "Math Tutor"
  },
  "worst_performer": {
    "agent_id": "science_agent_002",
    "agent_name": "Science Tutor"
  }
}
```

---

### GET `/agent-performance/metrics/summary`
Get aggregated metrics summary across all agents.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `days` (optional, integer): Number of days to analyze (default: 30)

**Response:**
```json
{
  "period": "Last 30 days",
  "total_agents": 5,
  "total_conversations": 750,
  "average_score": 78.5,
  "performance_distribution": {
    "Excellent": 1,
    "Good": 2,
    "Average": 1,
    "Poor": 1
  },
  "health_distribution": {
    "healthy": 3,
    "warning": 1,
    "critical": 1
  },
  "top_performers": [
    {
      "agent_id": "math_agent_001",
      "agent_name": "Math Tutor",
      "overall_score": 85.2
    }
  ],
  "agents_needing_attention": 2
}
```

---

## 6. All Agents Performance Routes (`/api/v1/agents`)

### GET `/agents/all-agents-performance`
Get performance details for all agents.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "message": "Found 5 agents",
  "total_agents": 5,
  "agents": [
    {
      "subject_agent_id": "math_agent_001",
      "database": "Grade10",
      "collection": "Mathematics",
      "agent_metadata": {
        "agent_name": "Math Tutor",
        "subject": "Mathematics"
      },
      "performance": {
        "total_conversations": 150,
        "average_score": 85.2
      },
      "document_id": "doc_123456"
    }
  ]
}
```

---

### GET `/agents/agent-performance/{agent_id}`
Get performance details for a specific agent.

**Headers:** `Authorization: Bearer <token>`

**URL Parameters:**
- `agent_id` (string): Agent ID

**Response:**
```json
{
  "success": true,
  "message": "Performance data for math_agent_001",
  "agent_id": "math_agent_001",
  "source": "vector_documents",
  "performance": {
    "total_conversations": 150,
    "average_score": 85.2,
    "pedagogical_value": 88.5,
    "confidence_score": 82.1
  }
}
```

---

## Error Responses

All endpoints may return these common error responses:

### 401 Unauthorized
```json
{
  "detail": "Could not validate credentials"
}
```

### 403 Forbidden
```json
{
  "detail": "Access denied: You can only access your own data"
}
```

### 404 Not Found
```json
{
  "detail": "Student not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Error retrieving data: Database connection failed"
}
```

---

## Postman Collection Setup

1. **Import Environment Variables:**
   - `base_url`: `http://localhost:8000/api/v1`
   - `token`: `{{login_response.body.access_token}}`

2. **Authentication Flow:**
   - First call `/auth/login` to get token
   - Use token in Authorization header for subsequent requests
   - Use `/auth/refresh` when token expires

3. **File Uploads:**
   - For endpoints with file uploads, use `form-data` in Postman
   - Set `Content-Type` to `multipart/form-data`

4. **Testing Tips:**
   - Save responses to environment variables for chained requests
   - Use Postman tests to automatically extract and set tokens
   - Create separate collections for different user roles (student, admin)

---

## Rate Limiting & Best Practices

- Use appropriate HTTP methods (GET for data, POST for creation, PUT for updates, DELETE for removal)
- Include proper error handling in client applications
- Refresh tokens before they expire to maintain session
- Use pagination for large data sets
- Implement retry logic for network failures
- Log API responses for debugging purposes

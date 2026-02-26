# Teacher AI Agent - API Documentation

## Base URL
```
https://your-domain.com/api/v1
```

## Authentication
Most endpoints require JWT authentication. Include token in Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

---

## 🔐 Authentication

### Create Admin
```http
POST /auth/create-admin
```
**Request:**
```json
{
  "username": "admin",
  "password": "securepassword",
  "email": "admin@example.com"
}
```
**Response:**
```json
{
  "message": "Admin created successfully",
  "user_id": "admin123"
}
```

### Create Student with Auth
```http
POST /auth/create-student-with-auth
```
**Request:**
```json
{
  "username": "student1",
  "password": "password123",
  "email": "student@example.com",
  "name": "John Doe"
}
```

### Change Password
```http
POST /auth/change-password
```
**Request:**
```json
{
  "current_password": "oldpassword",
  "new_password": "newpassword"
}
```

---

## 👥 Student Management

### Create Student
```http
POST /student/create-student
```
**Request:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "class": "10th Grade",
  "subjects": ["Math", "Science"]
}
```
**Response:**
```json
{
  "student_id": "student123",
  "name": "John Doe",
  "status": "created"
}
```

### Get Student List
```http
GET /student/student-list
```
**Response:**
```json
{
  "students": [
    {
      "student_id": "student123",
      "name": "John Doe",
      "email": "john@example.com",
      "class": "10th Grade"
    }
  ],
  "total": 1
}
```

### Get Student Details
```http
GET /student/{student_id}
```
**Response:**
```json
{
  "student_id": "student123",
  "name": "John Doe",
  "email": "john@example.com",
  "class": "10th Grade",
  "subjects": ["Math", "Science"],
  "preferences": {
    "learning_style": "visual",
    "response_length": "medium"
  }
}
```

### Update Student
```http
PUT /student/{student_id}
```
**Request:**
```json
{
  "name": "John Smith",
  "preferences": {
    "learning_style": "auditory",
    "response_length": "long"
  }
}
```

### Delete Student
```http
DELETE /student/{student_id}
```

### Submit Feedback
```http
POST /student/feedback
```
**Request:**
```json
{
  "student_id": "student123",
  "agent_id": "agent456",
  "rating": 5,
  "feedback": "Very helpful explanation"
}
```

---

## 🎓 Agent Management

### Create Agent
```http
POST /vectors/create_vectors
Content-Type: multipart/form-data
```
**Form Data:**
```
subject: Biology
class_: 10th Grade
agent_name: Biology Tutor
description: Expert biology teacher
teaching_tone: friendly
global_prompt_enabled: true
global_rag_enabled: false
files: [PDF documents]
```
**Response:**
```json
{
  "status": "success",
  "subject_agent_id": "agent123",
  "message": "Agent created successfully",
  "num_chunks": 150,
  "prompt": {
    "enabled": true,
    "global_prompt_content": "Always communicate respectfully with students...",
    "full_prompt": "You are an expert teacher AI...\n\nAlways communicate respectfully with students...\n\nYou are an expert and supportive school teacher..."
  },
  "shared_documents": []
}
```

### Update Agent
```http
PUT /vectors/{subject_agent_id}
Content-Type: multipart/form-data
```
**Form Data:**
```
agent_name: Updated Biology Tutor
global_prompt_enabled: true
global_rag_enabled: true
```
**Response:**
```json
{
  "status": "success",
  "message": "Agent updated successfully",
  "prompt": {
    "enabled": true,
    "global_prompt_content": "Always communicate respectfully with students...",
    "full_prompt": "Complete prompt with global content..."
  },
  "shared_documents_status": "enabled"
}
```

### Get Agent Details
```http
GET /vectors/{subject_agent_id}
```
**Response:**
```json
{
  "subject_agent_id": "agent123",
  "agent_metadata": {
    "agent_name": "Biology Tutor",
    "global_prompt_enabled": true,
    "global_rag_enabled": false
  },
  "document_count": 150
}
```

### Delete Agent
```http
DELETE /vectors/{subject_agent_id}
```

### Query Agent
```http
POST /student/agent-query
```
**Request:**
```json
{
  "query": "What is photosynthesis?",
  "agent_id": "agent123",
  "student_id": "student123"
}
```
**Response:**
```json
{
  "answer": "Photosynthesis is the process by which plants convert sunlight into energy...",
  "sources": ["document1.pdf", "document2.pdf"],
  "confidence": 0.95
}
```

---

## 🌍 Global Prompts Management

### Create Global Prompt
```http
POST /admin/global-prompts/
```
**Request:**
```json
{
  "name": "Respectful Communication",
  "content": "Always communicate respectfully with students. Use encouraging language.",
  "priority": 1,
  "version": "v1"
}
```
**Response:**
```json
{
  "status": "success",
  "message": "Global prompt 'Respectful Communication' created successfully",
  "prompt": {
    "id": "prompt123",
    "name": "Respectful Communication",
    "content": "Always communicate respectfully...",
    "priority": 1,
    "enabled": false
  }
}
```

### List All Global Prompts
```http
GET /admin/global-prompts/
```
**Response:**
```json
{
  "status": "success",
  "total_prompts": 2,
  "enabled_prompts": 1,
  "prompts": [
    {
      "id": "prompt123",
      "name": "Respectful Communication",
      "content": "Always communicate respectfully...",
      "priority": 1,
      "enabled": true,
      "version": "v1"
    }
  ]
}
```

### Enable Global Prompt
```http
POST /admin/global-prompts/{prompt_id}/enable
```
**Response:**
```json
{
  "status": "success",
  "message": "Global prompt 'Respectful Communication' enabled successfully",
  "prompt": {
    "id": "prompt123",
    "enabled": true
  }
}
```

### Disable Global Prompt
```http
POST /admin/global-prompts/{prompt_id}/disable
```

### Get Highest Priority Enabled Prompt
```http
GET /admin/global-prompts/enabled/highest-priority
```
**Response:**
```json
{
  "status": "success",
  "prompt": {
    "id": "prompt123",
    "name": "Respectful Communication",
    "content": "Always communicate respectfully...",
    "priority": 1,
    "enabled": true
  }
}
```

---

## 📊 Performance Monitoring

### Get Performance Overview
```http
GET /performance/overview
```
**Response:**
```json
{
  "total_agents": 25,
  "agents": [
    {
      "agent_id": "agent123",
      "agent_name": "Biology Tutor",
      "class_name": "10th Grade",
      "subject": "Biology",
      "overall_score": 85.5,
      "performance_level": "Good",
      "total_conversations": 150,
      "last_updated": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Get Agent Performance Details
```http
GET /performance/agent/{agent_id}
```
**Response:**
```json
{
  "agent_id": "agent123",
  "agent_metadata": {
    "agent_name": "Biology Tutor",
    "global_prompt_enabled": true
  },
  "performance_period": "Last 30 days",
  "total_conversations": 150,
  "metrics": {
    "avg_response_time": 2.5,
    "satisfaction_score": 4.2,
    "accuracy_rate": 0.89
  },
  "performance_level": "Good",
  "health_indicators": {
    "response_quality": "Good",
    "engagement_level": "High"
  },
  "trend_analysis": {
    "direction": "improving",
    "change_percentage": 12.5
  },
  "recommendations": [
    "Consider adding more examples to explanations"
  ]
}
```

### Get Agent Trends
```http
GET /performance/agent/{agent_id}/trends?period=30d
```
**Response:**
```json
{
  "agent_id": "agent123",
  "period": "30d",
  "trends": {
    "performance_score": [
      {"date": "2024-01-01", "value": 78.5},
      {"date": "2024-01-15", "value": 85.5}
    ],
    "conversation_count": [
      {"date": "2024-01-01", "value": 120},
      {"date": "2024-01-15", "value": 150}
    ]
  }
}
```

### Get Metrics Summary
```http
GET /performance/metrics/summary
```
**Response:**
```json
{
  "total_agents": 25,
  "active_agents": 22,
  "avg_performance_score": 82.3,
  "total_conversations": 3500,
  "avg_satisfaction": 4.1,
  "performance_distribution": {
    "Excellent": 5,
    "Good": 12,
    "Average": 6,
    "Poor": 2
  }
}
```

---

## 📁 Shared Knowledge Management

### Upload Shared Document
```http
POST /admin/shared-knowledge/upload
Content-Type: multipart/form-data
```
**Form Data:**
```
document_name: Biology Basics
description: Fundamental biology concepts
file: [PDF file]
```
**Response:**
```json
{
  "status": "success",
  "document_id": "doc123",
  "message": "Document uploaded successfully",
  "document_name": "Biology Basics"
}
```

### List Shared Documents
```http
GET /admin/shared-knowledge
```
**Response:**
```json
{
  "status": "success",
  "documents": [
    {
      "document_id": "doc123",
      "document_name": "Biology Basics",
      "description": "Fundamental biology concepts",
      "uploaded_at": "2024-01-15T10:30:00Z",
      "used_by_agents": 5
    }
  ]
}
```

### Enable Document for Agent
```http
POST /admin/shared-knowledge/{document_id}/enable
```
**Request:**
```json
{
  "agent_id": "agent123",
  "agent_name": "Biology Tutor",
  "class_name": "10th Grade",
  "subject": "Biology"
}
```

### Get Agent Shared Documents
```http
GET /admin/shared-knowledge/agent/{agent_id}
```
**Response:**
```json
{
  "status": "success",
  "enabled_documents": [
    {
      "document_id": "doc123",
      "document_name": "Biology Basics",
      "enabled_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

## 🔧 Admin Operations

### Get Dashboard Stats
```http
GET /admin/dashboard-counts
```
**Response:**
```json
{
  "total_students": 150,
  "total_agents": 25,
  "total_documents": 500,
  "active_conversations": 45,
  "system_health": "Good"
}
```

### Update Base Prompt
```http
POST /admin/update-base-prompt
```
**Request:**
```json
{
  "prompt": "You are an expert AI teacher with extensive knowledge..."
}
```

### Get Current Base Prompt
```http
GET /admin/current-base-prompt
```
**Response:**
```json
{
  "base_prompt": "You are an expert AI teacher with extensive knowledge..."
}
```

### Update Agent Global Settings
```http
POST /admin/agents/{agent_id}/global-settings
```
**Request:**
```json
{
  "global_prompt_enabled": true,
  "global_rag_enabled": false
}
```
**Response:**
```json
{
  "status": "success",
  "global_prompt_enabled": true,
  "global_rag_enabled": false,
  "message": "Updated global settings for agent agent123"
}
```

---

## 🔍 Vector/Search Operations

### Search Documents
```http
POST /vectors/search
```
**Request:**
```json
{
  "query": "photosynthesis process",
  "agent_id": "agent123",
  "top_k": 5
}
```
**Response:**
```json
{
  "results": [
    {
      "content": "Photosynthesis is the process by which plants...",
      "source": "biology_textbook.pdf",
      "score": 0.95,
      "chunk_id": "chunk123"
    }
  ],
  "total_results": 3
}
```

### Get Classes
```http
GET /vectors/classes
```
**Response:**
```json
{
  "classes": ["9th Grade", "10th Grade", "11th Grade"]
}
```

### Get Subjects
```http
GET /vectors/subjects?selected_class=10th Grade
```
**Response:**
```json
{
  "subjects": ["Biology", "Chemistry", "Physics"]
}
```

---

## 📈 Activity Tracking

### Get Activity Types
```http
GET /activity/activity-types
```
**Response:**
```json
{
  "activity_types": [
    {
      "type": "agent_query",
      "description": "Student queried an agent"
    },
    {
      "type": "agent_created",
      "description": "New agent was created"
    }
  ]
}
```

---

## Health Check

### System Health
```http
GET /health
```
**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "database": "connected",
  "cache": "connected"
}
```

---

## Error Responses

All endpoints return consistent error format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": "Agent ID is required"
  }
}
```

**Common Error Codes:**
- `UNAUTHORIZED` - Authentication required
- `FORBIDDEN` - Insufficient permissions
- `NOT_FOUND` - Resource not found
- `VALIDATION_ERROR` - Invalid input data
- `INTERNAL_ERROR` - Server error

---

## Rate Limiting
- **Authentication endpoints**: 5 requests per minute
- **Search endpoints**: 100 requests per minute
- **Other endpoints**: 1000 requests per hour

## File Upload Limits
- **Maximum file size**: 50MB
- **Supported formats**: PDF, TXT, DOCX
- **Concurrent uploads**: 5 per user

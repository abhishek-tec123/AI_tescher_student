# Student Recent Activity API

## Endpoint
```
GET /{student_id}/recent-activity
```

## Query Parameters
- `limit` (optional, default=6, max=100): Maximum number of agents to show (latest conversation per agent)
- `hours_back` (optional, max=8760): Only show activities from last N hours

## Response Format
```json
{
  "student_id": "student123",
  "recent_activity": [
    {
      "conversation_id": "64f8a9b2c3d4e5f6g7h8i9j0",
      "subject": "mathematics",
      "agent_id": "agent_math_456",
      "query": "What is calculus?",
      "response_preview": "Calculus is the mathematical study of continuous change...",
      "timestamp": "2026-02-27T10:30:00Z",
      "time_ago": "2 hours ago",
      "feedback": "like",
      "confusion_type": "NO_CONFUSION"
    },
    {
      "conversation_id": "64f8a9b1c2d3e4f5g6h7i8j9",
      "subject": "physics",
      "agent_id": "agent_physics_789",
      "query": "Explain Newton's laws",
      "response_preview": "Newton's three laws of motion form the foundation of classical mechanics...",
      "timestamp": "2026-02-27T09:15:00Z",
      "time_ago": "3 hours ago",
      "feedback": "neutral",
      "confusion_type": "FORMULA_CONFUSION"
    }
  ],
  "total_count": 6,
  "agents_used_count": 6,
  "unique_agents": [
    {
      "subject": "mathematics",
      "agent_id": "agent_math_456",
      "conversation_count": 8
    },
    {
      "subject": "physics",
      "agent_id": "agent_physics_789",
      "conversation_count": 5
    },
    {
      "subject": "chemistry",
      "agent_id": "",
      "conversation_count": 2
    }
  ]
}
```

## Features
- **Latest Conversation Per Agent**: Shows the most recent conversation from each agent/subject
- **Agent Usage Summary**: Displays how many different agents the student uses
- **Detailed Agent Breakdown**: Lists each agent with conversation counts
- **Time-based Filtering**: Optional filtering by recent hours
- **Access Control**: Students can only view their own activity

## Security
- Students can only access their own activity data
- Admins can view any student's activity
- All responses are properly authenticated and authorized

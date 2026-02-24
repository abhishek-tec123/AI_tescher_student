# Activity Tracking System

This document describes the activity tracking system that monitors database changes for agents and students.

## Overview

The activity tracking system logs all major database operations and provides APIs to retrieve recent activities. This helps administrators monitor system usage and track changes.

## Features

- **Automatic Activity Logging**: Logs agent creation/updates and student creation/updates
- **Recent Activity API**: Retrieve recent activities with time formatting
- **Activity Statistics**: Get statistics broken down by activity type
- **Filtering Options**: Filter by activity type, time range, and limit results

## API Endpoints

### Get Recent Activities

```
GET /api/v1/activity/recent
```

**Query Parameters:**
- `limit` (optional, default=50): Maximum number of activities to return (1-200)
- `activity_types` (optional): Filter by specific activity types
- `hours_back` (optional): Only show activities from last N hours

**Response Format:**
```json
[
  {
    "id": "activity_id",
    "activity_type": "agent_created",
    "target_id": "agent_MATH001",
    "target_name": "Advanced Mathematics",
    "description": "New agent created for Mathematics",
    "time_ago": "5 mins ago",
    "timestamp": "2024-02-24T10:30:00.000Z",
    "metadata": {
      "subject": "Mathematics",
      "class": "Class 12",
      "action": "created"
    }
  }
]
```

### Get Activity Statistics

```
GET /api/v1/activity/stats
```

**Query Parameters:**
- `days_back` (optional, default=7): Number of days to look back for stats (1-365)

**Response Format:**
```json
{
  "total_activities": 25,
  "period_days": 7,
  "by_type": [
    {
      "activity_type": "agent_created",
      "count": 5,
      "latest": "2024-02-24T10:30:00.000Z"
    },
    {
      "activity_type": "student_created",
      "count": 15,
      "latest": "2024-02-24T09:15:00.000Z"
    }
  ]
}
```

### Get Activity Types

```
GET /api/v1/activity/activity-types
```

**Response Format:**
```json
{
  "activity_types": [
    {
      "value": "agent_created",
      "label": "Agent Created"
    },
    {
      "value": "agent_updated",
      "label": "Agent Updated"
    },
    {
      "value": "student_created",
      "label": "Student Created"
    },
    {
      "value": "student_updated",
      "label": "Student Updated"
    }
  ]
}
```

## Activity Types

| Activity Type | Description | Triggers |
|---------------|-------------|----------|
| `agent_created` | New agent created | When new teaching agent is created with documents |
| `agent_updated` | Agent updated | When agent metadata or documents are updated |
| `student_created` | New student joined | When new student account is created |
| `student_updated` | Student profile updated | When student details are modified |

## Automatic Logging

The system automatically logs activities when:

### Agent Activities
- **Agent Creation**: When new vectors are created via `/api/v1/vectors/create_vectors`
- **Agent Updates**: When agent metadata or documents are updated via `/api/v1/vectors/{agent_id}`

### Student Activities
- **Student Creation**: When new student is created via authentication system
- **Student Updates**: When student profile is updated via admin or self-service

## Time Formatting

The API provides human-readable time formatting:
- `< 60 seconds`: "X seconds ago"
- `< 1 hour`: "X mins ago"
- `< 24 hours`: "X hours ago"
- `≥ 24 hours`: "X days ago"

## Database Schema

Activities are stored in the `activity_logs` collection in the `teacher_ai` database:

```javascript
{
  "_id": ObjectId("..."),
  "activity_type": "agent_created",
  "target_id": "agent_MATH001",
  "target_name": "Advanced Mathematics",
  "description": "New agent created for Mathematics",
  "metadata": {
    "subject": "Mathematics",
    "class": "Class 12",
    "action": "created"
  },
  "timestamp": ISODate("2024-02-24T10:30:00.000Z")
}
```

## Security

All activity endpoints require admin authentication (`require_role("admin")`).

## Example Usage

### Frontend Integration

```javascript
// Get recent activities for dashboard
async function loadRecentActivities() {
  const response = await fetch('/api/v1/activity/recent?limit=10');
  const activities = await response.json();
  
  activities.forEach(activity => {
    console.log(`${activity.description} - ${activity.time_ago}`);
  });
}

// Get activity statistics for admin panel
async function loadActivityStats() {
  const response = await fetch('/api/v1/activity/stats?days_back=30');
  const stats = await response.json();
  
  console.log(`Total activities: ${stats.total_activities}`);
}
```

### Sample Activity Display

```
Agent updated
Advanced Mathematics
5 mins ago

New student joined
Physics 101
1 hour ago

Agent created
Chemistry Basics
2 hours ago
```

## Testing

Use the provided test script to verify the system:

```bash
python3 test_activity.py
```

This will create sample activities and test the retrieval functions.

## Troubleshooting

### Activity Tracking Disabled

If MongoDB is not available, the system will gracefully disable activity tracking and print warnings. The APIs will return empty results in this case.

### Missing Activities

Check that:
1. MongoDB is running and accessible
2. The `teacher_ai` database exists
3. The `activity_logs` collection has proper indexes
4. Activities are being logged in the relevant functions

## Performance Considerations

- Activities are indexed by `timestamp` for efficient sorting
- Additional indexes on `activity_type` and `target_id` for filtering
- Old activities can be archived or cleaned up manually if needed
- Consider implementing TTL (Time To Live) for automatic cleanup

# Topic-Restricted Chat Agent

A production-grade conversational agent for EdTech platforms that enforces strict topic boundaries. Students can interact ONLY with a selected topic (not the full syllabus), ensuring accurate, context-bound responses.

## Overview

The Topic-Restricted Chat Agent ensures that:
- **Strict topic isolation**: LLM only uses pre-loaded topic chunks
- **Zero database calls during chat**: All context loaded at session start
- **Prevents cross-topic leakage**: Built-in safety measures
- **Personalized responses**: Student profile-aware prompt engineering

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Session Manager  │  Context Loader  │  Retriever  │  LLM + Safety │
│  (Redis-backed)   │  (MongoDB)       │  (In-Memory)│  (Strict)     │
└─────────────────────────────────────────────────────────────────┘
```

### Components

1. **TopicSessionManager** - Manages chat sessions with Redis/Memory storage
2. **TopicContextLoader** - Pre-fetches all topic chunks at session start
3. **SelectiveContextRetriever** - In-memory similarity scoring (zero DB calls)
4. **StrictConstraintEngine** - Enforces topic boundaries via prompt engineering
5. **JailbreakDetector** - Detects and prevents prompt injection attempts
6. **TopicRestrictedChatAgent** - Main orchestrator

## Installation

The agent is already integrated into the existing StudentAgent system.

### Dependencies

```bash
# Core dependencies (already in requirements.txt)
pymongo>=4.5.0
redis>=4.6.0
numpy>=1.24.0
scipy>=1.11.0
langchain-huggingface>=0.0.3
sentence-transformers>=2.2.2

# Optional for API
fastapi>=0.103.0
uvicorn>=0.23.0
```

## Quick Start

### Method 1: Using StudentAgent (Recommended)

```python
from studentAgent.student_agent import StudentAgent

# Initialize agent
agent = StudentAgent()
agent.load()

# Create topic-restricted session
session = agent.initialize_topic_session(
    student_id="student_001",
    class_name="10th",
    subject="Science",
    topic_id="topic_photosynthesis",
    student_profile={
        "learning_style": "visual",
        "grade_level": "10th"
    }
)

session_id = session['session_id']

# Ask questions (strictly topic-bound)
response = agent.ask_topic_restricted(
    session_id=session_id,
    query="What is the role of chlorophyll?"
)

print(response['response'])
print(f"Context used: {response['context_used']}")
print(f"Chunks referenced: {response['chunks_referenced']}")

# End session
agent.end_topic_session(session_id)
```

### Method 2: Direct Agent Usage

```python
from studentAgent.topic_restricted import TopicRestrictedChatAgent
import asyncio

async def main():
    # Initialize
    agent = TopicRestrictedChatAgent()
    await agent.initialize()
    
    # Create session
    session = await agent.initialize_session(
        student_id="student_002",
        class_name="9th",
        subject="Mathematics",
        topic_id="topic_algebra",
        student_profile={"grade_level": "9th"}
    )
    
    session_id = session['session_id']
    
    # Chat
    response = await agent.chat(
        session_id=session_id,
        query="How do I solve linear equations?"
    )
    
    print(response['response'])
    
    # End session
    await agent.end_session(session_id)

asyncio.run(main())
```

### Method 3: FastAPI Integration

```python
from fastapi import FastAPI
from studentAgent.api.topic_chat_routes import register_routes

app = FastAPI()

# Register topic chat routes
register_routes(app)

# Endpoints available:
# POST /api/v1/topic-chat/session           - Create session
# POST /api/v1/topic-chat/{session_id}/ask  - Send message
# GET  /api/v1/topic-chat/{session_id}      - Get session status
# DELETE /api/v1/topic-chat/{session_id}    - End session
```

## API Endpoints

### Create Session
```bash
POST /api/v1/topic-chat/session
Content-Type: application/json

{
    "student_id": "student_001",
    "class_name": "10th",
    "subject": "Science",
    "topic_id": "topic_photosynthesis",
    "student_profile": {
        "learning_style": "visual",
        "grade_level": "10th"
    }
}
```

Response:
```json
{
    "session_id": "sess_abc123",
    "topic": {
        "topic_id": "topic_photosynthesis",
        "topic_name": "Photosynthesis"
    },
    "context_stats": {
        "total_chunks": 45,
        "total_tokens": 9000,
        "estimated_context_window": "45%"
    },
    "message": "Session initialized for topic: Photosynthesis"
}
```

### Send Message
```bash
POST /api/v1/topic-chat/sess_abc123/ask
Content-Type: application/json

{
    "query": "What is the role of chlorophyll?"
}
```

Response:
```json
{
    "response": "Chlorophyll is the pigment that...",
    "context_used": true,
    "chunks_referenced": ["chunk_001", "chunk_003"],
    "retrieval_info": {
        "status": "success",
        "chunks_selected": 2,
        "scores": {"chunk_001": 0.85, "chunk_003": 0.72}
    },
    "session_id": "sess_abc123",
    "safety_flag": false
}
```

### Get Session Status
```bash
GET /api/v1/topic-chat/sess_abc123
```

### End Session
```bash
DELETE /api/v1/topic-chat/sess_abc123
```

## Configuration

### Environment Variables

```bash
# MongoDB
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM
GROQ_API_KEY=gsk_xxxxx
LLM_TEMPERATURE=0.3

# Topic Agent Settings
TOPIC_MAX_CONTEXT_CHUNKS=5
TOPIC_SIMILARITY_THRESHOLD=0.3
TOPIC_SESSION_TTL=1800
```

### Agent Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_context_chunks` | 5 | Number of chunks to retrieve per query |
| `similarity_threshold` | 0.3 | Minimum similarity score for chunk selection |
| `session_ttl` | 1800 | Session timeout in seconds |

## Safety Features

### Topic Boundary Enforcement

The agent enforces topic boundaries through multiple layers:

1. **Pre-filtering**: Only topic-specific chunks loaded at session start
2. **Similarity threshold**: Chunks must score ≥0.3 to be used
3. **Strict prompt constraints**: System prompt explicitly forbids external knowledge
4. **Response validation**: Post-hoc check for hallucination indicators

### Jailbreak Detection

Automatically detects and blocks:
- "Ignore previous instructions" attempts
- Prompt injection patterns
- Encoding obfuscation (base64, unicode escapes)
- Suspicious character ratios
- Off-topic indicators

### Off-Topic Handling

When a query is off-topic:
```json
{
    "response": "I can only answer questions about Photosynthesis based on your study materials...",
    "context_used": false,
    "off_topic": true
}
```

## How It Works

### Session Initialization

```
Student selects topic
    ↓
Load ALL chunks for topic from MongoDB
    ↓
Build metadata index (embeddings in memory)
    ↓
Store full chunks in Redis cache
    ↓
Return session_id
```

### Chat Flow

```
Student asks question
    ↓
Embed query (cached)
    ↓
Score against metadata (in-memory, no DB call)
    ↓
Select top-K chunks by similarity
    ↓
Fetch full content from Redis cache
    ↓
Build strict constraint prompt
    ↓
Call LLM with constrained context
    ↓
Validate response
    ↓
Return answer
```

## Performance

- **First query latency**: ~200-500ms (session pre-load)
- **Subsequent queries**: ~100-300ms (no DB calls)
- **Memory usage**: ~50-100KB per session (metadata only)
- **Session TTL**: 30 minutes (configurable)

## File Structure

```
studentAgent/
├── topic_restricted/
│   ├── __init__.py                      # Package exports
│   ├── topic_session_manager.py         # Session lifecycle
│   ├── topic_context_loader.py          # Pre-fetch chunks
│   ├── selective_retriever.py           # In-memory scoring
│   ├── constraint_engine.py             # Prompt construction
│   ├── jailbreak_detector.py            # Safety checks
│   ├── topic_restricted_chat_agent.py   # Main orchestrator
│   └── example_usage.py                 # Usage examples
├── api/
│   └── topic_chat_routes.py             # FastAPI routes
└── student_agent.py                     # Extended with topic methods
```

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Session not found | Session expired or invalid ID | Create new session |
| No relevant chunks | Query off-topic or threshold too high | Lower threshold or rephrase query |
| Embedding failed | Model not loaded | Check model cache |
| MongoDB connection | Invalid URI or network issue | Check MONGODB_URI env var |

## Testing

```bash
# Run example
python studentAgent/topic_restricted/example_usage.py

# Test API routes
python studentAgent/api/topic_chat_routes.py
```

## Integration with Existing System

The topic-restricted agent integrates seamlessly with the existing codebase:

- Reuses `RetrievalOrchestratorAgent` infrastructure
- Uses existing `ModelCache` for embeddings
- Compatible with existing MongoDB Atlas vector collections
- Works with existing student profile system

## License

Part of the AI Teacher-Student platform.

## Support

For issues or questions, refer to:
- Design document: `.windsurf/plans/topic-restricted-chat-agent-design-d68939.md`
- Example usage: `studentAgent/topic_restricted/example_usage.py`

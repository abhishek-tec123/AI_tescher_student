# Topic Extraction Agent Usage Guide

## Overview

The Topic Extraction Agent analyzes content stored in a subject agent's vector database and extracts a structured hierarchy of topics and subtopics. This helps students understand what topics are covered by each agent and navigate the available content.

## ✅ Implementation Status

**FULLY FUNCTIONAL** - The topic extraction agent is now working with direct LLM integration and successfully extracting topics from real content.

### Recent Test Results
- **Agent**: agent_TZKF8 (Social Science, Grade 8)
- **Chunks Analyzed**: 52
- **Topics Extracted**: 10 main topics with subtopics
- **Sample Topics**: Governance and Democracy, The Parliamentary System, Indian Parliament and Democracy
- **Confidence Scores**: 80-95% range

## API Endpoints

### 1. Extract Topics from Agent
**Endpoint:** `GET /api/v1/topics/extract/{subject_agent_id}`

**Description:** Extracts topics and subtopics from a subject agent's stored content.

**Parameters:**
- `subject_agent_id` (path): ID of the subject agent to analyze
- `max_topics` (query, optional): Maximum number of topics to return (1-50, default: 20)
- `include_subtopics` (query, optional): Whether to include subtopics (default: true)

**Example Request:**
```bash
GET /api/v1/topics/extract/agent_ABC123?max_topics=10&include_subtopics=true
```

**Response Format:**
```json
{
  "status": "success",
  "subject_agent_id": "agent_ABC123",
  "db_name": "10th",
  "collection_name": "Science",
  "topics": [
    {
      "topic": "Photosynthesis",
      "confidence": 0.95,
      "subtopics": [
        {"subtopic": "Light-dependent reactions", "confidence": 0.88},
        {"subtopic": "Calvin cycle", "confidence": 0.92}
      ],
      "chunk_count": 15
    },
    {
      "topic": "Cell Structure",
      "confidence": 0.89,
      "subtopics": [
        {"subtopic": "Plant cells", "confidence": 0.85},
        {"subtopic": "Animal cells", "confidence": 0.87}
      ],
      "chunk_count": 12
    }
  ],
  "total_chunks_analyzed": 50,
  "extraction_metadata": {
    "model_used": "sentence-transformers/all-MiniLM-L6-v2",
    "extraction_time": "2024-01-01T12:00:00Z",
    "max_topics_requested": 10,
    "include_subtopics": true
  }
}
```

### 2. Preview Topics Extraction
**Endpoint:** `GET /api/v1/topics/extract/{subject_agent_id}/preview`

**Description:** Faster preview version that analyzes limited samples to give a quick overview.

**Parameters:**
- `subject_agent_id` (path): ID of the subject agent
- `sample_size` (query, optional): Number of content samples to analyze (1-20, default: 5)

**Response:** Same format as full extraction but with limited topics and no subtopics.

## How It Works

1. **Content Retrieval**: The agent retrieves all document chunks stored for the specified subject agent from MongoDB Atlas.

2. **Content Analysis**: The chunks are analyzed using LLM to identify main topics and subtopics covered in the educational content.

3. **Topic Organization**: Similar topics are grouped together and organized into a hierarchical structure with confidence scores.

4. **Response Generation**: Returns a structured JSON with topics, subtopics, confidence scores, and metadata.

## Usage Examples

### For Students
Students can call this endpoint to see what topics are available in a subject agent before starting a conversation:

```javascript
// Get topics for a Science agent
const response = await fetch('/api/v1/topics/extract/agent_SCI123');
const data = await response.json();

console.log('Available topics:', data.topics);
```

### For Frontend Applications
Display the topic structure to help students navigate:

```javascript
function displayTopics(topics) {
  topics.forEach(topic => {
    console.log(`📚 ${topic.topic} (confidence: ${topic.confidence})`);
    
    if (topic.subtopics && topic.subtopics.length > 0) {
      topic.subtopics.forEach(subtopic => {
        console.log(`  📖 ${subtopic.subtopic} (confidence: ${subtopic.confidence})`);
      });
    }
  });
}
```

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- **404**: Subject agent not found
- **500**: Internal server error during extraction
- **400**: Invalid parameters

Example error response:
```json
{
  "detail": "Subject agent agent_INVALID123 not found or invalid"
}
```

## Implementation Details

### Agent Class
The `TopicExtractionAgent` class is located at:
- File: `Teacher_AI_Agent/agents/topic_extraction_agent.py`
- Methods: `extract_topics_from_agent()`, `_analyze_content_structure()`, `_organize_topics_hierarchy()`

### Dependencies
- MongoDB Atlas for content storage
- HuggingFaceEmbeddings for text processing (optional)
- LLM integration for topic analysis
- FastAPI for REST API endpoints

### Performance Considerations
- Topic extraction can be resource-intensive for large content sets
- Use the preview endpoint for quick overviews
- Consider caching results for frequently accessed agents
- Limit `max_topics` parameter for better performance

## Testing

Run the test script to verify the agent works correctly:

```bash
python3 test_topic_extraction.py
```

This will test the basic functionality without requiring the full FastAPI application.

## Future Enhancements

Potential improvements:
1. **Caching**: Cache extraction results to improve performance
2. **Incremental Updates**: Update topics incrementally when new content is added
3. **Topic Relationships**: Identify relationships between topics
4. **Visual Topic Maps**: Generate visual representations of topic hierarchies
5. **Topic Search**: Allow searching within extracted topics

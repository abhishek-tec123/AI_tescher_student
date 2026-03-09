# Vector Search Architecture - Function Calls and Returns

This plan details the complete vector search process with specific function calls and their return values at each step.

## Complete Function Call Flow with Returns

### **Example Scenario**
- **User Query**: "What is photosynthesis and how does it work in plants?"
- **Entry Point**: `retrieve_chunk_for_query_send_to_llm_enhanced()`

---

## **STEP 1: Entry Point Function Call**

### **Function Called**: `retrieve_chunk_for_query_send_to_llm_enhanced()`
**Location**: EnhancedSimilaritySearch.py line 800
**Parameters**:
```python
retrieve_chunk_for_query_send_to_llm_enhanced(
    query="What is photosynthesis and how does it work in plants?",
    db_name="science_db",
    collection_name="lessons", 
    subject_agent_id="agent_123",
    embedding_model=sentence_transformer_model,
    student_profile={"student_id": "john_123", "response_length": "detailed"},
    top_k=15,
    disable_rl=False
)
```

**Return**: Dict with response, quality_scores, sources, etc.

---

## **STEP 2: Core Question Extraction**

### **Function Called**: `retrieve_chunks_with_shared_knowledge()`
**Location**: EnhancedSimilaritySearch.py line 475
**Parameters**: Same as above (passed through)
**Return**: Dict from async function or fallback

### **Function Called**: `retrieve_chunks_with_shared_knowledge_async()`
**Location**: EnhancedSimilaritySearch.py line 277
**Parameters**: Same as above
**Return**: Dict with search results

### **Function Called**: `extract_core_question()`
**Location**: SimilaritySearch.py line 144
**Parameters**:
```python
extract_core_question(
    query="What is photosynthesis and how does it work in plants?"
)
```

**Return Value**:
```python
" What is photosynthesis and how does it work in plants?"
```

---

## **STEP 3: Query Embedding**

### **Function Called**: `embed_query()`
**Location**: SimilaritySearch.py line 230
**Parameters**:
```python
embed_query(
    query=" What is photosynthesis and how does it work in plants?",
    embedding_model=sentence_transformer_model
)
```

**Return Value**:
```python
[0.12, -0.45, 0.78, 0.23, -0.11, 0.56, ..., 0.34]  # 384-dimensional vector
```

---

## **STEP 4: Parallel Search Setup**

### **Function Called**: `_search_agent_collection_async()`
**Location**: EnhancedSimilaritySearch.py line 166
**Parameters**:
```python
_search_agent_collection_async(
    db_name="science_db",
    collection_name="lessons",
    query_embedding=[0.12, -0.45, 0.78, ..., 0.34],
    top_k=15,
    query_text=" What is photosynthesis and how does it work in plants?"
)
```

**Return Value**:
```python
(
    [
        {
            "chunk_text": "Photosynthesis is the process by which plants convert sunlight into energy...",
            "score": 0.89,
            "unique_chunk_id": "chunk_123",
            "source_type": "agent",
            "source_name": "science_db.lessons"
        },
        {
            "chunk_text": "The photosynthesis process occurs in chloroplasts. Light-dependent reactions...",
            "score": 0.85,
            "unique_chunk_id": "chunk_124", 
            "source_type": "agent",
            "source_name": "science_db.lessons"
        }
    ],
    "science_db.lessons"
)
```

### **Function Called**: `_search_shared_documents_async()`
**Location**: EnhancedSimilaritySearch.py line 195
**Parameters**:
```python
_search_shared_documents_async(
    subject_agent_id="agent_123",
    query_embedding=[0.12, -0.45, 0.78, ..., 0.34],
    top_k=15,
    query_text=" What is photosynthesis and how does it work in plants?"
)
```

**Return Value**:
```python
(
    [
        {
            "chunk_text": "Photosynthesis evolved 3.5 billion years ago. Ancient cyanobacteria...",
            "score": 0.68,
            "unique_chunk_id": "shared_456",
            "source_type": "shared",
            "source_name": "shared:Biology_Reference"
        }
    ],
    [
        {
            "type": "shared",
            "name": "Biology_Reference",
            "document_id": "doc_789",
            "results_count": 1
        }
    ]
)
```

---

## **STEP 5: Parallel Execution**

### **Function Called**: `asyncio.gather()`
**Location**: EnhancedSimilaritySearch.py line 322
**Parameters**:
```python
await asyncio.gather(*search_tasks, return_exceptions=True)
```

**Return Value**:
```python
[
    (
        [agent_chunk_1, agent_chunk_2],  # Agent results
        "science_db.lessons"             # Source name
    ),
    (
        [shared_chunk_1],               # Shared results
        [shared_source_info]            # Source info
    )
]
```

---

## **STEP 6: Content Validation**

### **Function Called**: `validate_content_relevance()`
**Location**: EnhancedSimilaritySearch.py line 73
**Parameters** (for each chunk):
```python
validate_content_relevance(
    query=" What is photosynthesis and how does it work in plants?",
    chunk_text="Photosynthesis is the process by which plants convert sunlight into energy...",
    min_keyword_matches=2
)
```

**Return Values**:
```python
# Chunk 1: "photosynthesis" + "plants" = 2 matches
True

# Chunk 2: "photosynthesis" + "process" = 2 matches  
True

# Chunk 3: "photosynthesis" = 1 match
False
```

---

## **STEP 7: Vector Search Functions (Called Internally)**

### **Function Called**: `find_similar_chunks()`
**Location**: SimilaritySearch.py line 283
**Parameters**:
```python
find_similar_chunks(
    query_embedding=[0.12, -0.45, 0.78, ..., 0.34],
    collection=science_db_lessons_collection,
    query=" What is photosynthesis and how does it work in plants?",
    limit=15
)
```

**Return Value**:
```python
[
    {
        "chunk_text": "Photosynthesis is the process by which plants convert sunlight into energy...",
        "score": 0.89,
        "unique_id": "doc_123",
        "unique_chunk_id": "chunk_123",
        "subject_agent_id": "agent_123",
        "document_id": "doc_123"
    }
]
```

### **Function Called**: `find_similar_chunks_in_memory()`
**Location**: SimilaritySearch.py line 428
**Parameters**:
```python
find_similar_chunks_in_memory(
    query_embedding=[0.12, -0.45, 0.78, ..., 0.34],
    collection=shared_knowledge_collection,
    top_k=8,
    similarity_threshold=0.0,
    query_text=" What is photosynthesis and how does it work in plants?"
)
```

**Return Value**:
```python
[
    {
        "chunk_text": "Photosynthesis evolved 3.5 billion years ago...",
        "score": 0.68,
        "unique_id": "shared_doc_456",
        "unique_chunk_id": "shared_456",
        "subject_agent_id": "agent_123",
        "document_id": "doc_789"
    }
]
```

---

## **STEP 8: LLM Response Generation**

### **Function Called**: `get_llm_response_from_chunk()`
**Location**: SimilaritySearch.py line 502
**Parameters**:
```python
get_llm_response_from_chunk(
    result_string="Chunk 1 (agent): Photosynthesis is the process by which plants convert sunlight into energy...\n\nChunk 2 (agent): The photosynthesis process occurs in chloroplasts...",
    query="What is photosynthesis and how does it work in plants?",
    student_profile={"student_id": "john_123", "response_length": "detailed"},
    logger=logger_instance
)
```

**Return Value**:
```python
{
    "response": "Photosynthesis is the fundamental process by which plants convert sunlight into chemical energy. Here's how it works:\n\n**The Process:**\n1. **Light Capture**: Plants use chlorophyll to capture sunlight energy\n2. **Raw Materials**: They take in CO2 from air and H2O from soil\n3. **Energy Conversion**: Using light energy, plants convert CO2 and water into glucose and oxygen\n\n**The Chemical Equation:**\n6CO2 + 6H2O + light energy → C6H12O6 + 6O2\n\n**Where It Happens:**\n- Photosynthesis occurs in chloroplasts\n- Light-dependent reactions capture sunlight\n- Calvin cycle fixes carbon into sugar",
    "quality_scores": {
        "relevance_score": 0.92,
        "context_usage": 0.88,
        "completeness": 0.85,
        "overall_quality": 0.90
    }
}
```

---

## **STEP 9: Quality Scoring**

### **Function Called**: `compute_quality_scores()`
**Location**: structured_response.py (imported)
**Parameters**:
```python
compute_quality_scores(
    query="What is photosynthesis and how does it work in plants?",
    response_text="Photosynthesis is the fundamental process by which plants convert sunlight into chemical energy...",
    retrieved_chunks=[validated_chunk_1, validated_chunk_2],
    context_string="Chunk 1 (agent): Photosynthesis is the process...\n\nChunk 2 (agent): The photosynthesis process..."
)
```

**Return Value**:
```python
{
    "relevance_score": 0.92,      # How well response answers query
    "context_usage": 0.88,        # How well response uses provided context
    "completeness": 0.85,         # How complete the answer is
    "accuracy_score": 0.90,       # Based on context accuracy
    "student_appropriateness": 0.95,  # Matches student level
    "overall_quality": 0.90       # Combined quality score
}
```

---

## **STEP 10: Caching Functions**

### **Function Called**: `response_cache.get_cached_response()`
**Location**: SimilaritySearch.py line 58
**Parameters**:
```python
response_cache.get_cached_response(
    question="What is photosynthesis and how does it work in plants?",
    student_id="john_123"
)
```

**Return Value** (if cached):
```python
{
    'response': "Photosynthesis is the fundamental process...",
    'quality_scores': {...},
    'from_cache': True,
    'repeat_count': 2
}
```

**Return Value** (if not cached):
```python
None
```

### **Function Called**: `response_cache.cache_response()`
**Location**: SimilaritySearch.py line 93
**Parameters**:
```python
response_cache.cache_response(
    question="What is photosynthesis and how does it work in plants?",
    response="Photosynthesis is the fundamental process...",
    quality_scores={...},
    student_id="john_123"
)
```

**Return Value**: None (void function)

---

## **STEP 11: Final Return Structure**

### **Final Function Return**: `retrieve_chunk_for_query_send_to_llm_enhanced()`
**Return Value**:
```python
{
    "response": "Photosynthesis is the fundamental process by which plants convert sunlight into chemical energy. Here's how it works:\n\n**The Process:**\n1. **Light Capture**: Plants use chlorophyll to capture sunlight energy\n2. **Raw Materials**: They take in CO2 from air and H2O from soil\n3. **Energy Conversion**: Using light energy, plants convert CO2 and water into glucose and oxygen\n\n**The Chemical Equation:**\n6CO2 + 6H2O + light energy → C6H12O6 + 6O2",
    "quality_scores": {
        "relevance_score": 0.92,
        "context_usage": 0.88,
        "completeness": 0.85,
        "accuracy_score": 0.90,
        "student_appropriateness": 0.95,
        "overall_quality": 0.90
    },
    "sources": [
        {
            "type": "agent",
            "name": "science_db.lessons",
            "results_count": 2
        }
    ],
    "source_summary": ["agent: science_db.lessons (2 chunks)"],
    "chunks_used": 2,
    "from_cache": False,
    "content_restriction": "none"
}
```

---

## **Complete Function Call Sequence**

```
1. retrieve_chunk_for_query_send_to_llm_enhanced()
   ↓
2. retrieve_chunks_with_shared_knowledge()
   ↓
3. retrieve_chunks_with_shared_knowledge_async()
   ↓
4. extract_core_question() → "What is photosynthesis..."
   ↓
5. embed_query() → [0.12, -0.45, 0.78, ...]
   ↓
6. asyncio.gather() with:
   - _search_agent_collection_async()
   - _search_shared_documents_async()
   ↓
7. validate_content_relevance() (for each chunk)
   ↓
8. get_llm_response_from_chunk()
   ↓
9. compute_quality_scores()
   ↓
10. Final return with response, scores, sources
```

---

## **Error Handling Returns**

### **When No Chunks Found**:
```python
{
    "response": "I'm not able to answer this question from the available learning materials...",
    "quality_scores": {"content_restriction": "no_chunks_found"},
    "sources": [],
    "content_restriction": "no_chunks_found"
}
```

### **When Below Threshold**:
```python
{
    "response": "I'm not able to find relevant content in the learning materials...",
    "quality_scores": {"content_restriction": "below_threshold"},
    "sources": [],
    "content_restriction": "below_threshold"
}
```

This complete function call and return structure shows exactly how data flows through the vector search architecture from initial query to final response.

# EnhancedSimilaritySearch.py - Functions and Usage

This plan explains all functions in EnhancedSimilaritySearch.py and where they are used throughout the project.

## All Functions in EnhancedSimilaritySearch.py

### **1. Public API Functions**

#### **retrieve_chunk_for_query_send_to_llm_enhanced()**
**Location**: Line 754
**Purpose**: Main entry point for enhanced search with shared knowledge
**Parameters**: query, db_name, collection_name, subject_agent_id, embedding_model, student_profile, top_k, disable_rl
**Returns**: Dict with response, quality_scores, sources, chunks_used, from_cache

**Used By**:
- `Teacher_AI_Agent.agent.retriever_agent.RetrievalOrchestratorAgent` (Lines 118, 208)
- `studentAgent.student_agent.StudentAgent` (via retriever_agent)

#### **retrieve_chunks_with_shared_knowledge()**
**Location**: Line 475
**Purpose**: Synchronous wrapper for backward compatibility
**Parameters**: Same as above
**Returns**: Dict from async function or fallback

**Used By**:
- `retrieve_chunk_for_query_send_to_llm_enhanced()` (Line 827)

#### **retrieve_chunks_with_shared_knowledge_async()**
**Location**: Line 277
**Purpose**: Main async enhanced retrieval with parallel search
**Parameters**: Same as above
**Returns**: Dict with search results

**Used By**:
- `retrieve_chunks_with_shared_knowledge()` (Line 504)

#### **_fallback_sync_search()**
**Location**: Line 515
**Purpose**: Emergency fallback when async fails
**Parameters**: Same as above
**Returns**: Dict with search results

**Used By**:
- `retrieve_chunks_with_shared_knowledge()` (Line 513)

---

### **2. Internal Search Functions**

#### **_search_agent_collection_async()**
**Location**: Line 166
**Purpose**: Async search for agent-specific knowledge base
**Parameters**: db_name, collection_name, query_embedding, top_k, query_text
**Returns**: Tuple (validated_results, source_name)

**Used By**:
- `retrieve_chunks_with_shared_knowledge_async()` (Line 315)

#### **_search_shared_documents_async()**
**Location**: Line 195
**Purpose**: Async search for shared knowledge documents
**Parameters**: subject_agent_id, query_embedding, top_k, query_text
**Returns**: Tuple (all_shared_results, sources_info)

**Used By**:
- `retrieve_chunks_with_shared_knowledge_async()` (Line 319)

---

### **3. Utility Functions**

#### **validate_content_relevance()**
**Location**: Line 73
**Purpose**: Validates chunk content relevance to query
**Parameters**: query, chunk_text, min_keyword_matches
**Returns**: Boolean

**Used By**:
- `_search_agent_collection_async()` (Line 179)
- `_search_shared_documents_async()` (Line 249)
- `_fallback_sync_search()` (Lines 626, 683)

#### **_build_safe_out_of_scope_response()**
**Location**: Line 41
**Purpose**: Creates safe response when no relevant content found
**Parameters**: query, restriction_reason
**Returns**: Dict with safe response

**Used By**:
- `retrieve_chunks_with_shared_knowledge_async()` (Line 430)
- `_fallback_sync_search()` (Line 731)

---

### **4. Caching Functions**

#### **_get_cache_key()**
**Location**: Line 142
**Purpose**: Generate cache key for vector search results
**Parameters**: query, db_name, collection_name, top_k
**Returns**: String cache key

**Used By**:
- `retrieve_chunks_with_shared_knowledge_async()` (Line 308)
- `_fallback_sync_search()` (Line 607)

#### **_get_cached_vector_results()**
**Location**: Line 147
**Purpose**: Get cached vector search results if valid
**Parameters**: cache_key
**Returns**: Cached results or None

**Used By**:
- `retrieve_chunks_with_shared_knowledge_async()` (Line 309)

#### **_cache_vector_results()**
**Location**: Line 158
**Purpose**: Cache vector search results
**Parameters**: cache_key, results
**Returns**: None

**Used By**:
- `retrieve_chunks_with_shared_knowledge_async()` (Line 515)
- `_fallback_sync_search()` (Line 732)

---

### **5. Connection Management**

#### **get_async_client()**
**Location**: Line 122
**Purpose**: Get async MongoDB client with connection pooling
**Parameters**: None
**Returns**: MongoClient instance

**Used By**:
- `_search_agent_collection_async()` (Line 170)
- `_search_shared_documents_async()` (Line 217)
- `_fallback_sync_search()` (Line 616, 654)

---

## Usage Flow in Project

### **Primary Usage Path**
```
1. StudentAgent.student_agent.StudentAgent
   ↓
2. RetrievalOrchestratorAgent.orchestrate_retrieval_and_response_async()
   ↓
3. retrieve_chunk_for_query_send_to_llm_enhanced()
   ↓
4. retrieve_chunks_with_shared_knowledge()
   ↓
5. retrieve_chunks_with_shared_knowledge_async() [PARALLEL SEARCH]
   ├── _search_agent_collection_async()
   └── _search_shared_documents_async()
```

### **Import Locations**
```python
# In retriever_agent.py
from search.EnhancedSimilaritySearch import retrieve_chunk_for_query_send_to_llm_enhanced

# In __init__.py (for package exports)
from Teacher_AI_Agent.agent.retriever_agent import RetrievalOrchestratorAgent
```

### **Actual Usage Code**

#### **In retriever_agent.py (Line 118)**:
```python
result = retrieve_chunk_for_query_send_to_llm_enhanced(
    query=query,
    db_name=db_name,
    collection_name=collection_name,
    subject_agent_id=subject_agent_id,
    embedding_model=self.embedding_model,
    student_profile=profile.dict(),
    top_k=top_k,
    disable_rl=disable_rl
)
```

#### **In retriever_agent.py (Line 208)**:
```python
result = retrieve_chunk_for_query_send_to_llm_enhanced(
    query=query,
    db_name=db_name,
    collection_name=collection_name,
    subject_agent_id=subject_agent_id,
    embedding_model=self.embedding_model,
    student_profile=profile.dict(),
    top_k=top_k,
    disable_rl=disable_rl
)
```

---

## Function Categories and Responsibilities

### **Entry Points (1 function)**
- `retrieve_chunk_for_query_send_to_llm_enhanced()` - Main API

### **Core Search Logic (3 functions)**
- `retrieve_chunks_with_shared_knowledge()` - Sync wrapper
- `retrieve_chunks_with_shared_knowledge_async()` - Main async logic
- `_fallback_sync_search()` - Emergency fallback

### **Search Workers (2 functions)**
- `_search_agent_collection_async()` - Agent knowledge search
- `_search_shared_documents_async()` - Shared knowledge search

### **Validation & Safety (2 functions)**
- `validate_content_relevance()` - Content validation
- `_build_safe_out_of_scope_response()` - Safe responses

### **Performance (4 functions)**
- `get_async_client()` - Connection pooling
- `_get_cache_key()` - Cache key generation
- `_get_cached_vector_results()` - Cache retrieval
- `_cache_vector_results()` - Cache storage

---

## Key Features Enabled by These Functions

### **1. Shared Knowledge Support**
- `_search_shared_documents_async()` enables global document access
- `subject_agent_id` parameter controls shared knowledge access

### **2. Parallel Processing**
- `retrieve_chunks_with_shared_knowledge_async()` runs agent + shared searches simultaneously
- Improves performance by ~50%

### **3. Content Safety**
- `validate_content_relevance()` prevents false positives
- `_build_safe_out_of_scope_response()` ensures RAG-only responses

### **4. Performance Optimization**
- Multiple caching layers (vector cache + response cache)
- Connection pooling for MongoDB
- Async operations with fallbacks

### **5. Backward Compatibility**
- Sync wrapper functions for existing code
- Automatic fallback to sync if async fails

---

## Integration Points

### **With SimilaritySearch.py**
```python
from search.SimilaritySearch import (
    extract_core_question,        # Query processing
    embed_query,                   # Vector generation
    find_similar_chunks,           # Agent search
    find_similar_chunks_in_memory, # Shared search
    get_llm_response_from_chunk,  # LLM generation
    response_cache                 # Response caching
)
```

### **With External Systems**
- **MongoDB**: Connection pooling and vector search
- **Shared Knowledge Manager**: Document access control
- **Groq LLM**: Response generation
- **Model Cache**: Embedding model management

This architecture provides a robust, scalable search system with shared knowledge support, safety features, and performance optimizations.

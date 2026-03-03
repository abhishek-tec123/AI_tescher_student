# How Search Works - Step-by-Step Code Flow

This plan explains the actual search process by tracing through the code execution flow in your project.

## Entry Point: retrieve_chunk_for_query_send_to_llm_enhanced()

The search starts at line 800 in EnhancedSimilaritySearch.py:

```python
def retrieve_chunk_for_query_send_to_llm_enhanced(
    query: str,
    db_name: str = None,
    collection_name: str = None,
    subject_agent_id: str = None,
    embedding_model=None,
    student_profile: dict = None,
    top_k: int = TOP_K,
    disable_rl: bool = False
) -> dict:
```

## Decision Logic (Lines 814-824)

**First Decision Point:**
- **IF** `subject_agent_id` is None → Use basic search from SimilaritySearch.py
- **ELSE** → Use enhanced search with shared knowledge

```python
if not subject_agent_id:
    return retrieve_chunk_for_query_send_to_llm(...)  # Basic search
else:
    return retrieve_chunks_with_shared_knowledge(...)  # Enhanced search
```

## Enhanced Search Flow: retrieve_chunks_with_shared_knowledge_async()

When `subject_agent_id` exists, the enhanced search follows these steps:

### Step 1: Input Validation (Lines 295-303)
```python
if not embedding_model:
    return _err("No embedding model provided.")
if not query or not query.strip():
    return _err("Query cannot be empty.")
```

### Step 2: Cache Check (Lines 307-331)
```python
# Check vector cache first
cache_key = _get_cache_key(query, db_name or "", collection_name or "", top_k)
cached_results = _get_cached_vector_results(cache_key)
if cached_results:
    return cached_results

# Check response cache
cached_response = response_cache.get_cached_response(query, student_id)
if cached_response:
    return cached_response
```

### Step 3: Core Question Extraction (Lines 333-350)
```python
core_question = extract_core_question(query)  # From SimilaritySearch.py
query_embedding = embed_query(core_question, embedding_model)
```

### Step 4: Parallel Search Setup (Lines 355-363)
```python
search_tasks = []

if db_name and collection_name:
    search_tasks.append(_search_agent_collection_async(...))
    
if subject_agent_id:
    search_tasks.append(_search_shared_documents_async(...))
```

### Step 5: Parallel Execution (Lines 365-366)
```python
search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
```

## Parallel Search Tasks

### Task 1: Agent Collection Search (_search_agent_collection_async)
```python
async def _search_agent_collection_async(db_name, collection_name, query_embedding, top_k, query_text):
    # Connect to MongoDB
    client = get_async_client()
    agent_collection = client[db_name][collection_name]
    
    # Find similar chunks using vector similarity
    agent_results = find_similar_chunks(query_embedding, agent_collection, limit=top_k, query=query_text)
    
    # Apply content validation
    validated_results = []
    for result in agent_results:
        chunk_text = result.get('text', result.get('chunk_text', ''))
        if validate_content_relevance(query_text, chunk_text):
            result["source_type"] = "agent"
            validated_results.append(result)
    
    return validated_results, f"{db_name}.{collection_name}"
```

### Task 2: Shared Documents Search (_search_shared_documents_async)
```python
async def _search_shared_documents_async(subject_agent_id, query_embedding, top_k, query_text):
    # Check if global RAG is enabled for this agent
    agent_data = get_agent_data(subject_agent_id)
    agent_global_rag_enabled = agent_metadata.get("global_rag_enabled", False)
    
    if not agent_global_rag_enabled:
        return [], []
    
    # Get enabled shared documents
    enabled_shared_docs = shared_knowledge_manager.get_agent_enabled_documents(subject_agent_id)
    
    # Search each shared document
    for shared_doc in enabled_shared_docs:
        shared_results = find_similar_chunks_in_memory(...)
        # Filter and validate results
        if validate_content_relevance(query_text, chunk_text):
            result["source_type"] = "shared"
            filtered_results.append(result)
    
    return all_shared_results, sources_info
```

## Step 6: Results Processing (Lines 368-440)

### Combine and Filter Results
```python
# Process results from parallel searches
all_results = []
agent_results = []
shared_results = []

for result in search_results:
    # Handle agent collection results
    if len(result) == 2 and isinstance(result[0], list):
        agent_results.extend(result[0])
    
    # Handle shared documents results  
    elif len(result) == 2 and isinstance(result[1], list):
        shared_results.extend(result[0])
        sources_info.extend(result[1])

# Apply threshold filtering
AGENT_HIGH_THRESHOLD = 0.3
SHARED_HIGH_THRESHOLD = 0.2

filtered_agent_results = [doc for doc in agent_results if doc.get("score", 0) >= AGENT_HIGH_THRESHOLD]
filtered_shared_results = [doc for doc in shared_results if doc.get("score", 0) >= SHARED_HIGH_THRESHOLD]
```

### ABSOLUTE RULE: No Relevant Content = No LLM Call
```python
if not filtered_agent_results and not filtered_shared_results:
    logger.error("🚫 NO RELEVANT CONTENT FOUND: LLM call BLOCKED.")
    result = _build_safe_out_of_scope_response(query, "no_relevant_content")
    return result
```

### Agent-First Combination
```python
# Agent chunks are primary, shared chunks supplement
final_results = filtered_agent_results + filtered_shared_results
final_results.sort(key=lambda x: x.get('score', 0), reverse=True)
all_results = final_results[:top_k]
```

## Step 7: LLM Response Generation (Lines 457-517)

### Build Context String
```python
context_chunks = []
for i, chunk in enumerate(all_results):
    chunk_content = chunk.get('text', chunk.get('chunk_text', ''))[:2000]
    source_info = f" ({chunk.get('source_type', 'unknown')})"
    context_chunks.append(f"Chunk {i+1}{source_info}: {chunk_content}")

result_string = "\n\n".join(context_chunks)
```

### Call LLM
```python
response_result = get_llm_response_from_chunk(
    result_string=result_string,
    query=query,
    student_profile=student_profile,
    logger=logger
)
```

## Step 8: Quality Scoring and Caching (Lines 501-517)
```python
# Compute quality scores
quality_scores = compute_quality_scores(query, response_text, all_results, result_string)

# Build final result
result = {
    "response": response_text,
    "quality_scores": quality_scores,
    "sources": sources_info,
    "chunks_used": len(all_results),
    "from_cache": False
}

# Cache the result
_cache_vector_results(cache_key, result)
```

## Key Search Functions Called

### From SimilaritySearch.py:
- `extract_core_question()` - Extracts actual question from formatted queries
- `embed_query()` - Converts question to vector embedding
- `find_similar_chunks()` - MongoDB Atlas vector search
- `find_similar_chunks_in_memory()` - In-memory cosine similarity
- `validate_content_relevance()` - Keyword matching validation
- `get_llm_response_from_chunk()` - Calls Groq LLM
- `compute_quality_scores()` - Evaluates response quality

### Content Validation Logic:
```python
def validate_content_relevance(query: str, chunk_text: str, min_keyword_matches: int = 2):
    # Extract key terms from query
    query_words = [word for word in query.lower().split() 
                   if len(word) > 2 and word not in STOP_WORDS]
    
    # Count keyword matches in chunk
    keyword_matches = sum(1 for word in query_words if word in chunk_text.lower())
    
    # Require minimum matches (relaxed for short queries)
    if len(query_words) <= 3:
        effective_min_matches = 1
    else:
        effective_min_matches = min_keyword_matches
    
    return keyword_matches >= effective_min_matches
```

## Summary Flow

```
Query → Cache Check → Core Extraction → Embedding → 
Parallel Search (Agent + Shared) → Content Validation → 
Threshold Filter → Context Building → LLM Call → 
Quality Scoring → Response Caching
```

This ensures students get accurate, curriculum-aligned answers with multiple safety checks and performance optimizations.

# Vector Search Architecture - Query to Response Flow with Example

This plan explains the complete vector search architecture from user query to LLM response, with a detailed example showing each step.

## Complete Architecture Flow

```
User Query → Core Extraction → Embedding → Vector Search → 
Content Validation → Threshold Filtering → Context Building → 
LLM Generation → Quality Scoring → Response
```

## Step-by-Step Architecture with Example

### **Example Scenario**
- **User Query**: "What is photosynthesis and how does it work in plants?"
- **Subject**: Science (10th grade)
- **Database**: science_db.lessons collection
- **Shared Knowledge**: Biology reference documents enabled

---

## **STEP 1: Query Processing**

### **Input Query**
```python
query = """
Current Question:
What is photosynthesis and how does it work in plants?

Class: 10th Science
Student: John (prefers detailed explanations)
"""
```

### **Core Question Extraction** (`extract_core_question()`)
```python
# Function extracts the actual question from formatted prompt
core_question = "What is photosynthesis and how does it work in plants?"
```

**Why?** Removes metadata, focuses search on the core question for better similarity.

---

## **STEP 2: Query Embedding**

### **Vector Generation** (`embed_query()`)
```python
# Using sentence transformer model
query_embedding = embed_query(core_question, embedding_model)
# Result: [0.12, -0.45, 0.78, ..., 0.23]  # 384-dimensional vector
```

**Why?** Converts text to numerical vector for semantic similarity comparison.

---

## **STEP 3: Parallel Vector Search**

### **Agent Collection Search** (Your curriculum content)
```python
# Searches science_db.lessons collection
agent_results = find_similar_chunks(
    query_embedding=[0.12, -0.45, 0.78, ...],
    collection=science_db.lessons,
    limit=15,
    query="What is photosynthesis and how does it work in plants?"
)
```

**Results Found:**
```python
[
    {
        "chunk_text": "Photosynthesis is the process by which plants convert sunlight into energy. During photosynthesis, plants use chlorophyll to capture light energy and convert CO2 and water into glucose and oxygen.",
        "score": 0.89,
        "unique_chunk_id": "chunk_123",
        "source_type": "agent"
    },
    {
        "chunk_text": "The photosynthesis process occurs in chloroplasts. Light-dependent reactions capture sunlight, while Calvin cycle fixes carbon. The overall equation: 6CO2 + 6H2O + light → C6H12O6 + 6O2",
        "score": 0.85,
        "unique_chunk_id": "chunk_124", 
        "source_type": "agent"
    },
    {
        "chunk_text": "Factors affecting photosynthesis include light intensity, CO2 concentration, temperature, and water availability. Plants optimize these factors for maximum energy production.",
        "score": 0.72,
        "unique_chunk_id": "chunk_125",
        "source_type": "agent"
    }
]
```

### **Shared Documents Search** (Global knowledge)
```python
# Searches shared_knowledge collection
shared_results = find_similar_chunks_in_memory(
    query_embedding=[0.12, -0.45, 0.78, ...],
    collection=shared_knowledge,
    top_k=8,
    similarity_threshold=0.2,
    query_text="What is photosynthesis and how does it work in plants?"
)
```

**Results Found:**
```python
[
    {
        "chunk_text": "Photosynthesis evolved 3.5 billion years ago. Ancient cyanobacteria developed this process, transforming Earth's atmosphere by producing oxygen.",
        "score": 0.68,
        "source_type": "shared",
        "source_name": "shared:Biology_Reference"
    },
    {
        "chunk_text": "Different plants have varying photosynthetic efficiency. C4 plants like sugarcane are more efficient in hot climates than C3 plants.",
        "score": 0.45,
        "source_type": "shared", 
        "source_name": "shared:Biology_Reference"
    }
]
```

---

## **STEP 4: Content Validation**

### **Keyword Matching Validation**
```python
def validate_content_relevance(query, chunk_text):
    # Extract keywords from query
    query_words = ["photosynthesis", "work", "plants"]
    
    # Count matches in chunk
    chunk_lower = chunk_text.lower()
    keyword_matches = sum(1 for word in query_words if word in chunk_lower)
    
    # Require minimum matches (2 for this query)
    return keyword_matches >= 2
```

### **Validation Results**
```python
# Agent chunks - all pass validation
chunk_123: "photosynthesis" + "plants" = 2 matches ✓
chunk_124: "photosynthesis" + "process" = 2 matches ✓  
chunk_125: "photosynthesis" = 1 match ✗ (rejected)

# Shared chunks
shared_1: "photosynthesis" = 1 match ✗ (rejected)
shared_2: "photosynthesis" = 1 match ✗ (rejected)

# Final validated results
validated_results = [chunk_123, chunk_124]  # Only agent chunks pass
```

---

## **STEP 5: Threshold Filtering**

### **Similarity Score Filtering**
```python
AGENT_HIGH_THRESHOLD = 0.3
SHARED_HIGH_THRESHOLD = 0.2

# Apply thresholds
filtered_agent = [chunk for chunk in agent_results if chunk.score >= 0.3]
filtered_shared = [chunk for chunk in shared_results if chunk.score >= 0.2]

# Results after filtering
filtered_agent = [chunk_123 (0.89), chunk_124 (0.85)]  # Both pass ✓
filtered_shared = []  # None pass validation, so none considered
```

### **Safety Check**
```python
if not filtered_agent and not filtered_shared:
    # ABSOLUTE RULE: No relevant content = No LLM call
    return safe_response("I cannot answer this from available materials")
```

---

## **STEP 6: Context Building**

### **Agent-First Combination**
```python
# Agent chunks get priority
final_results = filtered_agent + filtered_shared  # [chunk_123, chunk_124]
final_results.sort(key=lambda x: x.score, reverse=True)  # Already sorted
top_chunks = final_results[:15]  # Limit to top 15
```

### **Context String Construction**
```python
context_chunks = []
for i, chunk in enumerate(top_chunks):
    chunk_content = chunk.get('chunk_text', '')[:2000]  # Limit length
    source_info = f" (agent)"
    context_chunks.append(f"Chunk {i+1}{source_info}: {chunk_content}")

result_string = "\n\n".join(context_chunks)
```

**Final Context Sent to LLM:**
```
Chunk 1 (agent): Photosynthesis is the process by which plants convert sunlight into energy. During photosynthesis, plants use chlorophyll to capture light energy and convert CO2 and water into glucose and oxygen.

Chunk 2 (agent): The photosynthesis process occurs in chloroplasts. Light-dependent reactions capture sunlight, while Calvin cycle fixes carbon. The overall equation: 6CO2 + 6H2O + light → C6H12O6 + 6O2
```

---

## **STEP 7: LLM Generation**

### **LLM Call** (`get_llm_response_from_chunk()`)
```python
response = get_llm_response_from_chunk(
    result_string=context_string,  # The chunks above
    query="What is photosynthesis and how does it work in plants?",
    student_profile={
        "student_id": "john_123",
        "preferences": {
            "response_length": "detailed",
            "include_examples": True
        }
    }
)
```

### **LLM Prompt Structure**
```
You are a 10th grade science tutor. Answer using only the provided context.

Context:
[Chunk 1 and 2 from above]

Student Question: What is photosynthesis and how does it work in plants?

Student prefers detailed explanations with examples.
```

### **LLM Response**
```python
response_text = """
Photosynthesis is the fundamental process by which plants convert sunlight into chemical energy. Here's how it works:

**The Process:**
1. **Light Capture**: Plants use chlorophyll (green pigment) in their leaves to capture sunlight energy
2. **Raw Materials**: They take in carbon dioxide (CO2) from the air and water (H2O) from the soil
3. **Energy Conversion**: Using the captured light energy, plants convert CO2 and water into glucose (sugar) and oxygen

**The Chemical Equation:**
6CO2 + 6H2O + light energy → C6H12O6 + 6O2

**Where It Happens:**
- Photosynthesis occurs in specialized cell structures called chloroplasts
- The process has two main stages:
  - Light-dependent reactions (capture sunlight)
  - Calvin cycle (fixes carbon into sugar)

**Why It's Important:**
- Provides energy for the plant's growth and survival
- Produces oxygen as a byproduct, which is essential for most life on Earth
- Forms the base of most food chains

This elegant process allows plants to create their own food using just sunlight, water, and air!
"""
```

---

## **STEP 8: Quality Scoring**

### **Quality Analysis** (`compute_quality_scores()`)
```python
quality_scores = compute_quality_scores(
    query="What is photosynthesis and how does it work in plants?",
    response_text=response_text,
    retrieved_chunks=top_chunks,
    context_string=result_string
)
```

**Quality Metrics:**
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

## **STEP 9: Final Response**

### **Complete Response Object**
```python
final_result = {
    "response": response_text,  # The detailed explanation above
    "quality_scores": quality_scores,
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

## **Performance Timeline**

```
0ms: Query received
5ms: Core question extracted  
10ms: Query embedding generated
15ms: Parallel search started
200ms: Agent search completed (parallel)
180ms: Shared search completed (parallel)
205ms: Content validation completed
210ms: Threshold filtering completed  
215ms: Context building completed
800ms: LLM response generated
810ms: Quality scoring completed
815ms: Response returned
```

**Total Time: ~815ms** (LLM generation is the bottleneck)

---

## **Key Architecture Benefits**

### **1. Parallel Processing**
- Agent and shared searches run simultaneously
- Saves ~50% search time

### **2. Multi-Layer Safety**
- Content validation prevents false positives
- Threshold filtering ensures relevance
- RAG-only policy guarantees curriculum alignment

### **3. Adaptive Responses**
- Student preferences considered
- Quality scoring ensures high standards
- Caching improves repeat query performance

### **4. Scalable Design**
- Connection pooling handles high load
- Async operations scale well
- Fallback mechanisms ensure reliability

This architecture ensures students receive accurate, curriculum-aligned responses efficiently while maintaining high safety and quality standards.

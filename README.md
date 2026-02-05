Exploring the `studentProfileDetails` directory to locate where those scores are produced and how to retrieve them.


[11 tools called]


Implementing a Quality Score Analysis to compute and return all scores. The codebase currently returns only the response text. Adding a scoring pipeline that computes RAG Relevance from chunk scores and uses the LLM to evaluate Model Certainty, Answer Completeness, and Hallucination Risk.


[3 tools called]


Implementing quality scoring and propagating it through the pipeline.


[40 tools called]


Quality Score Analysis is now wired through the pipeline. You’ll get all scores in the API response.

## Changes made

1. **`compute_quality_scores`** in `Teacher_AI_Agent/search/structured_response.py`:
   - **RAG relevance**: From chunk similarity scores (0–100%)
   - **Model certainty / critical confidence**: From LLM evaluation
   - **Answer completeness**: From LLM evaluation  
   - **Hallucination risk**: From LLM evaluation (0–100, lower = safer)

2. **`SimilaritySearch.py`**: `retrieve_chunk_for_query_send_to_llm` now returns  
   `{"response": str, "quality_scores": dict}` instead of a plain string.

3. **`intentBasedAgent.py`**: The API response includes `quality_scores`.

## Example API response

```json
{
  "response": "The answer text...",
  "profile": { ... },
  "quality_scores": {
    "critical_confidence": 45,
    "model_certainty": 45,
    "rag_relevance": 65,
    "answer_completeness": 70,
    "hallucination_risk": 15
  }
}
```

## Score meanings

| Score | Description |
|-------|-------------|
| **critical_confidence** / **model_certainty** | Model’s confidence in the answer (0–100) |
| **rag_relevance** | Relevance of retrieved chunks to the query (0–100) |
| **answer_completeness** | How fully the answer covers the query (0–100) |
| **hallucination_risk** | Risk of unsupported or fabricated content (0–100, lower = safer) |

RAG relevance comes from chunk similarity scores. The other three are produced by a separate LLM evaluation call after generating the answer. Ensure `GROQ_API_KEY` is set for the LLM-based scores to be computed.


GET /vectors/status

GET /vectors/env_info

GET /vectors/classes

GET /vectors/subjects

GET /vectors/all_collections

GET /vectors/db_status/{class_}/{subject}

POST /vectors/search

POST /vectors/create_vectors
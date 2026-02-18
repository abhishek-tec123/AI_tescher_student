# -----------------------------
# Student-adaptive similarity search + Groq LLM
# -----------------------------

import logging
import os
import numpy as np
from pymongo import MongoClient
from search.structured_response import generate_response_from_groq, compute_quality_scores

# -----------------------------
# Logging
# -----------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# -----------------------------
# MongoDB & Vector Search Config
# -----------------------------
MONGODB_URI = os.environ.get("MONGODB_URI")
VECTOR_INDEX_NAME = "vector_index"
# In the current schema, the embedding vector is stored under `embedding.vector`
VECTOR_PATH = "embedding.vector"

TOP_K = 10
MIN_SCORE_THRESHOLD = 0.35  # Minimum cosine similarity for chunks to be considered relevant (lowered from 0.40 to handle edge cases)

# -----------------------------
# Query extraction helper
# -----------------------------
def extract_core_question(query: str) -> str:
    """
    Extracts the core question from a formatted query string.
    Looks for patterns like "Current Question:" or just uses the query if no pattern found.
    """
    import re
    
    # ---------------------------------------------------------
    # RL/Conversational Extraction (High Priority)
    # If the query is likely a conversational response from an LLM (e.g. RL rewrite)
    # try to extract just the core suggestion inside quotes.
    # ---------------------------------------------------------
    lower_query = query.lower()
    if any(keyword in lower_query for keyword in ["rewrit", "option", "alternative", "suggested"]):
        quoted = re.findall(r'"([^"]*)"', query)
        if quoted:
            # Prefer the longest quoted string if multiple exist (to avoid single words)
            best_chunk = max(quoted, key=len)
            if len(best_chunk) > 10: # Only if it's a meaningful phrase
                return best_chunk[:500]

    # Pattern 1: "Current Question:\n<question>"
    match = re.search(r"Current Question:\s*\n\s*(.+?)(?:\n\n|\nClass:|\nStudent preferences:|$)", query, re.DOTALL | re.IGNORECASE)
    if match:
        core = match.group(1).strip()
        if core:
            return core
    
    # Pattern 2: "Previous conversation:...\n\nCurrent Question:\n<question>"
    match = re.search(r"Current Question:\s*\n\s*(.+?)(?:\n\n|\nClass:|$)", query, re.DOTALL | re.IGNORECASE)
    if match:
        core = match.group(1).strip()
        if core:
            return core
    
    # Pattern 3: If query starts with "Q:" or "Question:"
    match = re.search(r"^(?:Q:|Question:)\s*(.+?)(?:\n|$)", query, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Fallback: use first line or first 200 chars if query is very long
    lines = query.strip().split('\n')
    if len(lines) > 0:
        first_line = lines[0].strip()
        # If first line is very short and looks like a question, use it
        if len(first_line) < 200 and '?' in first_line:
            return first_line
        # Otherwise, if query is very long (>500 chars), use first meaningful line
        if len(query) > 500:
            for line in lines[:5]:  # Check first 5 lines
                line = line.strip()
                if line and len(line) < 200 and not line.startswith(('Class:', 'Subject:', 'Student', 'Rules:', 'Previous')):
                    return line
    
    return query[:500] if len(query) > 500 else query

# -----------------------------
# Embedding helper
# -----------------------------
def embed_query(query: str, embedding_model) -> list:
    """Generate embedding vector for a query using the provided model."""
    return embedding_model.embed_query(query)

# -----------------------------
# Vector search helpers
# -----------------------------
def find_similar_chunks(query_embedding, collection, num_candidates=100, limit=TOP_K, index_name=VECTOR_INDEX_NAME):
    """MongoDB Atlas vector search."""
    try:
        pipeline = [
            {
                "$vectorSearch": {
                    "index": index_name,
                    # Match the stored schema: embedding vector is nested
                    "path": VECTOR_PATH,
                    "queryVector": query_embedding,
                    "numCandidates": num_candidates,
                    "limit": limit
                }
            },
            {
                "$project": {
                    # Normalize fields into a flat structure expected downstream
                    "chunk_text": "$chunk.text",
                    "score": {"$meta": "vectorSearchScore"},
                    "unique_id": "$document.doc_unique_id",
                    "unique_chunk_id": "$chunk.unique_chunk_id"
                }
            }
        ]
        return list(collection.aggregate(pipeline))
    except Exception as e:
        logger.warning(f"[VectorSearch] Atlas search failed: {e}")
        return []

def find_similar_chunks_in_memory(query_embedding, collection, top_k=TOP_K):
    """Fallback in-memory cosine similarity search."""
    # Match the current nested schema used when storing documents
    docs = list(
        collection.find(
            {},
            {
                "embedding.vector": 1,
                "chunk.text": 1,
                "chunk.unique_chunk_id": 1,
                "document.doc_unique_id": 1,
            },
        )
    )

    def cosine_similarity(a, b):
        a = np.array(a)
        b = np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    scored = []
    for doc in docs:
        # Safely extract nested fields according to the current schema
        embedding_container = doc.get("embedding") or {}
        embedding_vector = embedding_container.get("vector")
        if embedding_vector is None:
            # Skip documents without an embedding vector
            continue

        chunk_container = doc.get("chunk") or {}
        document_container = doc.get("document") or {}

        unique_id = document_container.get("doc_unique_id")
        unique_chunk_id = chunk_container.get("unique_chunk_id", "N/A")
        chunk_text = chunk_container.get("text", "")

        scored.append(
            {
                # Normalize into the flat structure expected downstream
                "unique_id": unique_id,
                "unique_chunk_id": unique_chunk_id,
                "chunk_text": chunk_text,
                "score": cosine_similarity(query_embedding, embedding_vector),
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]

# -----------------------------
# LLM response helper
# -----------------------------
def get_llm_response_from_chunk(
    result_string: str,
    query: str,
    student_profile: dict,
    logger
) -> str:
    """
    Calls the Groq LLM with a combined result string.
    Returns the response text.
    """
    try:
        response_text = generate_response_from_groq(
            input_text=result_string,
            query=query,
            student_profile=student_profile
        )

        if not response_text.strip():
            logger.warning("LLM returned empty response.")
            return (
                "I don’t have knowledge about this topic. "
                "You may refer to another agent source."
            )

        return response_text

    except Exception as e:
        logger.error(f"Groq LLM invocation failed: {e}")
        return "I don’t have knowledge about this topic. You may refer to another agent."

# -----------------------------
# Main retrieval + LLM
# -----------------------------
def retrieve_chunk_for_query_send_to_llm(
    query: str,
    db_name: str = None,
    collection_name: str = None,
    embedding_model=None,
    student_profile: dict = None,
    top_k: int = TOP_K
    ) -> dict:
    """
    Retrieves relevant chunks for a query and generates an LLM response.
    Returns: {"response": str, "quality_scores": dict}
    """
    db_name = db_name or ""
    collection_name = collection_name or ""

    # -----------------------------
    # Basic validation
    # -----------------------------
    _err = lambda msg: {"response": msg, "quality_scores": {}}

    if not embedding_model:
        logger.error("No embedding model provided.")
        return _err("No embedding model provided.")

    if not query or not query.strip():
        logger.error("Query cannot be empty.")
        return _err("Query cannot be empty.")

    # -----------------------------
    # Connect to MongoDB
    # -----------------------------
    try:
        client = MongoClient(MONGODB_URI)

        if db_name not in client.list_database_names():
            return _err(f"Database '{db_name}' does not exist.")

        if collection_name not in client[db_name].list_collection_names():
            return _err(f"Collection '{collection_name}' does not exist in database '{db_name}'.")

        collection = client[db_name][collection_name]
        doc_count = collection.count_documents({})

        if doc_count == 0:
            return _err(f"Collection '{collection_name}' is empty.")

        logger.info(f"[MongoDB] Connected to {db_name}.{collection_name} ({doc_count} documents)")

    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        return _err("Failed to connect to MongoDB.")

    # -----------------------------
    # Extract core question for embedding (better similarity scores)
    # Use full query for LLM response generation
    # -----------------------------
    core_question = extract_core_question(query)
    logger.info(f"Core question extracted for embedding: '{core_question[:100]}...' (full query length: {len(query)})")
    
    # Generate query embedding using core question only
    query_embedding = embed_query(core_question, embedding_model)

    # -----------------------------
    # Retrieve chunks
    # -----------------------------
    results = find_similar_chunks(query_embedding, collection, limit=top_k)

    if not results:
        logger.info("[VectorSearch] No results from Atlas, using in-memory fallback.")
        results = find_similar_chunks_in_memory(query_embedding, collection, top_k=top_k)

    if not results:
        # No chunks retrieved at all (empty collection or vector search failure).
        # Do NOT fall back to LLM without RAG context – return a safe message.
        logger.warning("No chunks retrieved from similarity search. Not calling LLM without context.")
        safe_msg = (
            "I’m not able to answer this question from the available learning materials. "
            "Please try rephrasing your question or ask your teacher for help."
        )
        quality_scores = compute_quality_scores(
            query=query,
            response_text=safe_msg,
            retrieved_chunks=[],
            context_string="",
        )
        return {"response": safe_msg, "quality_scores": quality_scores}

    # -----------------------------
    # LOG ALL retrieved chunks
    # -----------------------------
    logger.info("Retrieved chunks (before threshold filtering):")
    for idx, doc in enumerate(results):
        logger.info(
            f"[RAW {idx + 1}] Score: {doc.get('score', 0):.4f}, "
            f"Unique ID: {doc.get('unique_id')}, "
            f"Chunk ID: {doc.get('unique_chunk_id')}"
        )

    # -----------------------------
    # Filter by similarity threshold
    # -----------------------------
    filtered_results = [
        doc for doc in results
        if doc.get("score", 0) >= MIN_SCORE_THRESHOLD
    ]

    if not filtered_results:
        # If nothing passes the similarity threshold, do NOT call the LLM.
        # This avoids answers that rely purely on model prior knowledge.
        logger.warning(
            f"No chunks passed MIN_SCORE_THRESHOLD={MIN_SCORE_THRESHOLD}. "
            "Not calling LLM without RAG context."
        )
        safe_msg = (
            "I’m not able to find relevant content in the learning materials for this question. "
            "Please try asking it in a different way or consult your teacher."
        )
        quality_scores = compute_quality_scores(
            query=query,
            response_text=safe_msg,
            retrieved_chunks=[],
            context_string="",
        )
        return {"response": safe_msg, "quality_scores": quality_scores}

    # -----------------------------
    # LOG accepted chunks with content
    # -----------------------------
    logger.info("=" * 80)
    logger.info("✅ Chunks passed threshold and will be sent to LLM:")
    logger.info("=" * 80)
    for idx, doc in enumerate(filtered_results):
        chunk_text = doc.get("chunk_text", "")
        logger.info(
            f"[ACCEPTED {idx + 1}] Score: {doc['score']:.4f}, "
            f"Unique ID: {doc.get('unique_id')}, "
            f"Chunk ID: {doc.get('unique_chunk_id')}"
        )
        # logger.info(f"Chunk {idx + 1} Content ({len(chunk_text)} chars):")
        # logger.info(chunk_text[:300] + ("..." if len(chunk_text) > 300 else ""))
        # logger.info("-" * 80)

    # -----------------------------
    # Build combined result string
    # -----------------------------
    result_string = "\n---\n".join(doc["chunk_text"] for doc in filtered_results)
    logger.info(f"Combined context string length: {len(result_string)} chars")

    # -----------------------------
    # Call LLM function
    # -----------------------------
    # logger.info(f"Calling LLM with query: {query}")
    logger.info(f"Context chunks: {len(filtered_results)} chunks, {len(result_string)} total chars")
    
    response_text = get_llm_response_from_chunk(
        result_string=result_string,
        query=query,
        student_profile=student_profile or {},
        logger=logger
    )

    # -----------------------------
    # Compute Quality Score Analysis
    # -----------------------------
    quality_scores = compute_quality_scores(
        query=query,
        response_text=response_text,
        retrieved_chunks=filtered_results,
        context_string=result_string,
    )

    return {"response": response_text, "quality_scores": quality_scores}

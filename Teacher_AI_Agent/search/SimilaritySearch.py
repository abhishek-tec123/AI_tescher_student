# similarity_search.py
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

TOP_K = 3
MIN_SCORE_THRESHOLD = 0.40  # Minimum cosine similarity for chunks to be considered relevant

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
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": num_candidates,
                    "limit": limit
                }
            },
            {
                "$project": {
                    "chunk_text": 1,
                    "score": {"$meta": "vectorSearchScore"},
                    "unique_id": 1,
                    "unique_chunk_id": 1
                }
            }
        ]
        return list(collection.aggregate(pipeline))
    except Exception as e:
        logger.warning(f"[VectorSearch] Atlas search failed: {e}")
        return []

def find_similar_chunks_in_memory(query_embedding, collection, top_k=TOP_K):
    """Fallback in-memory cosine similarity search."""
    docs = list(collection.find({}, {"embedding": 1, "chunk_text": 1, "unique_id": 1, "unique_chunk_id": 1}))

    def cosine_similarity(a, b):
        a = np.array(a)
        b = np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    scored = [
        {
            "unique_id": doc["unique_id"],
            "unique_chunk_id": doc.get("unique_chunk_id", "N/A"),
            "chunk_text": doc["chunk_text"],
            "score": cosine_similarity(query_embedding, doc["embedding"])
        }
        for doc in docs if "embedding" in doc
    ]

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
    # Generate query embedding
    # -----------------------------
    query_embedding = embed_query(query, embedding_model)

    # -----------------------------
    # Retrieve chunks
    # -----------------------------
    results = find_similar_chunks(query_embedding, collection, limit=top_k)

    if not results:
        logger.info("[VectorSearch] No results from Atlas, using in-memory fallback.")
        results = find_similar_chunks_in_memory(query_embedding, collection, top_k=top_k)

    if not results:
        logger.warning("No chunks retrieved from similarity search.")
        return _err("I don’t have knowledge about this topic. You may refer to another agent.")

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
        logger.warning(
            f"No chunks passed MIN_SCORE_THRESHOLD={MIN_SCORE_THRESHOLD}. "
            "LLM will NOT be called."
        )
        return _err("I don’t have knowledge about this topic. You may refer to another agent.")

    # -----------------------------
    # LOG accepted chunks
    # -----------------------------
    logger.info("Chunks passed threshold and will be sent to LLM:")
    for idx, doc in enumerate(filtered_results):
        logger.info(
            f"[ACCEPTED {idx + 1}] Score: {doc['score']:.4f}, "
            f"Unique ID: {doc.get('unique_id')}, "
            f"Chunk ID: {doc.get('unique_chunk_id')}"
        )

    # -----------------------------
    # Build combined result string
    # -----------------------------
    result_string = "\n---\n".join(doc["chunk_text"] for doc in filtered_results)

    # -----------------------------
    # Call LLM function
    # -----------------------------
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

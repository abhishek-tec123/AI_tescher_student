# -----------------------------
# Student-adaptive similarity search + Groq LLM
# -----------------------------

import logging
import os
import numpy as np
import re
import hashlib
import time
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
MIN_SCORE_THRESHOLD = 0.3  # Threshold for chunk selection - balanced with content validation

# -----------------------------
# Response Caching System
# -----------------------------
class ResponseCache:
    def __init__(self):
        self.cache = {}
        self.question_frequency = {}
        self.cache_ttl = 3600  # 1 hour cache TTL
    
    def _get_question_hash(self, question):
        """Generate a hash for the question to use as cache key."""
        # Extract core question first to handle variations
        core_question = extract_core_question(question)
        
        # Normalize question: lowercase, remove extra whitespace, remove punctuation
        normalized = re.sub(r'[^\w\s]', '', core_question.lower().strip())
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove common question words that don't affect the core meaning
        stop_words = ['what', 'is', 'are', 'the', 'a', 'an', 'tell', 'me', 'explain', 'describe']
        words = normalized.split()
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        normalized = ' '.join(filtered_words)
        
        logger.info(f"[ResponseCache] Normalized question: '{normalized}'")
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def get_cached_response(self, question, student_id=None):
        """Get cached response if available and not expired."""
        question_hash = self._get_question_hash(question)
        current_time = time.time()
        
        if question_hash in self.cache:
            cached_data = self.cache[question_hash]
            
            # Check if cache is still valid
            if current_time - cached_data['timestamp'] < self.cache_ttl:
                # Update frequency count
                self.question_frequency[question_hash] = self.question_frequency.get(question_hash, 0) + 1
                
                frequency = self.question_frequency[question_hash]
                logger.info(f"[ResponseCache] Question repeated {frequency} times, using cached response")
                
                # Return longer response for repeated questions
                response = cached_data['response']
                if frequency > 1:
                    response = self._make_response_longer(response, frequency)
                
                return {
                    'response': response,
                    'quality_scores': cached_data['quality_scores'],
                    'from_cache': True,
                    'repeat_count': frequency
                }
            else:
                # Cache expired, remove it
                del self.cache[question_hash]
                if question_hash in self.question_frequency:
                    del self.question_frequency[question_hash]
        
        return None
    
    def cache_response(self, question, response, quality_scores, student_id=None):
        """Cache a response for future use."""
        question_hash = self._get_question_hash(question)
        
        self.cache[question_hash] = {
            'response': response,
            'quality_scores': quality_scores,
            'timestamp': time.time(),
            'student_id': student_id
        }
        
        # Initialize frequency count
        if question_hash not in self.question_frequency:
            self.question_frequency[question_hash] = 1
        
        logger.info(f"[ResponseCache] Cached response for question (hash: {question_hash[:8]}...)")
    
    def _make_response_longer(self, original_response, repeat_count):
        """Make response longer for repeated questions."""
        # Add more detailed explanations for repeated questions
        longer_prefixes = [
            "Since you've asked about this topic again, let me provide you with a more comprehensive explanation:\n\n",
            "Building on our previous discussion, here's a more detailed response:\n\n",
            "As this is an important topic you're revisiting, I'll elaborate further:\n\n",
            "Let me expand on the previous answer with additional details and context:\n\n"
        ]
        
        longer_suffixes = [
            "\n\nIf you need even more specific information about any aspect of this topic, please let me know!",
            "\n\nFeel free to ask follow-up questions if you'd like me to dive deeper into any particular area.",
            "\n\nI hope this expanded explanation helps you better understand this concept.",
            "\n\nWould you like me to provide examples or clarify any specific points in more detail?"
        ]
        
        prefix = longer_prefixes[min(repeat_count - 2, len(longer_prefixes) - 1)]
        suffix = longer_suffixes[min(repeat_count - 2, len(longer_suffixes) - 1)]
        
        return prefix + original_response + suffix
    
    def clear_cache(self):
        """Clear all cached responses."""
        self.cache.clear()
        self.question_frequency.clear()
        logger.info("[ResponseCache] Cache cleared")

# Global cache instance
response_cache = ResponseCache()

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

    # Pattern 0: "Search Query (RL Optimized):\n<query>"
    # This comes from mainAgent.py after RL optimization
    # Using re.DOTALL and a more flexible pattern to catch the content before the next section
    match = re.search(r"Search Query \(RL Optimized\):\s*\n\s*(.+?)(?:\n\n|\n[A-Z][a-z]+:|$)", query, re.DOTALL | re.IGNORECASE)
    if match:
        core = match.group(1).strip()
        if core:
            # print(f"DEBUG: Extracted via Pattern 0: {core[:100]}...")
            return core

    # Pattern 0.1: "Original Student Question:\n<question>"
    match = re.search(r"Original Student Question:\s*\n\s*(.+?)(?:\n\n|\nSearch Query|$)", query, re.DOTALL | re.IGNORECASE)
    if match:
        core = match.group(1).strip()
        if core:
            return core

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
        # Avoid systemic lines in fallbacks
        systemic_prefixes = (
            'Class:', 'Subject:', 'Student', 'Rules:', 'Previous', 
            'You are an expert', 'IMPORTANT INSTRUCTIONS', 'Target student', 'Use a friendly'
        )
        
        # If first line is very short and looks like a question, use it
        first_line = lines[0].strip()
        if len(first_line) < 200 and '?' in first_line and not first_line.startswith(systemic_prefixes):
            return first_line
            
        # Otherwise, if query is very long (>500 chars), use first meaningful line
        if len(query) > 500:
            for line in lines:  
                line = line.strip()
                if line and 10 < len(line) < 300 and not line.startswith(systemic_prefixes):
                    # Check if it contains labels we might have missed
                    if "Question:" in line or "Query:" in line:
                        continue
                    return line
    
    return query[:500] if len(query) > 500 else query

# -----------------------------
# Embedding helper
# -----------------------------
def embed_query(query: str, embedding_model) -> list:
    """Generate embedding vector for a query using the provided model."""
    return embedding_model.embed_query(query)

# -----------------------------
# Content relevance validation
# -----------------------------
def validate_content_relevance(query: str, chunk_text: str, min_keyword_matches: int = 2) -> bool:
    """
    Validates that retrieved chunk content is actually relevant to the query.
    Prevents false positives by checking keyword presence and semantic relevance.
    Slightly relaxed for very short, profile-style questions so that
    teacher resume/profile chunks can be used when appropriate.
    """
    if not query or not chunk_text:
        return False
    
    # Extract key terms from query (remove common words)
    query_lower = query.lower()
    query_words = [word.strip("?.,!;:()[]{}\"'") for word in query_lower.split() 
                   if len(word) > 2 and word not in ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'is', 'are', 'was', 'were', 'what', 'how', 'when', 'where', 'why', 'tell', 'me', 'explain', 'describe']]
    
    chunk_lower = chunk_text.lower()
    
    # Count keyword matches
    keyword_matches = 0
    for word in query_words:
        if word in chunk_lower:
            keyword_matches += 1
    
    # Dynamically relax requirement for very short/profile-style queries
    effective_min_matches = min_keyword_matches
    if len(query_words) <= 3:
        effective_min_matches = 1
    
    # Require minimum keyword matches
    if keyword_matches < effective_min_matches:
        logger.info(f"[ContentValidation] Rejected chunk: only {keyword_matches}/{len(query_words)} keywords matched (required {effective_min_matches})")
        return False
    
    # Additional check: chunk should not be too generic
    generic_phrases = ['this is a', 'this is an', 'it is a', 'it is an', 'here is', 'there is', 'the following', 'as follows']
    for phrase in generic_phrases:
        if chunk_lower.strip().startswith(phrase):
            logger.info(f"[ContentValidation] Rejected chunk: starts with generic phrase '{phrase}'")
            return False
    
    logger.info(f"[ContentValidation] Accepted chunk: {keyword_matches}/{len(query_words)} keywords matched (required {effective_min_matches})")
    return True

# -----------------------------
# Vector search helpers
# -----------------------------
def find_similar_chunks(query_embedding, collection, query="", num_candidates=100, limit=TOP_K, index_name=VECTOR_INDEX_NAME):
    """Cosine similarity search with NO fallback - balanced threshold with content validation."""
    logger.info(f"[CosineSearch] Using in-memory cosine similarity search ONLY")
    
    # ONLY use cosine similarity - NO FALLBACKS ALLOWED
    cosine_results = find_similar_chunks_in_memory(query_embedding, collection, top_k=limit, similarity_threshold=0.3, query_text=query)
    
    if cosine_results:
        logger.info(f"[CosineSearch] Cosine similarity returned {len(cosine_results)} results")
        return cosine_results
    else:
        # ABSOLUTE RULE: No results = NO FALLBACK - return empty list
        logger.error(f"🚫 COSINE SEARCH FAILED: No results found and NO fallbacks allowed. Returning empty list.")
        return []

def find_similar_chunks_in_memory(query_embedding, collection, top_k=TOP_K, similarity_threshold=0.3, query_text=""):
    """In-memory cosine similarity search with balanced threshold and content validation."""
    logger.info(f"[InMemorySearch] Starting in-memory cosine similarity search with threshold {similarity_threshold}")
    # Match the current nested schema used when storing documents
    docs = list(
        collection.find(
            {},
            {
                "embedding.vector": 1,
                "chunk.text": 1,
                "chunk.unique_chunk_id": 1,
                "document.doc_unique_id": 1,
                "subject_agent_id": 1,
                "document_id": 1,
                "agent_metadata": 1,
            },
        )
    )
    
    logger.info(f"[InMemorySearch] Found {len(docs)} documents with embeddings")

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

        unique_id = document_container.get("doc_unique_id") if document_container else None
        unique_chunk_id = chunk_container.get("unique_chunk_id", "N/A")
        chunk_text = chunk_container.get("text", "")

        similarity_score = cosine_similarity(query_embedding, embedding_vector)
        
        # FIRST check similarity threshold
        if similarity_score >= similarity_threshold:
            # THEN validate content relevance if query text is provided
            if query_text and not validate_content_relevance(query_text, chunk_text):
                logger.info(f"[InMemorySearch] Skipping chunk {unique_chunk_id} due to failed content validation")
                continue
                
            scored.append(
                {
                    # Normalize into the flat structure expected downstream
                    "unique_id": unique_id,
                    "unique_chunk_id": unique_chunk_id,
                    "chunk_text": chunk_text,
                    "score": similarity_score,
                    "subject_agent_id": doc.get("subject_agent_id"),
                    "document_id": doc.get("document_id"),
                    "document": document_container,
                    "chunk": doc.get("chunk"),
                    "agent_metadata": doc.get("agent_metadata"),
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_results = scored[:top_k]
    logger.info(f"[InMemorySearch] Returning {len(top_results)} results above threshold {similarity_threshold}, top score: {top_results[0]['score'] if top_results else 0:.4f}")
    return top_results

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
    STRICT VALIDATION: Only processes responses if valid content is provided.
    Returns the response text.
    """
    # ABSOLUTE CONTENT VALIDATION
    if not result_string or not result_string.strip():
        logger.error("🚫 EMPTY CONTENT: No valid content provided to LLM. Response BLOCKED.")
        return (
            "I don't have access to any relevant learning materials for this question. "
            "Please ask about topics covered in your current curriculum or consult your teacher."
        )
    
    if len(result_string.strip()) < 50:
        logger.error("🚫 INSUFFICIENT CONTENT: Content too short for meaningful response. Response BLOCKED.")
        return (
            "The available learning materials don't contain enough information about this topic. "
            "Please try a more specific question related to your curriculum."
        )
    
    try:
        response_text = generate_response_from_groq(
            input_text=result_string,
            query=query,
            student_profile=student_profile
        )

        if not response_text.strip():
            logger.warning("LLM returned empty response despite valid content.")
            return (
                "I'm not able to generate a response from the available learning materials. "
                "Please try rephrasing your question or ask your teacher for clarification."
            )

        logger.info(f"✅ LLM response generated successfully ({len(response_text)} chars)")
        return response_text

    except Exception as e:
        logger.error(f"🚫 LLM invocation failed: {e}")
        return "I'm not able to process this question with the available learning materials. Please ask your teacher for help."

# -----------------------------
# Main retrieval + LLM
# -----------------------------
def retrieve_chunk_for_query_send_to_llm(
    query: str,
    db_name: str = None,
    collection_name: str = None,
    embedding_model=None,
    student_profile: dict = None,
    top_k: int = TOP_K,
    disable_rl: bool = False
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
    # Check for cached response first
    # -----------------------------
    student_id = student_profile.get('student_id') if student_profile else None
    cached_response = response_cache.get_cached_response(query, student_id)
    
    if cached_response:
        logger.info(f"[ResponseCache] Returning cached response (repeat #{cached_response['repeat_count']})")
        return {
            "response": cached_response['response'], 
            "quality_scores": cached_response['quality_scores'],
            "from_cache": True,
            "repeat_count": cached_response['repeat_count']
        }

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
    results = find_similar_chunks(query_embedding, collection, query, limit=top_k)
    logger.info(f"[VectorSearch] Atlas search returned {len(results)} results")

    if not results:
        # ABSOLUTE RULE: No chunks retrieved = NO LLM call - no exceptions
        logger.error("🚫 NO CHUNKS RETRIEVED: Vector search returned no results. LLM call BLOCKED.")
        safe_msg = (
            "I'm not able to answer this question from the available learning materials. "
            "This question appears to be outside the scope of the current curriculum. "
            "Please try rephrasing your question with terms from your study materials or ask your teacher for help."
        )
        quality_scores = compute_quality_scores(
            query=query,
            response_text=safe_msg,
            retrieved_chunks=[],
            context_string="",
        )
        return {"response": safe_msg, "quality_scores": quality_scores, "content_restriction": "no_chunks_found"}

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
    # Filter by similarity threshold - BALANCED WITH CONTENT VALIDATION
    # -----------------------------
    MIN_SCORE_THRESHOLD = 0.3  # Threshold for chunk selection - content validation prevents false positives
    filtered_results = [
        doc for doc in results
        if doc.get("score", 0) >= MIN_SCORE_THRESHOLD
    ]

    if not filtered_results:
        # ABSOLUTE RULE: If nothing passes the similarity threshold, NEVER call the LLM
        logger.error(f"🚫 NO CHUNKS PASSED THRESHOLD: No chunks passed MIN_SCORE_THRESHOLD={MIN_SCORE_THRESHOLD}. LLM call BLOCKED.")
        safe_msg = (
            "I'm not able to find relevant content in the learning materials for this question. "
            "This question appears to be outside the scope of the current curriculum. "
            "Please try asking it in a different way using terms from your study materials or consult your teacher."
        )
        quality_scores = compute_quality_scores(
            query=query,
            response_text=safe_msg,
            retrieved_chunks=[],
            context_string="",
        )
        return {"response": safe_msg, "quality_scores": quality_scores, "content_restriction": "below_threshold"}

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

    # -----------------------------
    # Cache the response for future use
    # -----------------------------
    response_cache.cache_response(query, response_text, quality_scores, student_id)

    return {"response": response_text, "quality_scores": quality_scores, "from_cache": False, "content_restriction": "none"}
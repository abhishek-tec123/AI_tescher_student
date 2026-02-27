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
MIN_SCORE_THRESHOLD = 0.2  # Threshold for chunk selection - lowered for better recall

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
# Vector search helpers
# -----------------------------
def find_similar_chunks(query_embedding, collection, query="", num_candidates=100, limit=TOP_K, index_name=VECTOR_INDEX_NAME):
    """Cosine similarity search with regex fallback."""
    logger.info(f"[CosineSearch] Using in-memory cosine similarity search")
    
    # Try cosine similarity first
    cosine_results = find_similar_chunks_in_memory(query_embedding, collection, top_k=limit, similarity_threshold=0.2)
    
    if cosine_results:
        logger.info(f"[CosineSearch] Cosine similarity returned {len(cosine_results)} results")
        return cosine_results
    
    # If cosine similarity fails, try regex fallback
    logger.info(f"[CosineSearch] No cosine similarity results, trying regex fallback")
    regex_results = find_similar_chunks_regex_fallback(query, collection, limit=limit)
    
    return regex_results

def find_similar_chunks_regex_fallback(query, collection, limit=TOP_K):
    """Regex-based fallback search when cosine similarity fails."""
    logger.info(f"[RegexSearch] Starting regex fallback search")
    
    try:
        # Extract key terms from the query
        query_terms = query.lower().split()
        query_terms = [term.strip("?.,!;:") for term in query_terms if len(term) > 2]
        
        logger.info(f"[RegexSearch] Extracted terms: {query_terms[:5]}")  # Log first 5 terms
        
        # Build search pipeline
        pipeline = []
        
        if query_terms:
            # Create regex patterns - prioritize exact matches first
            patterns = []
            
            # Add exact word matches for first term (highest priority)
            if query_terms[0]:
                patterns.append({"chunk.text": {"$regex": r"\b" + re.escape(query_terms[0]) + r"\b", "$options": "i"}})
            
            # Add partial matches for all terms
            for term in query_terms[:5]:  # Limit to first 5 terms to avoid too many patterns
                patterns.append({"chunk.text": {"$regex": re.escape(term), "$options": "i"}})
            
            # Match documents containing any query term
            pipeline.append({
                "$match": {
                    "$or": patterns
                }
            })
            
            # Add a simple scoring mechanism based on term frequency and text length
            pipeline.append({
                "$addFields": {
                    "text_length": {"$strLenCP": "$chunk.text"},
                    "term_count": {
                        "$size": {
                            "$filter": {
                                "input": query_terms[:3],  # Check first 3 terms
                                "as": "term",
                                "cond": {
                                    "$regexMatch": {
                                        "input": "$chunk.text",
                                        "regex": {"$concat": ["(?i)", {"$literal": "\\b"}, "$$term", {"$literal": "\\b"}]}
                                    }
                                }
                            }
                        }
                    }
                }
            })
            
            # Sort by term count (descending) and text length (ascending for focused content)
            pipeline.append({
                "$sort": {"term_count": -1, "text_length": 1}
            })
            
        else:
            # If no query terms, just sample
            pipeline.append({"$sample": {"size": limit}})
        
        # Limit results
        pipeline.append({"$limit": limit})
        
        # Project final results with dynamic scoring
        pipeline.append({
            "$project": {
                "chunk_text": "$chunk.text",
                "score": {
                    "$switch": {
                        "branches": [
                            # High score for multiple term matches
                            {"case": {"$gte": ["$term_count", 3]}, "then": 0.7},
                            {"case": {"$gte": ["$term_count", 2]}, "then": 0.6},
                            {"case": {"$gte": ["$term_count", 1]}, "then": 0.5},
                            # Base score for text length (shorter, more focused content gets higher score)
                            {"case": {"$lt": [{"$strLenCP": "$chunk.text"}, 500]}, "then": 0.4},
                            {"case": {"$lt": [{"$strLenCP": "$chunk.text"}, 1000]}, "then": 0.3}
                        ],
                        "default": 0.2
                    }
                },
                "unique_id": "$document.doc_unique_id",
                "unique_chunk_id": "$chunk.unique_chunk_id",
                "subject_agent_id": "$subject_agent_id",
                "document_id": "$document_id",
                "document": {"doc_unique_id": "$document.doc_unique_id"},
                "chunk": {"text": "$chunk.text", "unique_chunk_id": "$chunk.unique_chunk_id"},
                "agent_metadata": "$agent_metadata"
            }
        })
        
        results = list(collection.aggregate(pipeline))
        logger.info(f"[RegexSearch] Regex search returned {len(results)} results")
        
        # Log top few results with scores
        for i, result in enumerate(results[:3]):
            logger.info(f"[RegexSearch] Result {i+1}: Score={result['score']:.3f}, Chunk ID: {result.get('unique_chunk_id')}")
        
        return results
        
    except Exception as e:
        logger.error(f"[RegexSearch] Regex search failed: {e}")
        # Final fallback to simple sampling
        try:
            pipeline = [
                {"$sample": {"size": limit}},
                {
                    "$project": {
                        "chunk_text": "$chunk.text",
                        "score": {"$literal": 0.1},  # Very low score for pure sampling
                        "unique_id": "$document.doc_unique_id",
                        "unique_chunk_id": "$chunk.unique_chunk_id",
                        "subject_agent_id": "$subject_agent_id",
                        "document_id": "$document_id",
                        "document": {"doc_unique_id": "$document.doc_unique_id"},
                        "chunk": {"text": "$chunk.text", "unique_chunk_id": "$chunk.unique_chunk_id"},
                        "agent_metadata": "$agent_metadata"
                    }
                }
            ]
            results = list(collection.aggregate(pipeline))
            logger.info(f"[RegexSearch] Sampling fallback returned {len(results)} results")
            return results
        except Exception as e2:
            logger.error(f"[RegexSearch] Even sampling failed: {e2}")
            return []

def find_similar_chunks_in_memory(query_embedding, collection, top_k=TOP_K, similarity_threshold=0.2):
    """Fallback in-memory cosine similarity search."""
    logger.info(f"[InMemorySearch] Starting in-memory cosine similarity search")
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
    logger.info(f"[InMemorySearch] Returning {len(top_results)} results, top score: {top_results[0]['score'] if top_results else 0:.4f}")
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
        logger.info("[VectorSearch] No results from Atlas, using in-memory fallback.")
        results = find_similar_chunks_in_memory(query_embedding, collection, top_k=top_k)
        logger.info(f"[VectorSearch] In-memory fallback returned {len(results)} results")

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

    # -----------------------------
    # Cache the response for future use
    # -----------------------------
    response_cache.cache_response(query, response_text, quality_scores, student_id)

    return {"response": response_text, "quality_scores": quality_scores, "from_cache": False}
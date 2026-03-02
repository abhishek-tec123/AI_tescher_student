# -----------------------------
# Enhanced similarity search with shared knowledge support
# -----------------------------

import logging
import os
import numpy as np
import hashlib
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from search.SimilaritySearch import (
    extract_core_question,
    embed_query,
    find_similar_chunks,
    find_similar_chunks_in_memory,
    get_llm_response_from_chunk,
    retrieve_chunk_for_query_send_to_llm,
    MIN_SCORE_THRESHOLD,
    TOP_K,
    response_cache
)
from search.structured_response import compute_quality_scores
from Teacher_AI_Agent.dbFun.shared_knowledge import shared_knowledge_manager

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
VECTOR_PATH = "embedding.vector"

def _build_safe_out_of_scope_response(query: str, restriction_reason: str):
    """
    Central helper to build a safe, curriculum-bound response when no
    relevant RAG content is available or when content restrictions apply.
    """
    safe_msg = (
        "I'm not able to answer this question from the available learning materials. "
        "This teaching assistant can only answer using your curriculum content and teacher-provided documents. "
        "Please try asking with terms from your study materials or consult your teacher for help."
    )
    quality_scores = compute_quality_scores(
        query=query,
        response_text=safe_msg,
        retrieved_chunks=[],
        context_string="",
    )
    # Tag that this was blocked by RAG policy, not hallucinated
    quality_scores["content_restriction"] = restriction_reason
    return {
        "response": safe_msg,
        "quality_scores": quality_scores,
        "sources": [],
        "source_summary": [],
        "chunks_used": 0,
        "from_cache": False,
        "content_restriction": restriction_reason,
    }


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
# Async MongoDB Connection Pool
# -----------------------------
_connection_pool = None
_executor = ThreadPoolExecutor(max_workers=10)

def get_async_client():
    """Get async MongoDB client with connection pooling."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = MongoClient(
            MONGODB_URI,
            maxPoolSize=20,
            minPoolSize=5,
            maxIdleTimeMS=30000,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
    return _connection_pool

# -----------------------------
# Vector Search Cache
# -----------------------------
_vector_cache = {}
_cache_ttl = 300  # 5 minutes

def _get_cache_key(query: str, db_name: str, collection_name: str, top_k: int) -> str:
    """Generate cache key for vector search results."""
    content = f"{query}_{db_name}_{collection_name}_{top_k}"
    return hashlib.md5(content.encode()).hexdigest()

def _get_cached_vector_results(cache_key: str):
    """Get cached vector search results if valid."""
    if cache_key in _vector_cache:
        cached_data, timestamp = _vector_cache[cache_key]
        if time.time() - timestamp < _cache_ttl:
            logger.info(f"🎯 Using cached vector results for key: {cache_key[:8]}...")
            return cached_data
        else:
            del _vector_cache[cache_key]
    return None

def _cache_vector_results(cache_key: str, results):
    """Cache vector search results."""
    _vector_cache[cache_key] = (results, time.time())
    # Limit cache size
    if len(_vector_cache) > 100:
        oldest_key = min(_vector_cache.keys(), key=lambda k: _vector_cache[k][1])
        del _vector_cache[oldest_key]

async def _search_agent_collection_async(db_name: str, collection_name: str, query_embedding, top_k: int, query_text=""):
    """Async wrapper for agent collection search with content validation."""
    def _search():
        try:
            client = get_async_client()
            if db_name in client.list_database_names() and collection_name in client[db_name].list_collection_names():
                agent_collection = client[db_name][collection_name]
                agent_results = find_similar_chunks(query_embedding, agent_collection, limit=top_k, query=query_text)
                
                # Apply additional content validation
                validated_results = []
                for result in agent_results:
                    chunk_text = result.get('text', result.get('chunk_text', ''))
                    if validate_content_relevance(query_text, chunk_text):
                        result["source_type"] = "agent"
                        result["source_name"] = f"{db_name}.{collection_name}"
                        validated_results.append(result)
                    else:
                        logger.info(f"[EnhancedSearch] Skipping agent chunk due to failed content validation")
                
                return validated_results, f"{db_name}.{collection_name}"
            return [], None
        except Exception as e:
            logger.error(f"Failed to search agent collection: {e}")
            return [], None
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _search)

async def _search_shared_documents_async(subject_agent_id: str, query_embedding, top_k: int, query_text=""):
    """Async wrapper for shared documents search with content validation."""
    def _search():
        try:
            # Get agent metadata to check if global RAG is enabled
            agent_global_rag_enabled = False
            try:
                from Teacher_AI_Agent.dbFun.get_agent_data import get_agent_data
                agent_data = get_agent_data(subject_agent_id)
                agent_metadata = agent_data.get("agent_metadata", {})
                agent_global_rag_enabled = agent_metadata.get("global_rag_enabled", False)
            except Exception as e:
                logger.warning(f"Failed to get agent metadata for {subject_agent_id}: {e}")
                agent_global_rag_enabled = False
            
            if not agent_global_rag_enabled:
                return [], []
            
            enabled_shared_docs = shared_knowledge_manager.get_agent_enabled_documents(subject_agent_id)
            if not enabled_shared_docs:
                return [], []
            
            client = get_async_client()
            shared_collection = client["teacher_ai"]["shared_knowledge"]
            all_shared_results = []
            sources_info = []
            
            for shared_doc in enabled_shared_docs:
                doc_id = shared_doc["document_id"]
                doc_name = shared_doc["document_name"]
                
                # Search within this shared document using a more permissive
                # similarity threshold, relying on strict content validation
                # and document filters to keep results safe and RAG-only.
                shared_results = find_similar_chunks_in_memory(
                    query_embedding,
                    shared_collection,
                    top_k=top_k // len(enabled_shared_docs) if enabled_shared_docs else top_k,
                    similarity_threshold=0.0,
                    query_text=query_text
                )
                
                # Filter results to only include chunks from this document AND pass content validation
                filtered_results = []
                for result in shared_results:
                    is_match = (
                        result.get("subject_agent_id") == subject_agent_id or
                        result.get("document_id") == doc_id or
                        result.get("document", {}).get("doc_unique_id") == doc_id
                    )
                    
                    if is_match:
                        # Apply content validation
                        chunk_text = result.get('text', result.get('chunk_text', ''))
                        if validate_content_relevance(query_text, chunk_text):
                            result["source_type"] = "shared"
                            result["source_name"] = f"shared:{doc_name}"
                            filtered_results.append(result)
                        else:
                            logger.info(f"[EnhancedSearch] Skipping shared chunk due to failed content validation")
                
                all_shared_results.extend(filtered_results)
                if filtered_results:
                    sources_info.append({
                        "type": "shared",
                        "name": doc_name,
                        "document_id": doc_id,
                        "results_count": len(filtered_results)
                    })
            
            return all_shared_results, sources_info
            
        except Exception as e:
            logger.error(f"Failed to search shared documents: {e}")
            return [], []
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _search)

# -----------------------------
# Enhanced search with shared knowledge
# -----------------------------
async def retrieve_chunks_with_shared_knowledge_async(
    query: str,
    db_name: str = None,
    collection_name: str = None,
    subject_agent_id: str = None,
    embedding_model=None,
    student_profile: dict = None,
    top_k: int = 15,
    disable_rl: bool = False
) -> dict:
    """
    Async enhanced retrieval that includes both agent-specific and shared knowledge documents.
    Returns: {"response": str, "quality_scores": dict, "sources": list}
    """
    
    # -----------------------------
    # Basic validation
    # -----------------------------
    _err = lambda msg: {"response": msg, "quality_scores": {}, "sources": []}

    if not embedding_model:
        logger.error("No embedding model provided.")
        return _err("No embedding model provided.")

    if not query or not query.strip():
        logger.error("Query cannot be empty.")
        return _err("Query cannot be empty.")

    # -----------------------------
    # Check vector cache first
    # -----------------------------
    cache_key = _get_cache_key(query, db_name or "", collection_name or "", top_k)
    cached_results = _get_cached_vector_results(cache_key)
    if cached_results:
        return cached_results

    # -----------------------------
    # Check for cached response
    # -----------------------------
    student_id = student_profile.get('student_id') if student_profile else None
    cached_response = response_cache.get_cached_response(query, student_id)
    
    if cached_response:
        logger.info(f"[ResponseCache] Returning cached response (repeat #{cached_response['repeat_count']})")
        result = {
            "response": cached_response['response'], 
            "quality_scores": cached_response['quality_scores'],
            "sources": [],
            "source_summary": [],
            "from_cache": True,
            "repeat_count": cached_response['repeat_count']
        }
        _cache_vector_results(cache_key, result)
        return result

    # -----------------------------
    # Extract core question for embedding
    # -----------------------------
    # Even when RL is disabled for shared documents, we still extract the
    # student's core question from the formatted prompt to drive retrieval.
    core_question = extract_core_question(query)
    if disable_rl:
        logger.info(
            f"RL disabled for shared documents - using extracted core question from original prompt: "
            f"'{core_question[:100]}...'"
        )
    else:
        logger.info(
            f"Core question extracted for embedding: '{core_question[:100]}...' "
            f"(full query length: {len(query)})"
        )
    
    # Generate query embedding using core question only
    query_embedding = embed_query(core_question, embedding_model)

    # -----------------------------
    # Parallel search for agent and shared documents
    # -----------------------------
    search_tasks = []
    
    if db_name and collection_name:
        # Use the extracted core_question for similarity + validation
        search_tasks.append(_search_agent_collection_async(db_name, collection_name, query_embedding, top_k, core_question))
    
    if subject_agent_id:
        # Use the extracted core_question for similarity + validation
        search_tasks.append(_search_shared_documents_async(subject_agent_id, query_embedding, top_k, core_question))
    
    # Execute searches in parallel
    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
    
    # Process results
    all_results = []
    sources_info = []
    raw_agent_results = []
    raw_shared_results = []
    
    for result in search_results:
        if isinstance(result, Exception):
            logger.error(f"Search task failed: {result}")
            continue
            
        if result is None:
            continue
            
        # Handle agent collection results
        if len(result) == 2 and isinstance(result[0], list) and isinstance(result[1], (str, type(None))):
            agent_results, source_name = result
            if agent_results:
                raw_agent_results.extend(agent_results)
                if source_name:
                    sources_info.append({
                        "type": "agent",
                        "name": source_name,
                        "results_count": len(agent_results)
                    })
                    logger.info(f"Retrieved {len(agent_results)} chunks from {source_name}")
        
        # Handle shared documents results
        elif len(result) == 2 and isinstance(result[0], list) and isinstance(result[1], list):
            shared_results, shared_sources = result
            if shared_results:
                raw_shared_results.extend(shared_results)
                sources_info.extend(shared_sources)
                logger.info(f"Retrieved {len(shared_results)} chunks from shared documents")
    
    logger.info(f"Total raw agent chunks: {len(raw_agent_results)}")
    logger.info(f"Total raw shared chunks: {len(raw_shared_results)}")
    
    # Sort by score within each source
    raw_agent_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    raw_shared_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # Apply high threshold filtering (>0.3) to agent results and a slightly
    # more permissive threshold for shared/global docs.
    AGENT_HIGH_THRESHOLD = 0.3
    SHARED_HIGH_THRESHOLD = 0.2
    filtered_agent_results = [
        doc for doc in raw_agent_results
        if doc.get("score", 0) >= AGENT_HIGH_THRESHOLD
    ]
    
    filtered_shared_results = [
        doc for doc in raw_shared_results
        if doc.get("score", 0) >= SHARED_HIGH_THRESHOLD
    ]
    
    logger.info(f"✅ Agent chunks passing threshold {AGENT_HIGH_THRESHOLD}: {len(filtered_agent_results)}")
    logger.info(f"✅ Shared chunks passing threshold {SHARED_HIGH_THRESHOLD}: {len(filtered_shared_results)}")
    
    # ABSOLUTE RULE: If neither agent nor shared chunks pass the threshold, NEVER call the LLM
    if not filtered_agent_results and not filtered_shared_results:
        logger.error("🚫 NO RELEVANT CONTENT FOUND: No chunks from agent or shared documents met threshold requirements. LLM call BLOCKED.")
        result = _build_safe_out_of_scope_response(query, "no_relevant_content")
        _cache_vector_results(cache_key, result)
        return result
    
    # Agent-first combination: agent chunks are primary, shared chunks supplement
    final_results = filtered_agent_results + filtered_shared_results
    
    # Sort final results by score and limit
    final_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    all_results = final_results[:top_k]
    
    logger.info(f"Using {len(all_results)} total chunks for LLM (agent first).")
    
    # Log all selected chunks with detailed information for debugging
    logger.info("=" * 80)
    logger.info("🔍 SELECTED CHUNKS FOR LLM (AFTER THRESHOLD FILTERING):")
    logger.info("=" * 80)
    for i, chunk in enumerate(all_results):
        chunk_content = chunk.get('text', chunk.get('chunk_text', ''))
        chunk_preview = chunk_content[:200] + ("..." if len(chunk_content) > 200 else "")
        logger.info(f"SELECTED CHUNK {i+1}:")
        logger.info(f"  Score: {chunk.get('score', 0):.4f}")
        logger.info(f"  Source: {chunk.get('source_type', 'unknown')}")
        logger.info(f"  Content Preview: {chunk_preview}")
        logger.info(f"  Full Content Length: {len(chunk_content)} chars")
        logger.info("-" * 60)
    
    # Build context from chunks
    context_chunks = []
    for i, chunk in enumerate(all_results):
        chunk_content = chunk.get('text', chunk.get('chunk_text', ''))[:2000]
        source_info = f" ({chunk.get('source_type', 'unknown')})"
        context_chunks.append(f"Chunk {i+1}{source_info}: {chunk_content}")
    
    result_string = "\n\n".join(context_chunks)
    
    # Log what content is being sent to LLM for debugging
    logger.info(f"📤 Sending {len(context_chunks)} chunks to LLM, total chars: {len(result_string)}")
    if context_chunks:
        logger.info(f"📝 First chunk preview: {context_chunks[0][:200]}...")
    logger.info(f"📤 SENDING TO LLM:")
    logger.info("=" * 80)
    
    # Generate response
    logger.info(f"📤 CALLING LLM WITH:")
    logger.info(f"Query: {query[:200]}...")
    logger.info(f"Context Length: {len(result_string)} chars")
    logger.info("=" * 80)
    response_result = get_llm_response_from_chunk(
        result_string=result_string,
        query=query,
        student_profile=student_profile,
        logger=logger
    )
    
    logger.info("=" * 80)
    logger.info("📝 LLM RESPONSE RECEIVED:")
    logger.info("=" * 80)
    
    if isinstance(response_result, dict):
        response_text = response_result.get("response", "")
        quality_scores = response_result.get("quality_scores", {})
    else:
        response_text = str(response_result)
        quality_scores = {}
    
    # Log LLM response details for debugging
    logger.info(f"Response Length: {len(response_text)} chars")
    logger.info(f"Response Preview: {response_text[:300]}...")
    logger.info(f"Quality Scores: {quality_scores}")
    
    # Compute quality scores if not provided
    if not quality_scores:
        quality_scores = compute_quality_scores(query, response_text, all_results, result_string)
    
    result = {
        "response": response_text,
        "quality_scores": quality_scores,
        "sources": sources_info,
        "source_summary": [f"{src['type']}: {src['name']} ({src['results_count']} chunks)" for src in sources_info],
        "chunks_used": len(all_results),
        "from_cache": False
    }
    
    # Cache the result
    _cache_vector_results(cache_key, result)
    
    return result

def retrieve_chunks_with_shared_knowledge(
    query: str,
    db_name: str = None,
    collection_name: str = None,
    subject_agent_id: str = None,
    embedding_model=None,
    student_profile: dict = None,
    top_k: int = 15,
    disable_rl: bool = False
) -> dict:
    """
    Synchronous wrapper for backward compatibility.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in an event loop, use run_in_executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, 
                    retrieve_chunks_with_shared_knowledge_async(
                        query, db_name, collection_name, subject_agent_id,
                        embedding_model, student_profile, top_k
                    )
                )
                return future.result(timeout=30)
        else:
            # If no event loop running, run directly
            return asyncio.run(
                retrieve_chunks_with_shared_knowledge_async(
                    query, db_name, collection_name, subject_agent_id,
                    embedding_model, student_profile, top_k
                )
            )
    except Exception as e:
        logger.error(f"Error in async wrapper: {e}")
        # Fallback to synchronous behavior
        return _fallback_sync_search(query, db_name, collection_name, subject_agent_id, embedding_model, student_profile, top_k, disable_rl)

def _fallback_sync_search(
    query: str,
    db_name: str = None,
    collection_name: str = None,
    subject_agent_id: str = None,
    embedding_model=None,
    student_profile: dict = None,
    top_k: int = TOP_K,
    disable_rl: bool = False
) -> dict:
    """
    Fallback synchronous search implementation.
    """
    _err = lambda msg: {"response": msg, "quality_scores": {}, "sources": []}

    if not embedding_model:
        return _err("No embedding model provided.")

    if not query or not query.strip():
        return _err("Query cannot be empty.")

    # Check response cache
    student_id = student_profile.get('student_id') if student_profile else None
    cached_response = response_cache.get_cached_response(query, student_id)
    
    if cached_response:
        return {
            "response": cached_response['response'], 
            "quality_scores": cached_response['quality_scores'],
            "sources": [],
            "from_cache": True,
            "repeat_count": cached_response['repeat_count']
        }

    # Extract core question and embed
    # Even when RL is disabled for shared documents, use the extracted core
    # question (not the full formatted prompt) for retrieval.
    core_question = extract_core_question(query)
    if disable_rl:
        logger.info(
            f"RL disabled for shared documents - using extracted core question from original prompt: "
            f"'{core_question[:100]}...'"
        )
    else:
        logger.info(f"Core question extracted for embedding (sync): '{core_question[:100]}...'")
    query_embedding = embed_query(core_question, embedding_model)

    # Generate cache key for this query
    cache_key = _get_cache_key(query, db_name or "", collection_name or "", top_k)

    # Synchronous searches
    all_results = []
    sources_info = []

    # Agent collection search with content validation
    if db_name and collection_name:
        try:
            client = get_async_client()
            if db_name in client.list_database_names() and collection_name in client[db_name].list_collection_names():
                agent_collection = client[db_name][collection_name]
                # Use core_question for similarity + validation
                agent_results = find_similar_chunks(query_embedding, agent_collection, limit=top_k, query=core_question)
                
                # Apply additional content validation
                validated_results = []
                for result in agent_results:
                    chunk_text = result.get('text', result.get('chunk_text', ''))
                    if validate_content_relevance(query, chunk_text):
                        result["source_type"] = "agent"
                        result["source_name"] = f"{db_name}.{collection_name}"
                        validated_results.append(result)
                    else:
                        logger.info(f"[EnhancedSearch] Skipping agent chunk due to failed content validation (sync)")
                
                all_results.extend(validated_results)
                if validated_results:
                    sources_info.append({
                        "type": "agent",
                        "name": f"{db_name}.{collection_name}",
                        "results_count": len(validated_results)
                    })
        except Exception as e:
            logger.error(f"Failed to search agent collection: {e}")

    # Shared documents search with content validation (simplified)
    if subject_agent_id:
        try:
            from Teacher_AI_Agent.dbFun.get_agent_data import get_agent_data
            agent_data = get_agent_data(subject_agent_id)
            agent_metadata = agent_data.get("agent_metadata", {})
            agent_global_rag_enabled = agent_metadata.get("global_rag_enabled", False)
            
            if agent_global_rag_enabled:
                enabled_shared_docs = shared_knowledge_manager.get_agent_enabled_documents(subject_agent_id)
                if enabled_shared_docs:
                    client = get_async_client()
                    shared_collection = client["teacher_ai"]["shared_knowledge"]
                    
                    for shared_doc in enabled_shared_docs:
                        doc_id = shared_doc["document_id"]
                        doc_name = shared_doc["document_name"]
                        
                        # Use in-memory cosine search with a more permissive
                        # similarity threshold for shared/global docs, driven
                        # by the extracted core_question.
                        shared_results = find_similar_chunks_in_memory(
                            query_embedding,
                            shared_collection,
                            top_k=top_k // len(enabled_shared_docs),
                            similarity_threshold=0.0,
                            query_text=core_question
                        )
                        
                        filtered_results = []
                        for result in shared_results:
                            is_match = (
                                result.get("subject_agent_id") == subject_agent_id or
                                result.get("document_id") == doc_id or
                                result.get("document", {}).get("doc_unique_id") == doc_id
                            )
                            
                            if is_match:
                                # Apply content validation
                                chunk_text = result.get('text', result.get('chunk_text', ''))
                                if validate_content_relevance(query, chunk_text):
                                    result["source_type"] = "shared"
                                    result["source_name"] = f"shared:{doc_name}"
                                    filtered_results.append(result)
                                else:
                                    logger.info(f"[EnhancedSearch] Skipping shared chunk due to failed content validation (sync)")
                        
                        all_results.extend(filtered_results)
                        if filtered_results:
                            sources_info.append({
                                "type": "shared",
                                "name": doc_name,
                                "document_id": doc_id,
                                "results_count": len(filtered_results)
                            })
        except Exception as e:
            logger.error(f"Failed to search shared documents: {e}")

    # Process results
    all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # Separate agent and shared results
    agent_results = [doc for doc in all_results if doc.get('source_type') == 'agent']
    shared_results = [doc for doc in all_results if doc.get('source_type') == 'shared']
    
    logger.info(f"Total raw agent chunks (sync): {len(agent_results)}")
    logger.info(f"Total raw shared chunks (sync): {len(shared_results)}")
    
    # Apply high threshold filtering (>0.3) to agent results and slightly
    # more permissive threshold for shared/global docs.
    AGENT_HIGH_THRESHOLD = 0.3
    SHARED_HIGH_THRESHOLD = 0.2
    filtered_agent_results = [
        doc for doc in agent_results
        if doc.get("score", 0) >= AGENT_HIGH_THRESHOLD
    ]
    
    filtered_shared_results = [
        doc for doc in shared_results
        if doc.get("score", 0) >= SHARED_HIGH_THRESHOLD
    ]
    
    logger.info(f"✅ Agent chunks passing threshold {AGENT_HIGH_THRESHOLD} (sync): {len(filtered_agent_results)}")
    logger.info(f"✅ Shared chunks passing threshold {SHARED_HIGH_THRESHOLD} (sync): {len(filtered_shared_results)}")
    
    # ABSOLUTE RULE: If neither agent nor shared chunks pass the threshold, NEVER call the LLM
    if not filtered_agent_results and not filtered_shared_results:
        logger.error("🚫 NO RELEVANT CONTENT FOUND (sync): No chunks from agent or shared documents met threshold requirements. LLM call BLOCKED.")
        result = _build_safe_out_of_scope_response(query, "no_relevant_content")
        _cache_vector_results(cache_key, result)
        return result
    
    # Agent-first combination: agent chunks are primary, shared chunks supplement
    final_results = filtered_agent_results + filtered_shared_results
    
    # Sort final results by score and limit
    final_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    all_results = final_results[:top_k]
    
    logger.info(f"Using {len(all_results)} total chunks for LLM (sync, agent first).")
    
    # Generate response
    context_chunks = []
    for i, chunk in enumerate(all_results):
        chunk_content = chunk.get('text', chunk.get('chunk_text', ''))[:2000]
        source_info = f" ({chunk.get('source_type', 'unknown')})"
        context_chunks.append(f"Chunk {i+1}{source_info}: {chunk_content}")
    
    result_string = "\n\n".join(context_chunks)
    
    # Log what content is being sent to LLM for debugging
    logger.info(f"📤 Sending {len(context_chunks)} chunks to LLM, total chars: {len(result_string)}")
    if context_chunks:
        logger.info(f"📝 First chunk preview: {context_chunks[0][:200]}...")
    
    response_result = get_llm_response_from_chunk(
        result_string=result_string,
        query=query,
        student_profile=student_profile,
        logger=logger
    )
    
    if isinstance(response_result, dict):
        response_text = response_result.get("response", "")
        quality_scores = response_result.get("quality_scores", {})
    else:
        response_text = str(response_result)
        quality_scores = {}
    
    # Compute quality scores if not provided
    if not quality_scores:
        logger.info(f"🔍 Computing quality scores with {len(all_results)} chunks")
        for i, chunk in enumerate(all_results):
            score = chunk.get("score", 0)
            source_type = chunk.get("source_type", "unknown")
            logger.info(f"   - Chunk {i+1}: score={score}, source_type={source_type}")
        quality_scores = compute_quality_scores(query, response_text, all_results, result_string)
        logger.info(f"📊 Final quality scores: {quality_scores}")
    
    result = {
        "response": response_text,
        "quality_scores": quality_scores,
        "sources": sources_info,
        "source_summary": [f"{src['type']}: {src['name']} ({src['results_count']} chunks)" for src in sources_info],
        "chunks_used": len(all_results),
        "from_cache": False
    }
    
    # Cache the result
    _cache_vector_results(cache_key, result)
    
    return result

# -----------------------------
# Backward compatibility wrapper
# -----------------------------
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
    """
    Enhanced version of retrieve_chunk_for_query_send_to_llm that includes shared knowledge.
    Falls back to original behavior if no shared documents are enabled.
    """
    
    # If no subject_agent_id, use original search
    if not subject_agent_id:
        return retrieve_chunk_for_query_send_to_llm(
            query=query,
            db_name=db_name,
            collection_name=collection_name,
            embedding_model=embedding_model,
            student_profile=student_profile,
            top_k=top_k,
            disable_rl=disable_rl
        )
    
    # Use enhanced search with shared knowledge
    return retrieve_chunks_with_shared_knowledge(
        query=query,
        db_name=db_name,
        collection_name=collection_name,
        subject_agent_id=subject_agent_id,
        embedding_model=embedding_model,
        student_profile=student_profile,
        top_k=top_k,
        disable_rl=disable_rl
    )

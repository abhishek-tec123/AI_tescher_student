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

async def _search_agent_collection_async(db_name: str, collection_name: str, query_embedding, top_k: int):
    """Async wrapper for agent collection search."""
    def _search():
        try:
            client = get_async_client()
            if db_name in client.list_database_names() and collection_name in client[db_name].list_collection_names():
                agent_collection = client[db_name][collection_name]
                agent_results = find_similar_chunks(query_embedding, agent_collection, limit=top_k)
                
                # Mark results as agent-specific
                for result in agent_results:
                    result["source_type"] = "agent"
                    result["source_name"] = f"{db_name}.{collection_name}"
                
                return agent_results, f"{db_name}.{collection_name}"
            return [], None
        except Exception as e:
            logger.error(f"Failed to search agent collection: {e}")
            return [], None
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _search)

async def _search_shared_documents_async(subject_agent_id: str, query_embedding, top_k: int):
    """Async wrapper for shared documents search."""
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
                
                # Search within this shared document
                shared_results = find_similar_chunks(
                    query_embedding, 
                    shared_collection, 
                    limit=top_k // len(enabled_shared_docs) if enabled_shared_docs else top_k
                )
                
                # Filter results to only include chunks from this document
                filtered_results = []
                for result in shared_results:
                    is_match = (
                        result.get("subject_agent_id") == subject_agent_id or
                        result.get("document_id") == doc_id or
                        result.get("document", {}).get("doc_unique_id") == doc_id
                    )
                    
                    if is_match:
                        result["source_type"] = "shared"
                        result["source_name"] = f"shared:{doc_name}"
                        filtered_results.append(result)
                
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
    if disable_rl:
        # For shared documents, use original query to avoid RL interference
        core_question = query
        logger.info(f"RL disabled for shared documents - using original query: '{query[:100]}...'")
    else:
        core_question = extract_core_question(query)
        logger.info(f"Core question extracted for embedding: '{core_question[:100]}...' (full query length: {len(query)})")
    
    # Generate query embedding using core question only
    query_embedding = embed_query(core_question, embedding_model)

    # -----------------------------
    # Parallel search for agent and shared documents
    # -----------------------------
    search_tasks = []
    
    if db_name and collection_name:
        search_tasks.append(_search_agent_collection_async(db_name, collection_name, query_embedding, top_k))
    
    if subject_agent_id:
        search_tasks.append(_search_shared_documents_async(subject_agent_id, query_embedding, top_k))
    
    # Execute searches in parallel
    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
    
    # Process results
    all_results = []
    sources_info = []
    
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
                all_results.extend(agent_results)
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
                all_results.extend(shared_results)
                sources_info.extend(shared_sources)
                logger.info(f"Retrieved {len(shared_results)} chunks from shared documents")
    
    # Sort by score and limit results
    all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # Separate agent and shared results
    agent_results = [doc for doc in all_results if doc.get('source_type') == 'agent']
    shared_results = [doc for doc in all_results if doc.get('source_type') == 'shared']
    
    # Apply threshold filtering only to agent results
    filtered_agent_results = [
        doc for doc in agent_results
        if doc.get("score", 0) >= MIN_SCORE_THRESHOLD
    ]
    
    # Combine results: shared documents (no threshold) + filtered agent results
    final_results = shared_results + filtered_agent_results
    
    # Sort final results by score and limit
    final_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    all_results = final_results[:top_k]
    
    logger.info(f"✅ Using {len([d for d in all_results if d.get('source_type') == 'shared'])} shared documents (no threshold)")
    logger.info(f"✅ Using {len([d for d in all_results if d.get('source_type') == 'agent'])} agent documents (threshold: {MIN_SCORE_THRESHOLD})")
    
    # Generate response using the chunks
    if not all_results:
        logger.warning("No relevant chunks found from any source")
        result = {"response": "I couldn't find relevant information to answer your question.", "quality_scores": {}, "sources": []}
        _cache_vector_results(cache_key, result)
        return result
    
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
    
    # Generate response
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
    if disable_rl:
        # For shared documents, use original query to avoid RL interference
        core_question = query
        logger.info(f"RL disabled for shared documents - using original query: '{query[:100]}...'")
    else:
        core_question = extract_core_question(query)
    query_embedding = embed_query(core_question, embedding_model)

    # Generate cache key for this query
    cache_key = _get_cache_key(query, db_name or "", collection_name or "", top_k)

    # Synchronous searches
    all_results = []
    sources_info = []

    # Agent collection search
    if db_name and collection_name:
        try:
            client = get_async_client()
            if db_name in client.list_database_names() and collection_name in client[db_name].list_collection_names():
                agent_collection = client[db_name][collection_name]
                agent_results = find_similar_chunks(query_embedding, agent_collection, limit=top_k)
                
                for result in agent_results:
                    result["source_type"] = "agent"
                    result["source_name"] = f"{db_name}.{collection_name}"
                
                all_results.extend(agent_results)
                sources_info.append({
                    "type": "agent",
                    "name": f"{db_name}.{collection_name}",
                    "results_count": len(agent_results)
                })
        except Exception as e:
            logger.error(f"Failed to search agent collection: {e}")

    # Shared documents search (simplified)
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
                        
                        shared_results = find_similar_chunks(
                            query_embedding, 
                            shared_collection, 
                            limit=top_k // len(enabled_shared_docs)
                        )
                        
                        filtered_results = []
                        for result in shared_results:
                            is_match = (
                                result.get("subject_agent_id") == subject_agent_id or
                                result.get("document_id") == doc_id or
                                result.get("document", {}).get("doc_unique_id") == doc_id
                            )
                            
                            if is_match:
                                result["source_type"] = "shared"
                                result["source_name"] = f"shared:{doc_name}"
                                filtered_results.append(result)
                        
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
    
    # Apply threshold filtering only to agent results
    filtered_agent_results = [
        doc for doc in agent_results
        if doc.get("score", 0) >= MIN_SCORE_THRESHOLD
    ]
    
    # Combine results: shared documents (no threshold) + filtered agent results
    final_results = shared_results + filtered_agent_results
    
    # Sort final results by score and limit
    final_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    all_results = final_results[:top_k]
    
    logger.info(f"✅ Using {len([d for d in all_results if d.get('source_type') == 'shared'])} shared documents (no threshold)")
    logger.info(f"✅ Using {len([d for d in all_results if d.get('source_type') == 'agent'])} agent documents (threshold: {MIN_SCORE_THRESHOLD})")
    
    if not all_results:
        return {"response": "I couldn't find relevant information to answer your question.", "quality_scores": {}, "sources": []}
    
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

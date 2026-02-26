# -----------------------------
# Enhanced similarity search with shared knowledge support
# -----------------------------

import logging
import os
import numpy as np
from pymongo import MongoClient
from search.SimilaritySearch import (
    extract_core_question,
    embed_query,
    find_similar_chunks,
    find_similar_chunks_in_memory,
    get_llm_response_from_chunk,
    MIN_SCORE_THRESHOLD,
    TOP_K
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
# Enhanced search with shared knowledge
# -----------------------------
def retrieve_chunks_with_shared_knowledge(
    query: str,
    db_name: str = None,
    collection_name: str = None,
    subject_agent_id: str = None,
    embedding_model=None,
    student_profile: dict = None,
    top_k: int = TOP_K
) -> dict:
    """
    Enhanced retrieval that includes both agent-specific and shared knowledge documents.
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
    # Extract core question for embedding
    # -----------------------------
    core_question = extract_core_question(query)
    logger.info(f"Core question extracted for embedding: '{core_question[:100]}...' (full query length: {len(query)})")
    
    # Generate query embedding using core question only
    query_embedding = embed_query(core_question, embedding_model)

    # -----------------------------
    # Collect results from multiple sources
    # -----------------------------
    all_results = []
    sources_info = []

    # 1. Get agent-specific documents (if available)
    if db_name and collection_name:
        try:
            client = MongoClient(MONGODB_URI)
            
            if db_name in client.list_database_names() and collection_name in client[db_name].list_collection_names():
                agent_collection = client[db_name][collection_name]
                agent_results = find_similar_chunks(query_embedding, agent_collection, limit=top_k)
                
                # Mark results as agent-specific
                for result in agent_results:
                    result["source_type"] = "agent"
                    result["source_name"] = f"{db_name}.{collection_name}"
                
                all_results.extend(agent_results)
                sources_info.append({
                    "type": "agent",
                    "name": f"{db_name}.{collection_name}",
                    "results_count": len(agent_results)
                })
                
                logger.info(f"Retrieved {len(agent_results)} chunks from agent collection {db_name}.{collection_name}")
        
        except Exception as e:
            logger.error(f"Failed to search agent collection: {e}")

    # 2. Get shared knowledge documents (if agent has enabled any AND global RAG is enabled for this agent)
    if subject_agent_id:
        try:
            # First, get agent metadata to check if global RAG is enabled
            agent_global_rag_enabled = False
            try:
                from Teacher_AI_Agent.dbFun.get_agent_data import get_agent_data
                agent_data = get_agent_data(subject_agent_id)
                agent_metadata = agent_data.get("agent_metadata", {})
                agent_global_rag_enabled = agent_metadata.get("global_rag_enabled", False)
                logger.info(f"Agent {subject_agent_id} global RAG enabled: {agent_global_rag_enabled}")
            except Exception as e:
                logger.warning(f"Failed to get agent metadata for {subject_agent_id}: {e}")
                agent_global_rag_enabled = False
            
            # Only proceed with shared knowledge if agent has global RAG enabled
            if agent_global_rag_enabled:
                enabled_shared_docs = shared_knowledge_manager.get_agent_enabled_documents(subject_agent_id)
                logger.info(f"Found {len(enabled_shared_docs)} enabled shared documents for agent {subject_agent_id}")
                
                if enabled_shared_docs:
                    client = MongoClient(MONGODB_URI)
                    shared_collection = client["teacher_ai"]["shared_knowledge"]
                    
                    for shared_doc in enabled_shared_docs:
                        try:
                            doc_id = shared_doc["document_id"]
                            doc_name = shared_doc["document_name"]
                            logger.info(f"Searching in shared document: {doc_name} (ID: {doc_id})")
                            
                            # Search within this shared document
                            logger.info(f"Performing vector search on shared collection 'teacher_ai.shared_knowledge'")
                            shared_results = find_similar_chunks(
                                query_embedding, 
                                shared_collection, 
                                limit=top_k // len(enabled_shared_docs) if enabled_shared_docs else top_k
                            )
                        
                            logger.info(f"Found {len(shared_results)} total chunks in shared collection before filtering")
                        
                        # Debug: Check if collection has any documents at all
                            total_docs = shared_collection.count_documents({})
                            logger.info(f"Shared collection has {total_docs} total documents")
                            
                            # Debug: Check if documents have embeddings
                            docs_with_embeddings = shared_collection.count_documents({"embedding.vector": {"$exists": True}})
                            logger.info(f"Shared collection has {docs_with_embeddings} documents with embeddings")
                            
                            # Debug: Sample one document to see its structure
                            sample_doc = shared_collection.find_one()
                            if sample_doc:
                                logger.debug(f"Sample shared document keys: {list(sample_doc.keys())}")
                                if "subject_agent_id" in sample_doc:
                                    logger.debug(f"Sample subject_agent_id: {sample_doc['subject_agent_id']}")
                            
                            # Debug: Log first few results if any
                            if shared_results:
                                logger.debug(f"First shared result keys: {list(shared_results[0].keys()) if shared_results else 'None'}")
                                for i, result in enumerate(shared_results[:2]):
                                    logger.debug(f"Shared result {i}: subject_agent_id={result.get('subject_agent_id')}, score={result.get('score')}")
                            
                            # Filter results to only include chunks from this document
                            # Check multiple possible ID fields that might be in the chunk
                            filtered_shared_results = []
                            for result in shared_results:
                                # Log the chunk structure for debugging
                                chunk_debug = {
                                    "subject_agent_id": result.get("subject_agent_id", ""),
                                    "document_id": result.get("document_id", ""),
                                    "doc_unique_id": result.get("document", {}).get("doc_unique_id", "")
                                }
                                logger.debug(f"Chunk debug info: {chunk_debug}")
                                
                                # Check if this chunk belongs to the current shared document
                                is_match = (
                                    result.get("subject_agent_id", "") == doc_id or
                                    result.get("document_id", "") == doc_id or
                                    result.get("document", {}).get("doc_unique_id", "") == doc_id
                                )
                                
                                logger.debug(f"Is match: {is_match}")
                                
                                if is_match:
                                    result["source_type"] = "shared"
                                    result["source_name"] = doc_name
                                    result["document_id"] = doc_id
                                    filtered_shared_results.append(result)
                            
                            all_results.extend(filtered_shared_results)
                            sources_info.append({
                                "type": "shared",
                                "name": doc_name,
                                "document_id": doc_id,
                                "results_count": len(filtered_shared_results)
                            })
                            
                            logger.info(f"Retrieved {len(filtered_shared_results)} chunks from shared document '{doc_name}' (filtered from {len(shared_results)} total)")
                        
                        except Exception as e:
                            logger.error(f"Failed to search shared document {shared_doc['document_name']}: {e}")
                            import traceback
                            logger.error(f"Search error traceback: {traceback.format_exc()}")
        
        except Exception as e:
            logger.error(f"Failed to get enabled shared documents: {e}")

    # -----------------------------
    # If no results from any source
    # -----------------------------
    if not all_results:
        logger.warning("No chunks retrieved from any source (agent or shared knowledge).")
        safe_msg = (
            "I'm not able to find relevant content in the available learning materials. "
            "Please try asking your question in a different way or consult your teacher."
        )
        quality_scores = compute_quality_scores(
            query=query,
            response_text=safe_msg,
            retrieved_chunks=[],
            context_string="",
        )
        return {"response": safe_msg, "quality_scores": quality_scores, "sources": []}

    # -----------------------------
    # Sort and filter results
    # -----------------------------
    # Sort by score (descending)
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # Filter by similarity threshold
    filtered_results = [
        doc for doc in all_results
        if doc.get("score", 0) >= MIN_SCORE_THRESHOLD
    ]

    if not filtered_results:
        logger.warning(
            f"No chunks passed MIN_SCORE_THRESHOLD={MIN_SCORE_THRESHOLD}. "
            "Not calling LLM without RAG context."
        )
        safe_msg = (
            "I'm not able to find relevant content in the learning materials for this question. "
            "Please try asking it in a different way or consult your teacher."
        )
        quality_scores = compute_quality_scores(
            query=query,
            response_text=safe_msg,
            retrieved_chunks=[],
            context_string="",
        )
        return {"response": safe_msg, "quality_scores": quality_scores, "sources": sources_info}

    # -----------------------------
    # Prioritize agent-specific results over shared ones
    # -----------------------------
    # Separate agent and shared results
    agent_results = [doc for doc in filtered_results if doc.get("source_type") == "agent"]
    shared_results = [doc for doc in filtered_results if doc.get("source_type") == "shared"]
    
    # Take top results, prioritizing agent-specific content
    # If we have agent results, take up to 70% from agent, 30% from shared
    # If no agent results, take all from shared
    if agent_results:
        agent_count = min(int(top_k * 0.7), len(agent_results))
        shared_count = min(top_k - agent_count, len(shared_results))
        final_results = agent_results[:agent_count] + shared_results[:shared_count]
    else:
        final_results = shared_results[:top_k]

    # -----------------------------
    # Log accepted chunks
    # -----------------------------
    logger.info("=" * 80)
    logger.info(f"✅ Final chunks accepted for LLM (total: {len(final_results)}):")
    logger.info("=" * 80)
    for idx, doc in enumerate(final_results):
        source_type = doc.get("source_type", "unknown")
        source_name = doc.get("source_name", "unknown")
        logger.info(
            f"[FINAL {idx + 1}] Score: {doc['score']:.4f}, "
            f"Source: {source_type.upper()} - {source_name}, "
            f"Chunk ID: {doc.get('unique_chunk_id')}"
        )

    # -----------------------------
    # Build combined result string
    # -----------------------------
    result_string = "\n---\n".join(doc["chunk_text"] for doc in final_results)
    logger.info(f"Combined context string length: {len(result_string)} chars")

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
        retrieved_chunks=final_results,
        context_string=result_string,
    )

    # -----------------------------
    # Prepare sources information for response
    # -----------------------------
    final_sources = []
    for doc in final_results:
        final_sources.append({
            "chunk_id": doc.get("unique_chunk_id"),
            "source_type": doc.get("source_type"),
            "source_name": doc.get("source_name"),
            "score": doc.get("score"),
            "document_id": doc.get("document_id") if doc.get("source_type") == "shared" else None
        })

    return {
        "response": response_text, 
        "quality_scores": quality_scores,
        "sources": final_sources,
        "source_summary": sources_info
    }

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
    top_k: int = TOP_K
) -> dict:
    """
    Enhanced version of retrieve_chunk_for_query_send_to_llm that includes shared knowledge.
    Falls back to original behavior if no shared documents are enabled.
    """
    
    # If no subject_agent_id, use original search
    if not subject_agent_id:
        from search.SimilaritySearch import retrieve_chunk_for_query_send_to_llm
        return retrieve_chunk_for_query_send_to_llm(
            query=query,
            db_name=db_name,
            collection_name=collection_name,
            embedding_model=embedding_model,
            student_profile=student_profile,
            top_k=top_k
        )
    
    # Use enhanced search with shared knowledge
    return retrieve_chunks_with_shared_knowledge(
        query=query,
        db_name=db_name,
        collection_name=collection_name,
        subject_agent_id=subject_agent_id,
        embedding_model=embedding_model,
        student_profile=student_profile,
        top_k=top_k
    )

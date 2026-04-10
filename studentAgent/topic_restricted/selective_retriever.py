"""
Selective Context Retriever

Performs in-memory similarity search against topic metadata.
Fetches only the most relevant full chunks for each query.
Zero database calls during chat - everything from pre-loaded cache.
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

try:
    import numpy as np
    from scipy.spatial.distance import cosine
except ImportError:
    np = None
    cosine = None

logger = logging.getLogger(__name__)


class SelectiveContextRetriever:
    """
    Performs in-memory similarity search against topic metadata.
    Fetches only the most relevant full chunks for each query.
    """
    
    def __init__(
        self,
        redis_client=None,
        embedding_model=None,
        default_top_k: int = 5,
        similarity_threshold: float = 0.3,
        use_memory_fallback: bool = True,
        max_context_tokens: int = 6000,
        tokens_per_chunk_estimate: int = 150
    ):
        self.redis = redis_client
        self.embedding_model = embedding_model
        self.default_top_k = default_top_k
        self.similarity_threshold = similarity_threshold
        self.use_memory_fallback = use_memory_fallback
        self.max_context_tokens = max_context_tokens
        self.tokens_per_chunk_estimate = tokens_per_chunk_estimate
        self._embedding_cache: Dict[str, List[float]] = {}
    
    async def retrieve_context(
        self,
        query: str,
        session_state: Dict[str, Any],
        top_k: Optional[int] = None,
        use_all_chunks: bool = False,
        respect_token_budget: bool = True
    ) -> Tuple[str, List[str], Dict[str, Any]]:
        """
        Retrieve relevant context for a query from pre-loaded topic.
        
        Args:
            query: Student's question
            session_state: Current session with topic_metadata
            top_k: Number of chunks to retrieve (default: self.default_top_k)
            use_all_chunks: If True, return all chunks sorted by relevance (respecting token_budget)
            respect_token_budget: If True and use_all_chunks, limit by max_context_tokens
            
        Returns:
            (context_string, selected_chunk_ids, retrieval_info)
        """
        k = top_k or self.default_top_k
        metadata_index = session_state.get('topic_metadata', [])
        
        # If use_all_chunks is True, set k to all chunks
        if use_all_chunks:
            k = len(metadata_index)
        
        if not metadata_index:
            logger.warning("No metadata index in session state")
            return (
                "",
                [],
                {
                    "status": "no_metadata",
                    "message": "No topic metadata available",
                    "highest_score": 0
                }
            )
        
        try:
            # Step 1: Embed the query (with caching)
            query_embedding = await self._get_query_embedding(query)
            
            if query_embedding is None:
                logger.error("Failed to generate query embedding")
                return (
                    "",
                    [],
                    {
                        "status": "embedding_failed",
                        "message": "Failed to embed query",
                        "highest_score": 0
                    }
                )
            
            # Step 2: Score all metadata entries (in-memory, no DB call)
            scored_chunks = self._score_chunks(query_embedding, metadata_index)
            
            # Step 3: Sort by score
            scored_chunks.sort(key=lambda x: x['score'], reverse=True)
            
            # Step 4: Filter by threshold
            filtered_chunks = [
                c for c in scored_chunks
                if c['score'] >= self.similarity_threshold
            ]
            
            if not filtered_chunks:
                highest_score = scored_chunks[0]['score'] if scored_chunks else 0
                logger.warning(f"No chunks passed similarity threshold {self.similarity_threshold}. Highest: {highest_score:.4f}")
                
                return (
                    "",
                    [],
                    {
                        "status": "no_relevant_chunks",
                        "message": f"No chunks met similarity threshold {self.similarity_threshold}",
                        "highest_score": highest_score,
                        "total_scored": len(scored_chunks)
                    }
                )
            
            # Step 5: Select chunks
            if use_all_chunks and respect_token_budget:
                # Select all chunks that fit within token budget, sorted by relevance
                selected, excluded_count = self._select_chunks_within_budget(
                    filtered_chunks, self.max_context_tokens
                )
                selected_ids = [c['chunk_id'] for c in selected]
                logger.info(
                    f"Selected {len(selected_ids)} chunks within {self.max_context_tokens} token budget, "
                    f"excluded {excluded_count} chunks"
                )
            else:
                selected = filtered_chunks[:k]
                selected_ids = [c['chunk_id'] for c in selected]
                logger.info(f"Selected {len(selected_ids)} chunks with scores: {[c['score'] for c in selected]}")
            
            # Step 6: Fetch full content from cache
            full_chunks = await self._get_full_chunks(
                session_state.get('full_chunks_cache_key', ''),
                selected_ids,
                session_state
            )
            
            # Step 7: Build context string
            context_string = self._build_context_string(selected_ids, full_chunks)
            
            total_tokens = sum(c.get('token_count', 0) for c in selected)
            
            retrieval_info = {
                "status": "success",
                "chunks_selected": len(selected_ids),
                "chunk_ids": selected_ids,
                "scores": {c['chunk_id']: round(c['score'], 4) for c in selected},
                "total_tokens": total_tokens,
                "threshold": self.similarity_threshold,
                "highest_score": selected[0]['score'] if selected else 0,
                "use_all_chunks": use_all_chunks,
                "token_budget_used": f"{total_tokens}/{self.max_context_tokens}" if use_all_chunks else None
            }
            
            return context_string, selected_ids, retrieval_info
            
        except Exception as e:
            logger.error(f"Error retrieving context: {e}", exc_info=True)
            return (
                "",
                [],
                {
                    "status": "error",
                    "message": str(e),
                    "highest_score": 0
                }
            )
    
    async def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        """Generate embedding for query with caching."""
        # Normalize query for cache key
        cache_key = query.lower().strip()
        
        # Check cache
        if cache_key in self._embedding_cache:
            logger.debug(f"Using cached embedding for query: {query[:50]}...")
            return self._embedding_cache[cache_key]
        
        # Generate new embedding
        if self.embedding_model is None:
            logger.error("No embedding model available")
            return None
        
        try:
            # Handle both sync and async embedding models
            if hasattr(self.embedding_model, 'embed_query'):
                embedding = self.embedding_model.embed_query(query)
            elif hasattr(self.embedding_model, 'aembed_query'):
                embedding = await self.embedding_model.aembed_query(query)
            else:
                logger.error("Embedding model has no embed_query method")
                return None
            
            # Cache the embedding
            self._embedding_cache[cache_key] = embedding
            
            # Limit cache size (LRU-like behavior)
            if len(self._embedding_cache) > 1000:
                # Remove oldest entries
                keys_to_remove = list(self._embedding_cache.keys())[:100]
                for key in keys_to_remove:
                    del self._embedding_cache[key]
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
    
    def _score_chunks(
        self,
        query_embedding: List[float],
        metadata_index: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Score all chunks against query embedding using cosine similarity.
        Pure in-memory operation, no DB calls.
        """
        scored = []
        
        query_vec = np.array(query_embedding) if np else query_embedding
        
        for meta in metadata_index:
            chunk_id = meta.get('chunk_id')
            chunk_embedding = meta.get('embedding')
            
            if not chunk_embedding or not chunk_id:
                continue
            
            try:
                # Calculate cosine similarity
                if np and cosine:
                    chunk_vec = np.array(chunk_embedding)
                    # Cosine similarity = 1 - cosine distance
                    similarity = 1 - cosine(query_vec, chunk_vec)
                else:
                    # Fallback: simple dot product for normalized vectors
                    similarity = self._simple_similarity(query_embedding, chunk_embedding)
                
                scored.append({
                    "chunk_id": chunk_id,
                    "score": float(similarity),
                    "preview": meta.get('preview', ''),
                    "key_terms": meta.get('key_terms', []),
                    "token_count": meta.get('token_count', 0),
                    "source_file": meta.get('source_file', ''),
                    "page_number": meta.get('page_number', 0)
                })
                
            except Exception as e:
                logger.warning(f"Error scoring chunk {chunk_id}: {e}")
                continue
        
        return scored
    
    def _simple_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Simple dot product similarity for normalized vectors."""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Normalize
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    async def _get_full_chunks(
        self,
        cache_key: str,
        chunk_ids: List[str],
        session_state: Dict = None
    ) -> Dict[str, Any]:
        """Fetch full chunk content from cache or session."""
        if not cache_key or not chunk_ids:
            return {}
        
        try:
            # Try Redis first
            if self.redis:
                cached_data = None
                try:
                    if hasattr(self.redis, 'get'):
                        cached_data = self.redis.get(cache_key)
                    else:
                        cached_data = await self.redis.get(cache_key)
                except Exception as e:
                    logger.warning(f"Redis get failed: {e}")
                
                if cached_data:
                    all_chunks = json.loads(cached_data)
                    return {cid: all_chunks.get(cid, {}) for cid in chunk_ids}
            
            # Fallback: check if chunks are in session state (for memory cache sharing)
            if session_state and 'full_chunks' in session_state:
                all_chunks = session_state['full_chunks']
                return {cid: all_chunks.get(cid, {}) for cid in chunk_ids}
            
            logger.warning(f"Cannot retrieve full chunks - no cache available for key: {cache_key}")
            return {}
            
        except Exception as e:
            logger.error(f"Error retrieving full chunks: {e}")
            return {}
    
    def _build_context_string(
        self,
        selected_ids: List[str],
        full_chunks: Dict[str, Any]
    ) -> str:
        """Build context string from selected chunks."""
        context_parts = []
        
        for i, chunk_id in enumerate(selected_ids, 1):
            chunk_data = full_chunks.get(chunk_id, {})
            chunk_text = chunk_data.get('text', '')
            source = chunk_data.get('source', {})
            
            if not chunk_text:
                logger.warning(f"No text found for chunk {chunk_id}")
                continue
            
            source_file = source.get('file_name', 'Unknown')
            page_number = source.get('page_number', 'N/A')
            
            context_parts.append(
                f"[Context {i}] Source: {source_file}, Page: {page_number}\n"
                f"{chunk_text}\n"
            )
        
        return "\n---\n".join(context_parts) if context_parts else ""
    
    def _select_chunks_within_budget(
        self,
        scored_chunks: List[Dict[str, Any]],
        max_tokens: int
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Select chunks that fit within token budget, prioritizing by relevance score.
        
        Args:
            scored_chunks: List of chunks sorted by score (highest first)
            max_tokens: Maximum tokens allowed
            
        Returns:
            (selected_chunks, excluded_count)
        """
        selected = []
        current_tokens = 0
        
        for chunk in scored_chunks:
            chunk_tokens = chunk.get('token_count', self.tokens_per_chunk_estimate)
            
            # Check if adding this chunk would exceed budget
            if current_tokens + chunk_tokens > max_tokens and selected:
                # We've already selected some chunks and this one would exceed budget
                break
            
            selected.append(chunk)
            current_tokens += chunk_tokens
            
            # Safety check: if single chunk exceeds budget, still include it but log warning
            if current_tokens > max_tokens and len(selected) == 1:
                logger.warning(
                    f"Single chunk {chunk['chunk_id']} exceeds token budget "
                    f"({chunk_tokens} > {max_tokens})"
                )
        
        excluded_count = len(scored_chunks) - len(selected)
        
        return selected, excluded_count
    
    def clear_embedding_cache(self):
        """Clear the embedding cache."""
        self._embedding_cache.clear()
        logger.info("Embedding cache cleared")

"""
Topic Context Loader

Loads all chunks for a topic at session initialization.
Separates metadata (lightweight, in-memory) from full content (cached).
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from pymongo import MongoClient
    from pymongo.server_api import ServerApi
except ImportError:
    MongoClient = None

try:
    import numpy as np
except ImportError:
    np = None

logger = logging.getLogger(__name__)


class TopicContextLoader:
    """
    Loads all chunks for a topic at session initialization.
    Separates metadata (lightweight, in-memory) from full content (cached).
    """
    
    def __init__(
        self,
        mongo_uri: str = None,
        redis_client=None,
        embedding_model=None,
        use_memory_fallback: bool = True
    ):
        self.mongo_uri = mongo_uri or os.environ.get("MONGODB_URI")
        self.redis = redis_client
        self.embedding_model = embedding_model
        self.use_memory_fallback = use_memory_fallback
        self._mongo_client = None
        self._memory_cache: Dict[str, Any] = {}
        
        # Initialize MongoDB connection
        if MongoClient and self.mongo_uri:
            try:
                self._mongo_client = MongoClient(
                    self.mongo_uri,
                    server_api=ServerApi('1')
                )
                logger.info("Connected to MongoDB Atlas")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                self._mongo_client = None
    
    async def load_topic_context(
        self,
        topic_id: str,
        subject_agent_id: str,
        db_name: str,
        collection_name: str
    ) -> Dict[str, Any]:
        """
        Load all chunks for a topic into session cache.
        
        Args:
            topic_id: Unique identifier for the topic
            subject_agent_id: Parent subject agent identifier
            db_name: Database name (class/grade)
            collection_name: Collection name (subject)
            
        Returns:
            {
                'metadata_index': [...],  # All chunk metadata with embeddings
                'cache_key': 'chunks:...',  # Redis/memory key for full chunks
                'stats': {...}              # Context statistics
            }
        """
        if not self._mongo_client:
            raise ValueError("MongoDB client not initialized")
        
        try:
            collection = self._mongo_client[db_name][collection_name]
            
            # If subject_agent_id is empty, look it up from existing documents
            if not subject_agent_id:
                try:
                    logger.info(f"Attempting DB lookup: db={db_name}, collection={collection_name}")
                    # Get ANY document to find the subject_agent_id format used
                    any_doc = collection.find_one()
                    logger.info(f"Any doc result: {any_doc is not None}")
                    if any_doc:
                        logger.info(f"Doc keys: {list(any_doc.keys())}")
                        if "subject_agent_id" in any_doc:
                            subject_agent_id = any_doc["subject_agent_id"]
                            logger.info(f"Found subject_agent_id from DB: {subject_agent_id}")
                        else:
                            logger.warning(f"No subject_agent_id field in document")
                    else:
                        logger.warning(f"No documents found in {db_name}.{collection_name}")
                except Exception as e:
                    logger.error(f"Could not lookup subject_agent_id: {e}", exc_info=True)
            
            # Query all chunks for this topic
            query = {"subject_agent_id": subject_agent_id}
            
            # If topic_id is specified and chunks have topic tagging
            if topic_id and topic_id != "all":
                query["$or"] = [
                    {"topic_id": topic_id},
                    {"tags": topic_id},
                    {"chunk.topic_id": topic_id}
                ]
            
            projection = {
                "chunk.unique_chunk_id": 1,
                "chunk.text": 1,
                "embedding.vector": 1,  # Root level embedding
                "chunk.metadata": 1,
                "document.file_name": 1,
                "document.page_number": 1,
                "tags": 1,
                "topic_id": 1
            }
            
            logger.info(f"Querying MongoDB: {db_name}.{collection_name} for topic {topic_id}")
            chunks = list(collection.find(query, projection))
            
            if not chunks:
                # Fallback: use all chunks for this subject agent
                logger.warning(f"No chunks with topic filter for '{topic_id}', using all chunks for subject {subject_agent_id}")
                query = {"subject_agent_id": subject_agent_id}
                chunks = list(collection.find(query, projection))
                
                if not chunks:
                    # Try without subject_agent_id filter (get all chunks in collection)
                    logger.warning(f"No chunks with subject_agent_id={subject_agent_id}, trying all documents")
                    chunks = list(collection.find({}, projection))
                    if chunks:
                        logger.info(f"Found {len(chunks)} chunks without subject_agent_id filter")
                
                if not chunks:
                    raise ValueError(f"No chunks found in {db_name}.{collection_name}")
                
                logger.info(f"Using {len(chunks)} chunks (no topic filtering)")
            
            logger.info(f"Retrieved {len(chunks)} chunks for topic {topic_id}")
            
            # Build metadata index and full chunks
            metadata_index = []
            full_chunks = {}
            total_tokens = 0
            
            for chunk in chunks:
                chunk_data = chunk.get('chunk', {})
                doc_data = chunk.get('document', {})
                
                chunk_id = chunk_data.get('unique_chunk_id') or f"chunk_{len(full_chunks)}"
                chunk_text = chunk_data.get('text', '')
                metadata = chunk_data.get('metadata', {})
                
                # Build embedding array - embedding is at ROOT level of document
                embedding_vector = None
                # Check root level embedding first
                if chunk.get('embedding') and chunk['embedding'].get('vector'):
                    embedding_vector = chunk['embedding']['vector']
                # Also check inside chunk (for backward compatibility)
                elif chunk_data.get('embedding') and chunk_data['embedding'].get('vector'):
                    embedding_vector = chunk_data['embedding']['vector']
                
                # Add to metadata index (lightweight)
                metadata_index.append({
                    "chunk_id": chunk_id,
                    "preview": chunk_text[:200] if chunk_text else "",
                    "embedding": embedding_vector,
                    "source_file": doc_data.get('file_name', ''),
                    "page_number": doc_data.get('page_number', 0),
                    "key_terms": metadata.get('key_terms', []) if metadata else [],
                    "token_count": metadata.get('token_count', len(chunk_text.split())) if chunk_text else 0,
                    "difficulty": metadata.get('difficulty_level', 'unknown') if metadata else 'unknown',
                    "tags": chunk.get('tags', [])
                })
                
                # Store full content
                full_chunks[chunk_id] = {
                    "text": chunk_text,
                    "metadata": metadata or {},
                    "source": doc_data,
                    "topic_id": chunk.get('topic_id', topic_id)
                }
                
                if metadata and metadata.get('token_count'):
                    total_tokens += metadata['token_count']
                elif chunk_text:
                    total_tokens += len(chunk_text.split())
            
            # Store full chunks in cache
            cache_key = f"chunks:sess_{topic_id}_{int(datetime.utcnow().timestamp())}"
            cache_data = json.dumps(full_chunks, default=str)
            
            if self.redis:
                try:
                    if hasattr(self.redis, 'setex'):
                        # Synchronous redis
                        self.redis.setex(cache_key, 3600, cache_data)  # 1 hour TTL
                    else:
                        # Async redis
                        await self.redis.setex(cache_key, 3600, cache_data)
                    logger.info(f"Full chunks cached in Redis: {cache_key}")
                except Exception as e:
                    logger.warning(f"Failed to cache in Redis: {e}, using memory fallback")
                    self._memory_cache[cache_key] = full_chunks
            elif self.use_memory_fallback:
                self._memory_cache[cache_key] = full_chunks
                logger.info(f"Full chunks cached in memory: {cache_key}")
            
            # Calculate statistics
            sources = list(set(m['source_file'] for m in metadata_index if m['source_file']))
            stats = {
                "total_chunks": len(chunks),
                "total_tokens": total_tokens,
                "estimated_context_window": f"{(total_tokens / 8000) * 100:.1f}%",  # Assuming 8K context
                "sources": sources,
                "loaded_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Context stats: {stats}")
            
            return {
                "metadata_index": metadata_index,
                "cache_key": cache_key,
                "stats": stats,
                "full_chunks": full_chunks  # Return full chunks for session storage
            }
            
        except Exception as e:
            logger.error(f"Error loading topic context: {e}", exc_info=True)
            raise
    
    async def get_full_chunks(self, cache_key: str, chunk_ids: List[str]) -> Dict[str, Any]:
        """Fetch full chunk content from cache."""
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
            
            # Fallback to memory
            if self.use_memory_fallback and cache_key in self._memory_cache:
                all_chunks = self._memory_cache[cache_key]
                return {cid: all_chunks.get(cid, {}) for cid in chunk_ids}
            
            return {}
            
        except Exception as e:
            logger.error(f"Error retrieving full chunks: {e}")
            return {}
    
    def close(self):
        """Close database connections."""
        if self._mongo_client:
            self._mongo_client.close()
            logger.info("MongoDB connection closed")

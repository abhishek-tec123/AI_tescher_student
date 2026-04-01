"""
Topic Session Manager

Manages topic-restricted chat sessions with Redis-backed state storage.
Handles session lifecycle, topic context loading, and conversation history.
"""

import json
import hashlib
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger(__name__)


class TopicSessionManager:
    """
    Manages topic-restricted chat sessions.
    Handles session lifecycle, state storage, and context loading.
    """
    
    def __init__(
        self,
        redis_client=None,
        context_loader=None,
        session_ttl: int = 1800,  # 30 minutes
        use_memory_fallback: bool = True
    ):
        self.redis = redis_client
        self.context_loader = context_loader
        self.session_ttl = session_ttl
        self.use_memory_fallback = use_memory_fallback
        self._memory_store: Dict[str, Dict] = {}  # Fallback if Redis not available
        
        if redis is None:
            logger.warning("Redis not available, using in-memory fallback")
            self.redis = None
        elif self.redis is None:
            try:
                self.redis = redis.from_url("redis://localhost:6379/0")
                logger.info("Connected to Redis")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}, using in-memory fallback")
                self.redis = None
    
    async def create_session(
        self,
        student_id: str,
        class_name: str,
        subject: str,
        topic_id: str,
        student_profile: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Initialize a new topic-restricted chat session.
        
        1. Validate topic exists
        2. Load all topic chunks into session cache
        3. Build metadata index in memory
        4. Return session configuration
        
        Returns:
            {
                "session_id": str,
                "topic": Dict,
                "context_stats": Dict,
                "message": str
            }
        """
        session_id = self._generate_session_id(student_id, topic_id)
        
        try:
            # Step 1: Validate topic and get definition
            topic_def = await self._get_topic_definition(topic_id, class_name, subject)
            if not topic_def:
                return {
                    "error": f"Topic {topic_id} not found",
                    "session_id": None
                }
            
            # Step 2: Load topic context using context loader
            if self.context_loader is None:
                raise ValueError("Context loader not configured")
            
            context_data = await self.context_loader.load_topic_context(
                topic_id=topic_id,
                subject_agent_id=topic_def.get('subject_agent_id', ''),
                db_name=class_name,
                collection_name=subject
            )
            
            # Step 3: Build session state
            session_state = {
                "session_id": session_id,
                "student_id": student_id,
                "class_name": class_name,
                "subject": subject,
                "topic": {
                    "topic_id": topic_id,
                    "topic_name": topic_def.get('topic_name', topic_id),
                    "description": topic_def.get('description', '')
                },
                "topic_metadata": context_data.get('metadata_index', []),
                "full_chunks_cache_key": context_data.get('cache_key', ''),
                "full_chunks": context_data.get('full_chunks', {}),  # Store chunks in session
                "context_stats": context_data.get('stats', {}),
                "student_profile": student_profile or {},
                "conversation_history": [],
                "created_at": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat(),
                "config": {
                    "strict_mode": True,
                    "allow_off_topic": False,
                    "max_context_chunks": 5
                }
            }
            
            # Step 4: Store session
            await self._save_session(session_id, session_state)
            
            logger.info(
                f"Session initialized: {session_id} "
                f"for topic: {session_state['topic']['topic_name']}"
            )
            
            return {
                "session_id": session_id,
                "topic": session_state['topic'],
                "context_stats": session_state['context_stats'],
                "message": f"Session initialized for topic: {session_state['topic']['topic_name']}"
            }
            
        except Exception as e:
            logger.error(f"Session initialization failed: {e}", exc_info=True)
            return {
                "error": str(e),
                "session_id": None
            }
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session state from cache."""
        try:
            if self.redis:
                session_data = await self._async_redis_get(f"session:{session_id}")
                if session_data:
                    return json.loads(session_data)
            elif self.use_memory_fallback:
                return self._memory_store.get(session_id)
            return None
        except Exception as e:
            logger.error(f"Error retrieving session: {e}")
            return self._memory_store.get(session_id) if self.use_memory_fallback else None
    
    async def update_session(
        self,
        session_id: str,
        user_message: Dict[str, Any],
        assistant_message: Dict[str, Any],
        selected_chunks: List[str]
    ):
        """Update session with new message and chunk usage."""
        try:
            session = await self.get_session(session_id)
            if not session:
                raise ValueError("Session not found")
            
            # Add to conversation history
            session['conversation_history'].append({
                "role": "user",
                "content": user_message.get('content', ''),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            session['conversation_history'].append({
                "role": "assistant",
                "content": assistant_message.get('content', ''),
                "selected_chunks": selected_chunks,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Update activity timestamp
            session['last_activity'] = datetime.utcnow().isoformat()
            
            # Save back
            await self._save_session(session_id, session)
            
        except Exception as e:
            logger.error(f"Error updating session: {e}")
    
    async def end_session(self, session_id: str) -> bool:
        """Terminate session and clean up resources."""
        try:
            session = await self.get_session(session_id)
            if not session:
                return False
            
            # Clean up full chunks cache
            cache_key = session.get('full_chunks_cache_key')
            if cache_key:
                if self.redis:
                    await self._async_redis_delete(cache_key)
                elif self.use_memory_fallback and cache_key in self._memory_store:
                    del self._memory_store[cache_key]
            
            # Delete session
            if self.redis:
                await self._async_redis_delete(f"session:{session_id}")
            elif self.use_memory_fallback and session_id in self._memory_store:
                del self._memory_store[session_id]
            
            logger.info(f"Session ended: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            return False
    
    async def _get_topic_definition(self, topic_id: str, class_name: str = "", subject: str = "") -> Optional[Dict]:
        """Fetch topic definition and determine subject_agent_id from existing data."""
        subject_agent_id = ""
        
        # Try to find the actual subject_agent_id from existing chunks
        if self.context_loader and class_name and subject:
            try:
                # Use the context_loader's mongo client
                mongo_client = getattr(self.context_loader, '_mongo_client', None)
                if mongo_client:
                    collection = mongo_client[class_name][subject]
                    # Get one document to extract the subject_agent_id
                    sample = collection.find_one({}, {"subject_agent_id": 1})
                    logger.info(f"DB lookup sample: {sample}")
                    if sample and sample.get("subject_agent_id"):
                        subject_agent_id = sample["subject_agent_id"]
                        logger.info(f"Found subject_agent_id from DB: {subject_agent_id}")
                    else:
                        logger.warning(f"No subject_agent_id found in DB sample")
                else:
                    logger.warning("MongoDB client not available for lookup")
            except Exception as e:
                logger.error(f"Could not lookup subject_agent_id: {e}", exc_info=True)
        
        # Fallback: construct from class and subject
        if not subject_agent_id:
            subject_agent_id = f"agent_{class_name}_{subject}" if class_name and subject else ""
            logger.warning(f"Using constructed subject_agent_id: {subject_agent_id}")
        
        return {
            "topic_id": topic_id,
            "topic_name": topic_id.replace("topic_", "").replace("_", " ").title(),
            "subject_agent_id": subject_agent_id,
            "description": ""
        }
    
    def _generate_session_id(self, student_id: str, topic_id: str) -> str:
        """Generate unique session ID."""
        hash_input = f"{student_id}:{topic_id}:{datetime.utcnow().timestamp()}"
        hash_suffix = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"sess_{student_id[:6]}_{hash_suffix}"
    
    async def _save_session(self, session_id: str, session_state: Dict):
        """Save session to storage with TTL."""
        session_data = json.dumps(session_state, default=str)
        
        if self.redis:
            await self._async_redis_setex(
                f"session:{session_id}",
                self.session_ttl,
                session_data
            )
        elif self.use_memory_fallback:
            self._memory_store[session_id] = session_state
            logger.debug(f"Session saved to memory: {session_id}")
    
    # Async Redis helper methods (for compatibility)
    async def _async_redis_get(self, key: str) -> Optional[str]:
        """Async wrapper for Redis get."""
        if hasattr(self.redis, 'get'):
            # Synchronous redis
            return self.redis.get(key)
        # Async redis
        return await self.redis.get(key)
    
    async def _async_redis_setex(self, key: str, ttl: int, value: str):
        """Async wrapper for Redis setex."""
        if hasattr(self.redis, 'setex'):
            # Synchronous redis
            self.redis.setex(key, ttl, value)
        else:
            # Async redis
            await self.redis.setex(key, ttl, value)
    
    async def _async_redis_delete(self, key: str):
        """Async wrapper for Redis delete."""
        if hasattr(self.redis, 'delete'):
            # Synchronous redis
            self.redis.delete(key)
        else:
            # Async redis
            await self.redis.delete(key)

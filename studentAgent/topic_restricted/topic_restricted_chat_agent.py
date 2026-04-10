"""
Topic Restricted Chat Agent

Main orchestrator for topic-restricted chat.
Coordinates session management, context retrieval, and LLM calls.
Ensures strict topic boundaries and prevents cross-topic leakage.
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add parent directories to path for imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
_root_dir = os.path.dirname(_parent_dir)

if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

logger = logging.getLogger(__name__)


class TopicRestrictedChatAgent:
    """
    Main orchestrator for topic-restricted chat.
    Coordinates session management, context retrieval, and LLM calls.
    """
    
    def __init__(
        self,
        session_manager=None,
        retriever=None,
        llm_gateway=None,
        jailbreak_detector=None,
        max_context_chunks: int = 5,
        similarity_threshold: float = 0.3,
        use_full_context: bool = True,
        max_context_tokens: int = 6000
    ):
        self.session_manager = session_manager
        self.retriever = retriever
        self.llm_gateway = llm_gateway
        self.jailbreak_detector = jailbreak_detector
        self.max_context_chunks = max_context_chunks
        self.similarity_threshold = similarity_threshold
        self.use_full_context = use_full_context
        self.max_context_tokens = max_context_tokens
        self._embedding_model = None
        self._initialized = False
    
    async def initialize(
        self,
        mongo_uri: str = None,
        redis_client=None,
        embedding_model=None
    ):
        """
        Initialize the agent with all required components.
        
        Args:
            mongo_uri: MongoDB connection string
            redis_client: Redis client instance
            embedding_model: Pre-loaded embedding model
        """
        if self._initialized:
            return
        
        try:
            # Import components
            from .topic_session_manager import TopicSessionManager
            from .topic_context_loader import TopicContextLoader
            from .selective_retriever import SelectiveContextRetriever
            from .jailbreak_detector import JailbreakDetector
            
            # Initialize context loader if not provided
            if self.session_manager is None:
                context_loader = TopicContextLoader(
                    mongo_uri=mongo_uri,
                    redis_client=redis_client,
                    embedding_model=embedding_model
                )
                
                self.session_manager = TopicSessionManager(
                    redis_client=redis_client,
                    context_loader=context_loader,
                    session_ttl=1800
                )
            
            # Initialize retriever if not provided
            if self.retriever is None:
                self.retriever = SelectiveContextRetriever(
                    redis_client=redis_client,
                    embedding_model=embedding_model,
                    default_top_k=self.max_context_chunks,
                    similarity_threshold=self.similarity_threshold
                )
            
            # Initialize jailbreak detector if not provided
            if self.jailbreak_detector is None:
                from .jailbreak_detector import TopicBoundaryDetector
                self.jailbreak_detector = TopicBoundaryDetector(
                    strict_mode=True,
                    embedding_model=embedding_model,
                    similarity_threshold=0.25,
                    topic_centroid_similarity_threshold=0.20
                )
            
            # Store embedding model reference
            self._embedding_model = embedding_model
            
            self._initialized = True
            logger.info("TopicRestrictedChatAgent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize TopicRestrictedChatAgent: {e}", exc_info=True)
            raise
    
    async def initialize_session(
        self,
        student_id: str,
        class_name: str,
        subject: str,
        topic_id: str,
        student_profile: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Initialize a new topic-restricted chat session.
        
        Args:
            student_id: Unique student identifier
            class_name: Class/grade (e.g., '10th')
            subject: Subject name (e.g., 'Science')
            topic_id: Topic identifier
            student_profile: Optional student personalization data
            
        Returns:
            Session initialization result with session_id
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            result = await self.session_manager.create_session(
                student_id=student_id,
                class_name=class_name,
                subject=subject,
                topic_id=topic_id,
                student_profile=student_profile
            )
            
            if result.get('error'):
                logger.error(f"Session initialization failed: {result['error']}")
            else:
                logger.info(
                    f"Session initialized: {result['session_id']} "
                    f"for topic: {result.get('topic', {}).get('topic_name', 'Unknown')}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Session initialization error: {e}", exc_info=True)
            return {
                "error": str(e),
                "session_id": None
            }
    
    async def chat(
        self,
        session_id: str,
        query: str
    ) -> Dict[str, Any]:
        """
        Process a chat message within a topic-restricted session.
        """
        if not self._initialized:
            await self.initialize()
        
        # Step 1: Get session
        session = await self.session_manager.get_session(session_id)
        if not session:
            return {
                "error": "Session not found or expired",
                "response": "Your session has expired. Please start a new chat session.",
                "session_id": session_id
            }
        
        # Step 2: Semantic topic boundary check (replaces regex-based jailbreak detection)
        topic_metadata = session.get('topic_metadata', [])
        topic_name = session['topic'].get('topic_name', 'this topic')
        
        if self.jailbreak_detector and hasattr(self.jailbreak_detector, 'check_topic_boundary'):
            is_on_topic, confidence, reason, details = await self.jailbreak_detector.check_topic_boundary(
                query=query,
                topic_metadata=topic_metadata,
                topic_name=topic_name
            )
            
            if not is_on_topic:
                logger.warning(f"Off-topic query detected: {reason} (confidence: {confidence:.2f})")
                off_topic_msg = (
                    f"I can only answer questions about {topic_name} "
                    f"based on your study materials. This question appears to be outside "
                    f"the scope of the current topic. Please ask a question related to {topic_name}."
                )
                await self.session_manager.update_session(
                    session_id=session_id,
                    user_message={"content": query},
                    assistant_message={"content": off_topic_msg},
                    selected_chunks=[]
                )
                return {
                    "response": off_topic_msg,
                    "context_used": False,
                    "off_topic": True,
                    "session_id": session_id,
                    "safety_flag": False,
                    "topic_confidence": confidence,
                    "topic_check_details": details
                }
        else:
            # Fallback to legacy jailbreak detection
            is_jailbreak, reason, details = self.jailbreak_detector.detect(query)
            if is_jailbreak:
                logger.warning(f"Jailbreak attempt detected: {reason}")
                return {
                    "response": "I'm not able to process this request. Please ask a question related to your current study topic.",
                    "context_used": False,
                    "off_topic": True,
                    "session_id": session_id,
                    "safety_flag": True
                }
        
        try:
            # Step 3: Retrieve relevant context (use full context mode if enabled)
            context_string, selected_chunks, retrieval_info = await self.retriever.retrieve_context(
                query=query,
                session_state=session,
                top_k=self.max_context_chunks,
                use_all_chunks=self.use_full_context,
                respect_token_budget=True
            )
            
            # Check if context retrieval failed
            if retrieval_info.get('status') == 'embedding_failed':
                error_msg = f"I can only answer questions about {topic_name} based on your study materials. Please try rephrasing your question."
                await self.session_manager.update_session(
                    session_id=session_id,
                    user_message={"content": query},
                    assistant_message={"content": error_msg},
                    selected_chunks=[]
                )
                return {"response": error_msg, "context_used": False, "off_topic": True, "session_id": session_id}
            
            # Step 3b: Check semantic relevance (replaces keyword-based validation)
            if retrieval_info.get('status') == 'no_relevant_chunks':
                # Even with full context, if no chunks passed similarity threshold, query may be off-topic
                logger.warning(f"No relevant chunks found for query in topic '{topic_name}'")
                off_topic_msg = (
                    f"I can only answer questions about {topic_name} "
                    f"based on your study materials. This question appears to be outside "
                    f"the scope of the current topic. Please ask a question related to {topic_name}."
                )
                await self.session_manager.update_session(
                    session_id=session_id,
                    user_message={"content": query},
                    assistant_message={"content": off_topic_msg},
                    selected_chunks=[]
                )
                return {"response": off_topic_msg, "context_used": False, "off_topic": True, "session_id": session_id}
            
            # Step 4: Build strict prompt
            from .constraint_engine import StrictConstraintEngine
            
            constraint_engine = StrictConstraintEngine(topic_config=session.get('config', {}))
            prompt = constraint_engine.build_strict_prompt(
                query=query,
                context_string=context_string,
                conversation_history=session.get('conversation_history', []),
                student_profile=session.get('student_profile', {}),
                topic=session.get('topic', {})
            )
            
            # Step 5: Call LLM
            if self.llm_gateway:
                llm_response = await self.llm_gateway.generate(
                    prompt=prompt,
                    temperature=0.3,
                    max_tokens=2000
                )
            else:
                # Fallback: use Teacher_AI_Agent's LLM
                llm_response = await self._call_llm_fallback(prompt)
            
            # Step 6: Validate response
            is_valid, reason, validation_info = constraint_engine.validate_response(
                response=llm_response,
                topic_name=session['topic'].get('topic_name', ''),
                context_string=context_string
            )
            
            if not is_valid:
                logger.warning(f"Response validation failed: {reason}")
                # Could regenerate or use a safe fallback
                llm_response = constraint_engine.build_off_topic_response(
                    session['topic'].get('topic_name', 'this topic')
                )
            
            # Step 7: Update session
            await self.session_manager.update_session(
                session_id=session_id,
                user_message={"content": query},
                assistant_message={"content": llm_response},
                selected_chunks=selected_chunks
            )
            
            response_data = {
                "response": llm_response,
                "context_used": True,
                "chunks_referenced": selected_chunks,
                "retrieval_info": retrieval_info,
                "validation_info": validation_info,
                "session_id": session_id
            }
            
            # Include full context mode info if applicable
            if self.use_full_context:
                response_data["full_context_mode"] = True
                response_data["token_budget"] = retrieval_info.get("token_budget_used")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error processing chat: {e}", exc_info=True)
            return {
                "error": f"Failed to process message: {str(e)}",
                "response": "I'm having trouble answering right now. Please try again or rephrase your question.",
                "session_id": session_id
            }
    
    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """End a chat session and clean up resources."""
        if not self._initialized:
            await self.initialize()
        
        success = await self.session_manager.end_session(session_id)
        
        return {
            "session_id": session_id,
            "ended": success,
            "message": "Session ended successfully" if success else "Session not found"
        }
    
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get current session state and statistics."""
        if not self._initialized:
            await self.initialize()
        
        session = await self.session_manager.get_session(session_id)
        
        if not session:
            return {
                "error": "Session not found",
                "session_id": session_id
            }
        
        history = session.get('conversation_history', [])
        message_count = len([m for m in history if m.get('role') == 'user'])
        
        return {
            "session_id": session_id,
            "topic": session.get('topic', {}),
            "context_stats": session.get('context_stats', {}),
            "message_count": message_count,
            "created_at": session.get('created_at'),
            "last_activity": session.get('last_activity'),
            "student_id": session.get('student_id'),
            "subject": session.get('subject'),
            "class_name": session.get('class_name')
        }
    
    async def _call_llm_fallback(self, prompt: str) -> str:
        """
        Fallback LLM call using existing Teacher_AI_Agent infrastructure.
        """
        try:
            # Import from Teacher_AI_Agent
            sys.path.insert(0, os.path.join(_root_dir, 'Teacher_AI_Agent'))
            from Teacher_AI_Agent.search.structured_response import generate_response_from_groq
            
            # Call the existing LLM function
            response = generate_response_from_groq(
                input_text=prompt.split("## PROVIDED CONTEXT")[1].split("## CONVERSATION HISTORY")[0] if "## PROVIDED CONTEXT" in prompt else prompt,
                query=prompt.split("## STUDENT QUESTION")[-1].strip() if "## STUDENT QUESTION" in prompt else "",
                student_profile={}
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Fallback LLM call failed: {e}")
            return "I'm not able to generate a response at this time. Please try again later."
    
    def _extract_topic_keywords(self, topic_name: str) -> List[str]:
        """
        Extract relevant keywords from topic name for validation.
        """
        topic_lower = topic_name.lower()
        
        # Extract words from topic name itself (3+ characters)
        topic_words = [w.strip() for w in topic_lower.replace("-", " ").replace("_", " ").split() if len(w.strip()) > 2]
        
        return list(set(topic_words))  # Remove duplicates

import os
import sys
import logging
import asyncio
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

# Ensure parent path is available
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from Teacher_AI_Agent.agent.retriever_agent import RetrievalOrchestratorAgent
from studentAgent.run_single_queryFun import run_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StudentAgent:
    """
    High-level async-enabled agent wrapper for running queries
    with optional student personalization.
    
    Extended with topic-restricted chat capability for strict
    topic boundary enforcement.
    """

    def __init__(self):
        self.retriever_agent = RetrievalOrchestratorAgent()
        self._loaded = False
        self._executor = ThreadPoolExecutor(max_workers=3)
        # Topic-restricted chat components (lazy initialization)
        self._topic_chat_agent = None
        self._topic_chat_loaded = False

    def load(self):
        """
        Load retriever resources once (embeddings, vector DB, etc.)
        """
        if not self._loaded:
            logger.info("Loading RetrieverAgent...")
            self.retriever_agent.load()
            self._loaded = True

    async def ask_async(
        self,
        query: str,
        class_name: str,
        subject: str,
        student_profile: Optional[Dict] = None,
        subject_agent_id: Optional[str] = None,  # for shared knowledge
        top_k: int = 10,
    ):
        """
        Async version of ask method for better performance.
        """
        if not self._loaded:
            self.load()

        logger.info("Running async query for class=%s subject=%s", class_name, subject)

        def _run_query():
            return run_query(
                retriever_agent=self.retriever_agent,
                query=query,
                db_name=class_name,
                collection_name=subject,
                student_profile=student_profile,
                subject_agent_id=subject_agent_id,  # Pass for shared knowledge
                top_k=top_k
            )
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _run_query)

    def ask(
        self,
        query: str,
        class_name: str,
        subject: str,
        student_profile: Optional[Dict] = None,
        subject_agent_id: Optional[str] = None,  # for shared knowledge
        top_k: int = 10,
    ):
        """
        Run a query with optional student profile.
        Uses async version internally for better performance.

        Args:
            query (str): Student question
            class_name (str): Class/grade (e.g., '10th')
            subject (str): Subject (e.g., 'Science')
            student_profile (dict, optional): Personalization config
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in an event loop, use run_in_executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, 
                        self.ask_async(
                            query, class_name, subject, student_profile, subject_agent_id, top_k
                        )
                    )
                    return future.result(timeout=60)
            else:
                # If no event loop running, run directly
                return asyncio.run(
                    self.ask_async(
                        query, class_name, subject, student_profile, subject_agent_id, top_k
                    )
                )
        except Exception as e:
            logger.error(f"Error in async wrapper: {e}")
            # Fallback to synchronous behavior
            return self._ask_sync_fallback(query, class_name, subject, student_profile, subject_agent_id, top_k)

    def _ask_sync_fallback(
        self,
        query: str,
        class_name: str,
        subject: str,
        student_profile: Optional[Dict] = None,
        subject_agent_id: Optional[str] = None,
        top_k: int = 10,
    ):
        """
        Fallback synchronous ask method.
        """
        if not self._loaded:
            self.load()

        logger.info("Running sync query for class=%s subject=%s", class_name, subject)

        return run_query(
            retriever_agent=self.retriever_agent,
            query=query,
            db_name=class_name,
            collection_name=subject,
            student_profile=student_profile,
            subject_agent_id=subject_agent_id,  # Pass for shared knowledge
            top_k=top_k
        )

    # =========================================================================
    # TOPIC-RESTRICTED CHAT METHODS
    # =========================================================================

    async def _init_topic_chat_agent(self) -> 'TopicRestrictedChatAgent':
        """
        Lazy initialization of topic-restricted chat agent.
        """
        try:
            from studentAgent.topic_restricted import TopicRestrictedChatAgent
            
            agent = TopicRestrictedChatAgent(
                max_context_chunks=5,
                similarity_threshold=0.3
            )
            
            # Initialize with default settings
            await agent.initialize()
            
            self._topic_chat_loaded = True
            logger.info("Topic-restricted chat agent initialized")
            
            return agent
            
        except Exception as e:
            logger.error(f"Failed to initialize topic chat agent: {e}", exc_info=True)
            raise

    async def initialize_topic_session_async(
        self,
        student_id: str,
        class_name: str,
        subject: str,
        topic_id: str,
        student_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Initialize a topic-restricted chat session.
        
        This creates a session that strictly enforces topic boundaries,
        only answering based on the selected topic's content.
        
        Args:
            student_id: Unique student identifier
            class_name: Class/grade (e.g., '10th')
            subject: Subject name (e.g., 'Science')
            topic_id: Topic identifier (e.g., 'topic_photosynthesis')
            student_profile: Optional personalization data
            
        Returns:
            Session info including session_id for subsequent calls
        """
        if not self._loaded:
            self.load()
        
        # Initialize topic chat agent on first use
        if self._topic_chat_agent is None:
            self._topic_chat_agent = await self._init_topic_chat_agent()
        
        return await self._topic_chat_agent.initialize_session(
            student_id=student_id,
            class_name=class_name,
            subject=subject,
            topic_id=topic_id,
            student_profile=student_profile
        )

    def initialize_topic_session(
        self,
        student_id: str,
        class_name: str,
        subject: str,
        topic_id: str,
        student_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for initialize_topic_session_async.
        
        Args:
            student_id: Unique student identifier
            class_name: Class/grade (e.g., '10th')
            subject: Subject name (e.g., 'Science')
            topic_id: Topic identifier
            student_profile: Optional personalization data
            
        Returns:
            Session info including session_id
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in an event loop, use run_in_executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.initialize_topic_session_async(
                            student_id, class_name, subject, topic_id, student_profile
                        )
                    )
                    return future.result(timeout=60)
            else:
                # If no event loop running, run directly
                return asyncio.run(
                    self.initialize_topic_session_async(
                        student_id, class_name, subject, topic_id, student_profile
                    )
                )
        except Exception as e:
            logger.error(f"Error in initialize_topic_session: {e}")
            return {"error": str(e), "session_id": None}

    async def ask_topic_restricted_async(
        self,
        session_id: str,
        query: str,
    ) -> Dict[str, Any]:
        """
        Async version of topic-restricted chat.
        
        Ask a question within a topic-restricted session.
        The agent will ONLY answer based on the selected topic's content.
        
        Args:
            session_id: Active session identifier from initialize_topic_session
            query: Student's question
            
        Returns:
            Response with context usage information
        """
        if not self._loaded:
            self.load()
        
        if self._topic_chat_agent is None:
            raise ValueError("Topic chat session not initialized. Call initialize_topic_session first.")
        
        return await self._topic_chat_agent.chat(
            session_id=session_id,
            query=query
        )

    def ask_topic_restricted(
        self,
        session_id: str,
        query: str,
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for ask_topic_restricted_async.
        
        Ask a question within a topic-restricted session.
        
        Args:
            session_id: Active session identifier
            query: Student's question
            
        Returns:
            Response with context usage information
            
        Example:
            >>> agent = StudentAgent()
            >>> session = agent.initialize_topic_session(
            ...     student_id="stu_001",
            ...     class_name="10th",
            ...     subject="Science",
            ...     topic_id="topic_photosynthesis"
            ... )
            >>> response = agent.ask_topic_restricted(
            ...     session_id=session['session_id'],
            ...     query="What is the role of chlorophyll?"
            ... )
            >>> print(response['response'])
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in an event loop, use run_in_executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.ask_topic_restricted_async(session_id, query)
                    )
                    return future.result(timeout=60)
            else:
                # If no event loop running, run directly
                return asyncio.run(
                    self.ask_topic_restricted_async(session_id, query)
                )
        except Exception as e:
            logger.error(f"Error in ask_topic_restricted: {e}")
            return {
                "error": str(e),
                "response": "I'm having trouble answering right now. Please try again.",
                "session_id": session_id
            }

    def end_topic_session(self, session_id: str) -> Dict[str, Any]:
        """
        End a topic-restricted chat session.
        
        Args:
            session_id: Session to end
            
        Returns:
            End session confirmation
        """
        try:
            if self._topic_chat_agent is None:
                return {"error": "No active topic chat agent", "ended": False}
            
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._topic_chat_agent.end_session(session_id)
                    )
                    return future.result(timeout=30)
            else:
                return asyncio.run(
                    self._topic_chat_agent.end_session(session_id)
                )
                
        except Exception as e:
            logger.error(f"Error ending topic session: {e}")
            return {"error": str(e), "ended": False}

"""
Topic Chat API Routes

FastAPI endpoints for topic-restricted chat functionality.
Provides session management and chat endpoints.
"""

import os
import sys
import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

# Try to import FastAPI
try:
    from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    # Create dummy classes for type hints
    class BaseModel:
        pass
    class APIRouter:
        def get(self, *args, **kwargs): pass
        def post(self, *args, **kwargs): pass
        def delete(self, *args, **kwargs): pass
    class Query:
        def __init__(self, *args, **kwargs): pass

# Add paths for imports
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

# Import ConversationManager and StudentManager for persistence
try:
    from studentProfileDetails.dbutils import ConversationManager, StudentManager
    HAS_CONVERSATION_MANAGER = True
except ImportError:
    HAS_CONVERSATION_MANAGER = False
    logger.warning("ConversationManager not available, chat persistence disabled")

# Pydantic models for request/response
if HAS_FASTAPI:
    class CreateSessionRequest(BaseModel):
        student_id: str = Field(..., description="Unique student identifier")
        class_name: str = Field(..., description="Class/grade (e.g., '10th')")
        subject: str = Field(..., description="Subject name (e.g., 'Science')")
        topic_id: str = Field(..., description="Topic identifier")
        student_profile: Optional[Dict[str, Any]] = Field(
            default=None,
            description="Optional student personalization data"
        )
    
    class ChatRequest(BaseModel):
        query: str = Field(..., description="Student's question", max_length=3000)
    
    class ChatResponse(BaseModel):
        response: str = Field(..., description="Agent's response")
        context_used: bool = Field(..., description="Whether context was used")
        chunks_referenced: List[str] = Field(default_factory=list)
        retrieval_info: Dict[str, Any] = Field(default_factory=dict)
        session_id: str = Field(..., description="Session identifier")
        conversation_id: Optional[str] = Field(default=None, description="Database conversation ID")
        safety_flag: Optional[bool] = Field(default=False)
        
    class SessionResponse(BaseModel):
        session_id: str
        topic: Dict[str, Any]
        context_stats: Dict[str, Any]
        message: str
        
    class SessionStatusResponse(BaseModel):
        session_id: str
        topic: Dict[str, Any]
        context_stats: Dict[str, Any]
        message_count: int
        created_at: Optional[str]
        last_activity: Optional[str]
        student_id: str
        subject: str
        class_name: str
        
    class EndSessionResponse(BaseModel):
        session_id: str
        ended: bool
        message: str
    
    class SubtopicInfo(BaseModel):
        subtopic: str
        confidence: Optional[float] = None
    
    class TopicInfo(BaseModel):
        topic_id: str
        topic_name: str
        description: Optional[str] = None
        subtopics: Optional[List[Union[str, SubtopicInfo]]] = None
    
    class TopicsListResponse(BaseModel):
        topics: List[TopicInfo]
        total_count: int
        class_name: Optional[str] = None
        subject: Optional[str] = None
        message: str

# Global agent instance (initialized on first use)
_topic_chat_agent = None

async def get_topic_chat_agent():
    """Get or initialize the topic chat agent."""
    global _topic_chat_agent
    
    if _topic_chat_agent is None:
        try:
            from studentAgent.topic_restricted import TopicRestrictedChatAgent
            from Teacher_AI_Agent.model_cache import ModelCache
            
            # Get embedding model from cache
            model_cache = ModelCache()
            embedding_model = model_cache.get_embedding_model()
            
            _topic_chat_agent = TopicRestrictedChatAgent()
            await _topic_chat_agent.initialize(embedding_model=embedding_model)
            
        except Exception as e:
            logger.error(f"Failed to initialize topic chat agent: {e}")
            raise HTTPException(status_code=500, detail="Failed to initialize chat agent")
    
    return _topic_chat_agent

# Create router
if HAS_FASTAPI:
    router = APIRouter(prefix="/topic-chat", tags=["topic-chat"])
else:
    router = None
    logger.warning("FastAPI not available, API routes not created")

# API Endpoints
if HAS_FASTAPI:
    @router.post("/session", response_model=SessionResponse)
    async def create_session(
        request: CreateSessionRequest,
        agent = Depends(get_topic_chat_agent)
    ):
        """
        Initialize a new topic-restricted chat session.
        
        Loads all topic chunks into session cache.
        """
        try:
            result = await agent.initialize_session(
                student_id=request.student_id,
                class_name=request.class_name,
                subject=request.subject,
                topic_id=request.topic_id,
                student_profile=request.student_profile
            )
            
            if result.get('error'):
                raise HTTPException(status_code=400, detail=result['error'])
            
            return SessionResponse(
                session_id=result['session_id'],
                topic=result['topic'],
                context_stats=result['context_stats'],
                message=result.get('message', 'Session created successfully')
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating session: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")
    
    @router.get("/topics", response_model=TopicsListResponse)
    async def list_topics(
        class_name: Optional[str] = None,
        subject: Optional[str] = None,
        max_topics: int = Query(default=20, ge=1, le=50, description="Maximum number of topics to extract")
    ):
        """
        List all available topics for topic-restricted chat.
        
        This endpoint dynamically extracts topics from the subject's document chunks
        using LLM analysis. Students can use the returned topic_id to start a chat session.
        
        Args:
            class_name: Optional filter by class/grade (e.g., '10')
            subject: Optional filter by subject (e.g., 'Science')
            max_topics: Maximum number of topics to return (1-50)
            
        Returns:
            List of topics with their IDs, names, and descriptions
            
        Example:
            GET /api/v1/topic-chat/topics?class_name=10&subject=Science
            
            Response:
            {
                "topics": [
                    {
                        "topic_id": "Metals and Non-metals",
                        "topic_name": "Metals and Non-metals",
                        "description": "Properties and uses of metals and non-metals",
                        "subtopics": ["Physical properties", "Chemical properties"]
                    }
                ],
                "total_count": 5,
                "class_name": "10",
                "subject": "Science",
                "message": "Successfully extracted 5 topics"
            }
        """
        try:
            # Import required modules
            import os
            from pymongo import MongoClient
            from Teacher_AI_Agent.agents.topic_extraction_agent import TopicExtractionAgent
            from Teacher_AI_Agent.model_cache import ModelCache
            
            # Get embedding model from cache
            model_cache = ModelCache()
            embedding_model = model_cache.get_embedding_model()
            topic_agent = TopicExtractionAgent(embedding_model=embedding_model)
            
            topics_list = []
            
            # If class_name and subject provided, extract from that specific collection
            if class_name and subject:
                try:
                    # Extract topics from the specific collection
                    result = topic_agent.extract_topics_from_agent(
                        subject_agent_id=f"agent_{class_name}_{subject}",
                        db_name=class_name,
                        collection_name=subject,
                        max_topics=max_topics,
                        include_subtopics=True
                    )
                    
                    if result.get("status") == "success":
                        for topic in result.get("topics", []):
                            topic_name = topic.get("topic", "").strip()
                            # Skip topics with empty names
                            if not topic_name:
                                logger.warning(f"Skipping topic with empty name: {topic}")
                                continue
                            topics_list.append({
                                "topic_id": topic_name.replace(" ", "_").lower(),
                                "topic_name": topic_name,
                                "description": topic.get("description", ""),
                                "subtopics": topic.get("subtopics", [])
                            })
                        
                        return TopicsListResponse(
                            topics=topics_list,
                            total_count=len(topics_list),
                            class_name=class_name,
                            subject=subject,
                            message=f"Successfully extracted {len(topics_list)} topics from {class_name}.{subject}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to extract from {class_name}.{subject}: {e}")
            
            # Otherwise, scan all available collections
            MONGODB_URI = os.environ.get("MONGODB_URI")
            if MONGODB_URI:
                client = MongoClient(MONGODB_URI)
                
                # Get all databases (excluding system databases)
                system_dbs = {"admin", "local", "config"}
                databases = [db for db in client.list_database_names() if db not in system_dbs]
                
                for db_name in databases:
                    if class_name and db_name != class_name:
                        continue
                        
                    db = client[db_name]
                    collections = db.list_collection_names()
                    
                    for collection_name in collections:
                        if subject and collection_name != subject:
                            continue
                            
                        try:
                            # Get a sample to find subject_agent_id
                            collection = db[collection_name]
                            sample = collection.find_one({}, {"subject_agent_id": 1})
                            
                            if sample and sample.get("subject_agent_id"):
                                result = topic_agent.extract_topics_from_agent(
                                    subject_agent_id=sample["subject_agent_id"],
                                    db_name=db_name,
                                    collection_name=collection_name,
                                    max_topics=max_topics,
                                    include_subtopics=True
                                )
                                
                                if result.get("status") == "success":
                                    for topic in result.get("topics", []):
                                        topic_name = topic.get("topic", "").strip()
                                        # Skip topics with empty names
                                        if not topic_name:
                                            logger.warning(f"Skipping topic with empty name from {db_name}.{collection_name}")
                                            continue
                                        topic_id = topic_name.replace(" ", "_").lower()
                                        # Check if topic already exists to avoid duplicates
                                        if not any(t.get("topic_id") == topic_id for t in topics_list):
                                            topics_list.append({
                                                "topic_id": topic_id,
                                                "topic_name": topic_name,
                                                "description": topic.get("description", ""),
                                                "subtopics": topic.get("subtopics", [])
                                            })
                        except Exception as e:
                            logger.warning(f"Failed to extract from {db_name}.{collection_name}: {e}")
                            continue
                
                client.close()
            
            return TopicsListResponse(
                topics=topics_list,
                total_count=len(topics_list),
                class_name=class_name,
                subject=subject,
                message=f"Successfully extracted {len(topics_list)} topics from available collections"
            )
            
        except Exception as e:
            logger.error(f"Error listing topics: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list topics: {str(e)}"
            )
    
    @router.post("/{session_id}/ask", response_model=ChatResponse)
    async def chat_message(
        session_id: str,
        request: ChatRequest,
        agent = Depends(get_topic_chat_agent)
    ):
        """
        Send a message in a topic-restricted chat session.
        
        The agent will:
        1. Retrieve relevant context from pre-loaded topic
        2. Enforce strict topic constraints
        3. Generate response using ONLY the provided context
        4. Save conversation to database for persistence
        """
        try:
            result = await agent.chat(
                session_id=session_id,
                query=request.query
            )
            
            if result.get('error'):
                # Check if session expired
                if "expired" in result['error'].lower() or "not found" in result['error'].lower():
                    raise HTTPException(status_code=404, detail=result['error'])
                raise HTTPException(status_code=400, detail=result['error'])
            
            # Save conversation to database if persistence is available
            if HAS_CONVERSATION_MANAGER:
                try:
                    # Get session info to extract metadata
                    session_status = await agent.get_session_status(session_id)
                    
                    if not session_status.get('error'):
                        student_id = session_status.get('student_id', '')
                        subject = session_status.get('subject', 'Topic Chat')
                        class_name = session_status.get('class_name', '')
                        
                        # Get student's subject_agent_id from their profile
                        subject_agent_id = None
                        try:
                            student_manager = StudentManager()
                            student = student_manager.get_student(student_id)
                            logger.info(f"🔍 Student lookup: {student_id}, found: {student is not None}")
                            if student:
                                logger.info(f"🔍 Student keys: {list(student.keys())}")
                                logger.info(f"🔍 Session subject: '{subject}' (type: {type(subject)})")
                                # Check for subject_agent in student_details or at root level
                                student_details = student.get('student_details', {})
                                subject_agent_data = student_details.get('subject_agent') or student.get('subject_agent') or student.get('subject_agents')
                                logger.info(f"🔍 Subject agent data: {subject_agent_data}")
                                # Also check for direct subject_agent_id at root or in chat_sessions
                                if not subject_agent_data:
                                    chat_sessions = student.get('chat_sessions', {})
                                    subject_agent_id = chat_sessions.get('subject_agent_id') or student.get('subject_agent_id')
                                if subject_agent_data:
                                    for sa in subject_agent_data:
                                        sa_subject = sa.get('subject', '').lower().strip()
                                        session_subject = subject.lower().strip() if subject else ''
                                        logger.info(f"🔍 Comparing: '{sa_subject}' == '{session_subject}'")
                                        if sa_subject == session_subject:
                                            subject_agent_id = sa.get('subject_agent_id')
                                            logger.info(f"✅ Found subject_agent_id: {subject_agent_id}")
                                            break
                                    if not subject_agent_id:
                                        logger.warning(f"⚠️ No matching subject found for '{subject}'")
                                else:
                                    logger.warning(f"⚠️ No subject_agent data for student {student_id}")
                            else:
                                logger.warning(f"⚠️ Student not found: {student_id}")
                        except Exception as e:
                            logger.warning(f"❌ Could not fetch subject_agent_id: {e}", exc_info=True)
                        
                        # Initialize conversation manager and save
                        conversation_manager = ConversationManager()
                        conversation_id = conversation_manager.add_conversation(
                            student_id=student_id,
                            subject=subject,
                            query=request.query,
                            response=result['response'],
                            chat_session_id=session_id,
                            agent_id=subject_agent_id if subject_agent_id else (f"topic_{class_name}_{subject}" if class_name and subject else "topic_chat"),
                            additional_data={
                                "topic_id": session_status.get('topic', {}).get('topic_id', ''),
                                "topic_name": session_status.get('topic', {}).get('topic_name', ''),
                                "class_name": class_name,
                                "context_used": result.get('context_used', False),
                                "chunks_referenced": result.get('chunks_referenced', [])
                            }
                        )
                        logger.info(f"Conversation saved for session {session_id}, student {student_id}, agent {subject_agent_id}, conversation_id: {conversation_id}")
                        # Store conversation_id for response
                        result['conversation_id'] = conversation_id
                except Exception as e:
                    # Log error but don't fail the chat response
                    logger.error(f"Failed to save conversation: {e}")
            
            return ChatResponse(
                response=result['response'],
                context_used=result.get('context_used', False),
                chunks_referenced=result.get('chunks_referenced', []),
                retrieval_info=result.get('retrieval_info', {}),
                session_id=result['session_id'],
                conversation_id=result.get('conversation_id'),
                safety_flag=result.get('safety_flag', False)
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing chat message: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")
    
    @router.get("/{session_id}", response_model=SessionStatusResponse)
    async def get_session_status(
        session_id: str,
        agent = Depends(get_topic_chat_agent)
    ):
        """Get current session state and statistics."""
        try:
            result = await agent.get_session_status(session_id)
            
            if result.get('error'):
                raise HTTPException(status_code=404, detail=result['error'])
            
            return SessionStatusResponse(
                session_id=result['session_id'],
                topic=result['topic'],
                context_stats=result['context_stats'],
                message_count=result.get('message_count', 0),
                created_at=result.get('created_at'),
                last_activity=result.get('last_activity'),
                student_id=result.get('student_id', ''),
                subject=result.get('subject', ''),
                class_name=result.get('class_name', '')
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting session status: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")
    
    @router.delete("/{session_id}", response_model=EndSessionResponse)
    async def end_session(
        session_id: str,
        agent = Depends(get_topic_chat_agent)
    ):
        """End a chat session and clean up resources."""
        try:
            result = await agent.end_session(session_id)
            
            return EndSessionResponse(
                session_id=result['session_id'],
                ended=result['ended'],
                message=result.get('message', 'Session ended')
            )
            
        except Exception as e:
            logger.error(f"Error ending session: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to end session: {str(e)}")

    @router.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "topic-chat-agent"
        }

# Function to register routes with main app
def register_routes(app):
    """Register topic chat routes with FastAPI app."""
    if HAS_FASTAPI and router:
        app.include_router(router)
        logger.info("Topic chat API routes registered")
    else:
        logger.warning("Could not register topic chat routes - FastAPI not available")

# Standalone function for testing
async def test_topic_chat():
    """Test function for topic chat agent."""
    print("Testing Topic Restricted Chat Agent...")
    
    try:
        from studentAgent.topic_restricted import TopicRestrictedChatAgent
        
        agent = TopicRestrictedChatAgent()
        await agent.initialize()
        
        # Create a test session
        session_result = await agent.initialize_session(
            student_id="test_student_001",
            class_name="10th",
            subject="Science",
            topic_id="topic_photosynthesis",
            student_profile={
                "learning_style": "visual",
                "grade_level": "10th"
            }
        )
        
        if session_result.get('error'):
            print(f"Session creation failed: {session_result['error']}")
            return
        
        session_id = session_result['session_id']
        print(f"✓ Session created: {session_id}")
        print(f"  Topic: {session_result['topic']['topic_name']}")
        print(f"  Context stats: {session_result['context_stats']}")
        
        # Test on-topic query
        print("\n--- Testing on-topic query ---")
        response1 = await agent.chat(
            session_id=session_id,
            query="What is photosynthesis?"
        )
        print(f"Query: 'What is photosynthesis?'")
        print(f"Response: {response1['response'][:200]}...")
        print(f"Context used: {response1['context_used']}")
        
        # Test off-topic query
        print("\n--- Testing off-topic query ---")
        response2 = await agent.chat(
            session_id=session_id,
            query="Who won the World Cup in 2022?"
        )
        print(f"Query: 'Who won the World Cup in 2022?'")
        print(f"Response: {response2['response'][:200]}...")
        print(f"Off-topic detected: {response2.get('off_topic', False)}")
        
        # End session
        print("\n--- Ending session ---")
        end_result = await agent.end_session(session_id)
        print(f"Session ended: {end_result['ended']}")
        
        print("\n✓ All tests completed successfully!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_topic_chat())

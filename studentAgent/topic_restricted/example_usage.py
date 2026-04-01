"""
Topic Restricted Chat Agent - Usage Example

This example demonstrates how to use the topic-restricted chat functionality
to create a chat session that strictly enforces topic boundaries.
"""

import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_usage():
    """
    Example: Student using topic-restricted chat
    """
    print("=" * 60)
    print("Topic Restricted Chat Agent - Example Usage")
    print("=" * 60)
    
    try:
        from studentAgent.student_agent import StudentAgent
        
        # Initialize the agent
        print("\n1. Initializing StudentAgent...")
        agent = StudentAgent()
        agent.load()
        print("   ✓ Agent loaded successfully")
        
        # Step 1: Initialize topic session
        print("\n2. Creating topic-restricted session...")
        session = agent.initialize_topic_session(
            student_id="student_123",
            class_name="10th",
            subject="Science",
            topic_id="topic_photosynthesis",
            student_profile={
                "learning_style": "visual",
                "grade_level": "10th",
                "response_length": "medium",
                "include_example": True
            }
        )
        
        if session.get('error'):
            print(f"   ✗ Session creation failed: {session['error']}")
            return
        
        session_id = session['session_id']
        print(f"   ✓ Session created: {session_id}")
        print(f"   ✓ Topic: {session['topic']['topic_name']}")
        print(f"   ✓ Context stats: {session['context_stats']}")
        
        # Step 2: Chat with on-topic questions
        print("\n3. Testing on-topic questions...")
        
        on_topic_questions = [
            "What is photosynthesis?",
            "What is the role of chlorophyll?",
            "How do plants convert light energy?",
            "What is the Calvin cycle?",
        ]
        
        for i, question in enumerate(on_topic_questions, 1):
            print(f"\n   Q{i}: {question}")
            response = agent.ask_topic_restricted(
                session_id=session_id,
                query=question
            )
            
            if response.get('error'):
                print(f"   ✗ Error: {response['error']}")
            else:
                print(f"   A{i}: {response['response'][:150]}...")
                print(f"      Context used: {response.get('context_used', False)}")
                print(f"      Chunks: {len(response.get('chunks_referenced', []))}")
        
        # Step 3: Test off-topic question
        print("\n4. Testing off-topic question (should be rejected)...")
        off_topic_response = agent.ask_topic_restricted(
            session_id=session_id,
            query="Who won the World Cup in 2022?"
        )
        print(f"   Q: Who won the World Cup in 2022?")
        print(f"   A: {off_topic_response['response'][:150]}...")
        print(f"      Off-topic detected: {off_topic_response.get('off_topic', False)}")
        
        # Step 4: Test another off-topic question
        print("\n5. Testing another off-topic question...")
        off_topic_response2 = agent.ask_topic_restricted(
            session_id=session_id,
            query="How do I bake a chocolate cake?"
        )
        print(f"   Q: How do I bake a chocolate cake?")
        print(f"   A: {off_topic_response2['response'][:150]}...")
        print(f"      Off-topic detected: {off_topic_response2.get('off_topic', False)}")
        
        # Step 5: End session
        print("\n6. Ending session...")
        end_result = agent.end_topic_session(session_id)
        print(f"   ✓ Session ended: {end_result.get('ended', False)}")
        
        print("\n" + "=" * 60)
        print("Example completed successfully!")
        print("=" * 60)
        
    except ImportError as e:
        print(f"\n✗ Import error: {e}")
        print("  Make sure all dependencies are installed.")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def example_direct_usage():
    """
    Example: Direct usage of TopicRestrictedChatAgent
    """
    print("\n" + "=" * 60)
    print("Direct TopicRestrictedChatAgent Usage")
    print("=" * 60)
    
    async def run():
        try:
            from studentAgent.topic_restricted import TopicRestrictedChatAgent
            
            # Initialize agent
            print("\n1. Initializing TopicRestrictedChatAgent...")
            agent = TopicRestrictedChatAgent(
                max_context_chunks=5,
                similarity_threshold=0.3
            )
            await agent.initialize()
            print("   ✓ Agent initialized")
            
            # Create session
            print("\n2. Creating session...")
            session = await agent.initialize_session(
                student_id="student_456",
                class_name="9th",
                subject="Mathematics",
                topic_id="topic_algebraic_equations",
                student_profile={
                    "grade_level": "9th",
                    "learning_style": "step_by_step"
                }
            )
            
            if session.get('error'):
                print(f"   ✗ Failed: {session['error']}")
                return
            
            session_id = session['session_id']
            print(f"   ✓ Session: {session_id}")
            
            # Ask questions
            print("\n3. Asking questions...")
            questions = [
                "How do I solve linear equations?",
                "What is the quadratic formula?",
            ]
            
            for question in questions:
                print(f"\n   Q: {question}")
                response = await agent.chat(
                    session_id=session_id,
                    query=question
                )
                print(f"   A: {response['response'][:150]}...")
            
            # End session
            print("\n4. Ending session...")
            result = await agent.end_session(session_id)
            print(f"   ✓ Ended: {result['ended']}")
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run())


def example_api_usage():
    """
    Example: API usage with FastAPI
    """
    print("\n" + "=" * 60)
    print("API Usage Example")
    print("=" * 60)
    
    example_code = '''
# In your FastAPI main.py:

from fastapi import FastAPI
from studentAgent.api.topic_chat_routes import register_routes

app = FastAPI()

# Register topic chat routes
register_routes(app)

# Now you have these endpoints:
# POST /api/v1/topic-chat/session           - Create session
# POST /api/v1/topic-chat/{session_id}/ask  - Send message  
# GET  /api/v1/topic-chat/{session_id}      - Get session status
# DELETE /api/v1/topic-chat/{session_id}    - End session

# Example client usage:
import requests

# Create session
response = requests.post(
    "http://localhost:8000/api/v1/topic-chat/session",
    json={
        "student_id": "stu_001",
        "class_name": "10th",
        "subject": "Science", 
        "topic_id": "topic_photosynthesis",
        "student_profile": {
            "learning_style": "visual",
            "grade_level": "10th"
        }
    }
)
session = response.json()
session_id = session["session_id"]

# Send message
response = requests.post(
    f"http://localhost:8000/api/v1/topic-chat/{session_id}/ask",
    json={"query": "What is photosynthesis?"}
)
answer = response.json()
print(answer["response"])

# End session
requests.delete(f"http://localhost:8000/api/v1/topic-chat/{session_id}")
'''
    print(example_code)


if __name__ == "__main__":
    # Run examples
    print("\n" + "=" * 80)
    print("TOPIC RESTRICTED CHAT AGENT - USAGE EXAMPLES")
    print("=" * 80)
    
    # Example 1: StudentAgent usage
    asyncio.run(example_usage())
    
    # Example 2: Direct agent usage
    example_direct_usage()
    
    # Example 3: API usage
    example_api_usage()
    
    print("\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80)

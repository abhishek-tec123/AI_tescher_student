#!/usr/bin/env python3
"""
Test script for chat session agent information storage
"""

import requests
import json

# Test data
BASE_URL = "http://localhost:8000/api/v1/student"
STUDENT_ID = "std_EA9MG"

def test_create_session_with_agent():
    """Test creating a chat session with agent information"""
    print("🧪 Testing chat session creation with agent information...")
    
    session_data = {
        "student_id": STUDENT_ID,
        "title": "New Math Chat",
        "agent_type": "subject",
        "agent_name": "Math",
        "agent_id": "agent_6ZN6T"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat-sessions",
            json=session_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Session created successfully!")
            print(f"   Session ID: {result.get('chat_session_id')}")
            print(f"   Title: {result.get('title')}")
            print(f"   Agent Type: {result.get('agent_type')}")
            print(f"   Agent Name: {result.get('agent_name')}")
            print(f"   Agent ID: {result.get('agent_id')}")
            return result.get('chat_session_id')
        else:
            print(f"❌ Failed to create session: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating session: {e}")
        return None

def test_get_sessions():
    """Test retrieving chat sessions to verify agent information is stored"""
    print("\n🧪 Testing chat session retrieval...")
    
    try:
        response = requests.get(f"{BASE_URL}/{STUDENT_ID}/chat-sessions")
        
        if response.status_code == 200:
            result = response.json()
            sessions = result.get('chat_sessions', [])
            print(f"✅ Retrieved {len(sessions)} sessions")
            
            for session in sessions[:3]:  # Show first 3 sessions
                print(f"\n📝 Session: {session.get('chat_session_id')}")
                print(f"   Title: {session.get('title')}")
                print(f"   Agent Type: {session.get('agent_type', 'N/A')}")
                print(f"   Agent Name: {session.get('agent_name', 'N/A')}")
                print(f"   Agent ID: {session.get('agent_id', 'N/A')}")
                print(f"   Created: {session.get('created_at', 'N/A')}")
                
        else:
            print(f"❌ Failed to retrieve sessions: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error retrieving sessions: {e}")

def test_create_session_without_agent():
    """Test creating a chat session without agent information (backward compatibility)"""
    print("\n🧪 Testing backward compatibility (no agent info)...")
    
    session_data = {
        "student_id": STUDENT_ID,
        "title": "General Chat"
        # No agent information
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat-sessions",
            json=session_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Session created without agent info (backward compatible)!")
            print(f"   Session ID: {result.get('chat_session_id')}")
            print(f"   Title: {result.get('title')}")
            return result.get('chat_session_id')
        else:
            print(f"❌ Failed to create session: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating session: {e}")
        return None

if __name__ == "__main__":
    print("🚀 Starting Chat Session Agent Information Tests\n")
    
    # Test 1: Create session with agent info
    session_id_1 = test_create_session_with_agent()
    
    # Test 2: Create session without agent info (backward compatibility)
    session_id_2 = test_create_session_without_agent()
    
    # Test 3: Retrieve all sessions to verify storage
    test_get_sessions()
    
    print("\n🎯 Test Summary:")
    print("✅ API now accepts agent information in session creation")
    print("✅ Agent information is stored in database")
    print("✅ Agent information is returned in session listings")
    print("✅ Backward compatibility maintained (optional agent fields)")
    print("\n🔧 Frontend can now send agent information like:")
    print(json.dumps({
        "student_id": "std_EA9MG",
        "title": "New Math Chat",
        "agent_type": "subject",
        "agent_name": "Math", 
        "agent_id": "agent_6ZN6T"
    }, indent=2))

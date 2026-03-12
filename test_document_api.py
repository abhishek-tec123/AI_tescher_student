#!/usr/bin/env python3
"""
Test script for the new document API endpoint
"""

import requests
import json

# Example usage of the new API endpoint
def test_agent_document_ids_api():
    """
    Test the POST /documents/agent-documents endpoint
    """
    
    # API endpoint URL (adjust based on your server configuration)
    url = "http://localhost:8000/documents/agent-documents"
    
    # Request body with agent_id
    request_data = {
        "agent_id": "agent_VR8FA"  # Example agent ID from your database
    }
    
    # Headers (you'll need to add authentication token)
    headers = {
        "Content-Type": "application/json",
        # Add your auth token here, e.g.:
        # "Authorization": "Bearer your_token_here"
    }
    
    try:
        print(f"Making POST request to: {url}")
        print(f"Request body: {json.dumps(request_data, indent=2)}")
        
        # Make the POST request
        response = requests.post(url, json=request_data, headers=headers)
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Success! Response:")
            print(f"Agent ID: {result['agent_id']}")
            print(f"Total documents: {result['total_count']}")
            print(f"Document IDs: {result['doc_unique_ids']}")
        else:
            print(f"\n❌ Error! Status: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")

# Expected response format:
"""
{
    "agent_id": "agent_VR8FA",
    "doc_unique_ids": ["89952", "89953", "89954"],
    "total_count": 3
}
"""

if __name__ == "__main__":
    test_agent_document_ids_api()

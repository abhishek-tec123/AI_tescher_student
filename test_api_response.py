#!/usr/bin/env python3

import requests
import json

# Test the API endpoint
url = "http://localhost:8000/api/v1/student/agent-query"
headers = {"Content-Type": "application/json"}
data = {
    "student_id": "std_XS1KB",
    "class_name": "10", 
    "subject": "Home science",
    "query": "what is role of abhishek"
}

try:
    response = requests.post(url, headers=headers, json=data, timeout=30)
    if response.status_code == 200:
        result = response.json()
        print("🔍 API Response:")
        print(f"Response length: {len(result.get('response', ''))}")
        print(f"First 200 chars: {result.get('response', '')[:200]}...")
        
        # Check if response contains Abhishek information
        response_text = result.get('response', '').lower()
        if 'abhishek' in response_text:
            print("✅ SUCCESS: Response contains Abhishek information!")
        else:
            print("❌ ISSUE: Response does not contain Abhishek information")
            
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Connection error: {e}")
    print("Make sure the server is running on localhost:8000")

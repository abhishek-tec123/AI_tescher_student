#!/usr/bin/env python3

import asyncio
import sys
import os
import logging

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up logging to see the search process
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def test_search_logic():
    """Test the search logic directly without full imports."""
    
    # Mock data to simulate the search results
    mock_results = [
        {"score": 0.0858, "source_type": "shared", "text": "Abhishek Kumar is a Python developer with 2+ years of experience..."},
        {"score": 0.3576, "source_type": "agent", "text": "Home science topics include nutrition and family studies..."},
        {"score": 0.1, "source_type": "shared", "text": "Abhishek worked as a software engineer at TechCorp..."}
    ]
    
    MIN_SCORE_THRESHOLD = 0.2
    top_k = 10
    
    print("🔍 Testing threshold filtering logic...")
    print(f"Mock results: {len(mock_results)} items")
    print(f"MIN_SCORE_THRESHOLD: {MIN_SCORE_THRESHOLD}")
    print("-" * 50)
    
    # Apply the new logic from EnhancedSimilaritySearch.py
    all_results = mock_results
    all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # Separate agent and shared results
    agent_results = [doc for doc in all_results if doc.get('source_type') == 'agent']
    shared_results = [doc for doc in all_results if doc.get('source_type') == 'shared']
    
    print(f"Agent results: {len(agent_results)}")
    for result in agent_results:
        print(f"  - Score: {result['score']}, Type: {result['source_type']}")
    
    print(f"Shared results: {len(shared_results)}")
    for result in shared_results:
        print(f"  - Score: {result['score']}, Type: {result['source_type']}")
    
    # Apply threshold filtering only to agent results
    filtered_agent_results = [
        doc for doc in agent_results
        if doc.get("score", 0) >= MIN_SCORE_THRESHOLD
    ]
    
    # Combine results: shared documents (no threshold) + filtered agent results
    final_results = shared_results + filtered_agent_results
    
    # Sort final results by score and limit
    final_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    all_results = final_results[:top_k]
    
    print("-" * 50)
    print("✅ FINAL RESULTS:")
    for i, result in enumerate(all_results):
        print(f"  {i+1}. Score: {result['score']:.4f}, Type: {result['source_type']}")
        print(f"     Text: {result['text'][:50]}...")
    
    shared_count = len([d for d in all_results if d.get('source_type') == 'shared'])
    agent_count = len([d for d in all_results if d.get('source_type') == 'agent'])
    
    print(f"\n✅ Using {shared_count} shared documents (no threshold)")
    print(f"✅ Using {agent_count} agent documents (threshold: {MIN_SCORE_THRESHOLD})")
    
    if shared_count > 0:
        print(f"\n🎉 SUCCESS: Shared documents are now included regardless of low similarity scores!")
    else:
        print(f"\n❌ ISSUE: No shared documents found")

if __name__ == "__main__":
    asyncio.run(test_search_logic())

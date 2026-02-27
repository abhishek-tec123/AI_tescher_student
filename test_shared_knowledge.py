#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Teacher_AI_Agent.search.EnhancedSimilaritySearch import retrieve_chunks_with_shared_knowledge
from model_cache import model_cache

async def test_shared_knowledge():
    """Test the shared knowledge search without threshold filtering."""
    
    # Initialize embedding model
    embedding_model = model_cache.get_embedding_model("sentence-transformers/all-MiniLM-L6-v2")
    
    # Test query
    query = "what is role of abhishek"
    
    # Student profile
    student_profile = {
        "student_id": "std_XS1KB",
        "class_name": "10", 
        "subject": "Home science"
    }
    
    print("🔍 Testing shared knowledge search...")
    print(f"Query: {query}")
    print(f"Student ID: {student_profile['student_id']}")
    print("-" * 50)
    
    try:
        # Search with shared knowledge
        result = retrieve_chunks_with_shared_knowledge(
            query=query,
            db_name="10",
            collection_name="Home science", 
            subject_agent_id="agent_YXA00",
            embedding_model=embedding_model,
            student_profile=student_profile,
            top_k=10,
            disable_rl=True
        )
        
        print("📊 Results:")
        print(f"Response length: {len(result.get('response', ''))}")
        print(f"Sources: {result.get('source_summary', [])}")
        print(f"Chunks used: {result.get('chunks_used', 0)}")
        print("-" * 50)
        
        print("📝 Response preview:")
        response = result.get('response', '')
        print(response[:500] + "..." if len(response) > 500 else response)
        
        # Check if shared documents were used
        sources = result.get('sources', [])
        shared_docs = [s for s in sources if s.get('type') == 'shared']
        
        if shared_docs:
            print(f"\n✅ SUCCESS: Used {len(shared_docs)} shared document(s)")
            for doc in shared_docs:
                print(f"   - {doc.get('name', 'Unknown')}: {doc.get('results_count', 0)} chunks")
        else:
            print(f"\n❌ ISSUE: No shared documents were used")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_shared_knowledge())

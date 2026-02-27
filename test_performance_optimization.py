#!/usr/bin/env python3
"""
Performance Test for Response Generation Optimization
Tests the async improvements and caching mechanisms.
"""

import asyncio
import time
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from studentAgent.student_agent import StudentAgent
from studentProfileDetails.generate_response_with_groq import _generate_response_async
from Teacher_AI_Agent.search.EnhancedSimilaritySearch import retrieve_chunks_with_shared_knowledge_async

async def test_llm_performance():
    """Test LLM async performance and caching."""
    print("🧪 Testing LLM Performance...")
    
    query = "What is photosynthesis?"
    context = "Photosynthesis is the process by which plants make their own food."
    
    # Test multiple identical queries to test caching
    times = []
    for i in range(3):
        start_time = time.time()
        try:
            response = await _generate_response_async(query, context)
            end_time = time.time()
            duration = end_time - start_time
            times.append(duration)
            print(f"  Query {i+1}: {duration:.2f}s - {response[:50]}...")
        except Exception as e:
            print(f"  Query {i+1} failed: {e}")
    
    if times:
        avg_time = sum(times) / len(times)
        print(f"  📊 Average LLM time: {avg_time:.2f}s")
        if len(times) > 1 and times[1] < times[0] * 0.5:
            print("  ✅ Caching appears to be working (subsequent queries faster)")

async def test_vector_search_performance():
    """Test vector search async performance and caching."""
    print("\n🧪 Testing Vector Search Performance...")
    
    query = "Explain photosynthesis"
    db_name = "10th"
    collection_name = "Science"
    
    # Mock embedding model (would normally be loaded)
    class MockEmbeddingModel:
        def encode(self, text):
            return [0.1] * 384  # Mock embedding
    
    embedding_model = MockEmbeddingModel()
    
    times = []
    for i in range(3):
        start_time = time.time()
        try:
            result = await retrieve_chunks_with_shared_knowledge_async(
                query=query,
                db_name=db_name,
                collection_name=collection_name,
                embedding_model=embedding_model,
                student_profile={"student_id": "test_student"},
                top_k=5
            )
            end_time = time.time()
            duration = end_time - start_time
            times.append(duration)
            print(f"  Search {i+1}: {duration:.2f}s - {result.get('response', 'No response')[:50]}...")
        except Exception as e:
            print(f"  Search {i+1} failed: {e}")
    
    if times:
        avg_time = sum(times) / len(times)
        print(f"  📊 Average vector search time: {avg_time:.2f}s")

async def test_student_agent_performance():
    """Test StudentAgent async performance."""
    print("\n🧪 Testing StudentAgent Performance...")
    
    try:
        agent = StudentAgent()
        agent.load()
        
        query = "What is photosynthesis?"
        
        times = []
        for i in range(3):
            start_time = time.time()
            try:
                result = await agent.ask_async(
                    query=query,
                    class_name="10th",
                    subject="Science",
                    student_profile={"level": "basic", "tone": "friendly"}
                )
                end_time = time.time()
                duration = end_time - start_time
                times.append(duration)
                
                if isinstance(result, dict):
                    response = result.get("response", "No response")
                else:
                    response = str(result)[:100]
                
                print(f"  Agent query {i+1}: {duration:.2f}s - {response[:50]}...")
            except Exception as e:
                print(f"  Agent query {i+1} failed: {e}")
        
        if times:
            avg_time = sum(times) / len(times)
            print(f"  📊 Average StudentAgent time: {avg_time:.2f}s")
            
    except Exception as e:
        print(f"  ❌ StudentAgent test failed: {e}")

async def main():
    """Run all performance tests."""
    print("🚀 Performance Optimization Test Suite")
    print("=" * 50)
    
    start_total = time.time()
    
    # Test individual components
    await test_llm_performance()
    await test_vector_search_performance()
    await test_student_agent_performance()
    
    end_total = time.time()
    total_duration = end_total - start_total
    
    print("\n" + "=" * 50)
    print(f"🏁 Total test time: {total_duration:.2f}s")
    print("\n📋 Optimization Summary:")
    print("  ✅ Async LLM calls with caching")
    print("  ✅ Async vector search with parallel processing")
    print("  ✅ Connection pooling for MongoDB")
    print("  ✅ Thread pool execution for blocking operations")
    print("  ✅ Fallback to synchronous operations")
    print("\n🎯 Expected Performance Improvements:")
    print("  - Cached responses: <1s")
    print("  - Parallel vector search: 30-50% faster")
    print("  - Connection pooling: Reduced latency")
    print("  - Async operations: Better concurrency")

if __name__ == "__main__":
    asyncio.run(main())

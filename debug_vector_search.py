#!/usr/bin/env python3
"""
Debug script to check vector search configuration and document structure
"""

import os
import sys
from pymongo import MongoClient

# Add the project root to Python path
sys.path.append('/Users/macbook/Desktop/langchain_adk')

def main():
    # Connect to MongoDB
    MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
    client = MongoClient(MONGODB_URI)
    db = client['teacher_ai']
    
    print("=== Vector Search Debug ===")
    
    # Check the 10.Science collection
    collection = db['10.Science']
    
    # Get document count
    total_docs = collection.count_documents({})
    docs_with_embeddings = collection.count_documents({"embedding": {"$exists": True}})
    print(f"Collection: 10.Science")
    print(f"Total documents: {total_docs}")
    print(f"Documents with embeddings: {docs_with_embeddings}")
    
    # Sample a document to check structure
    sample = collection.find_one({})
    if sample:
        print(f"\nSample document structure:")
        print(f"Top-level keys: {list(sample.keys())}")
        
        if 'embedding' in sample:
            print(f"Embedding type: {type(sample['embedding'])}")
            if isinstance(sample['embedding'], dict):
                print(f"Embedding keys: {list(sample['embedding'].keys())}")
                if 'vector' in sample['embedding']:
                    vector = sample['embedding']['vector']
                    print(f"Vector type: {type(vector)}")
                    if isinstance(vector, list):
                        print(f"Vector length: {len(vector)}")
                        print(f"First 5 values: {vector[:5]}")
    
    # Check search indexes
    try:
        print(f"\nSearch indexes:")
        indexes = collection.list_search_indexes()
        for idx in indexes:
            print(f"  Index: {idx}")
    except Exception as e:
        print(f"Error listing indexes: {e}")
    
    # Try a simple vector search
    print(f"\nTesting vector search...")
    try:
        # Create a dummy query vector (same dimension as expected)
        dummy_vector = [0.0] * 384  # Common embedding dimension
        
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding.vector",
                    "queryVector": dummy_vector,
                    "numCandidates": 10,
                    "limit": 5
                }
            },
            {
                "$project": {
                    "chunk_text": "$chunk.text",
                    "score": {"$meta": "vectorSearchScore"},
                    "unique_id": "$document.doc_unique_id"
                }
            }
        ]
        
        results = list(collection.aggregate(pipeline))
        print(f"Vector search returned {len(results)} results")
        
        if results:
            print(f"First result sample:")
            first = results[0]
            print(f"  Keys: {list(first.keys())}")
            if 'chunk_text' in first:
                text = first['chunk_text']
                print(f"  Text preview: {text[:100]}...")
            if 'score' in first:
                print(f"  Score: {first['score']}")
        
    except Exception as e:
        print(f"Vector search failed: {e}")
    
    client.close()

if __name__ == "__main__":
    main()

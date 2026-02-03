"""
Main entry point for terminal use of EmbeddingStoreAgent and RetrieverAgent.

These agents are passive and only execute when explicitly called.
Perfect for use in REST APIs - just import and call methods as needed.

Example for REST API:
    from Teacher_AI_Agent import EmbeddingStoreAgent, RetrieverAgent
    
    # In your FastAPI route:
    @app.post("/store_embeddings")
    async def store_embeddings(file_paths: List[str], db_name: str, collection_name: str):
        agent = EmbeddingStoreAgent()
        return agent.store_embeddings(file_paths, db_name, collection_name)
    
    @app.post("/query")
    async def query(query: str, db_name: str, collection_name: str):
        agent = RetrieverAgent()
        return agent.chunk_retriever(query, db_name, collection_name)
"""

import logging
from Teacher_AI_Agent.agent.embedding_store_agent import EmbeddingStoreAgent
from Teacher_AI_Agent.agent.retriever_agent import RetrieverAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    """
    Terminal-based example usage of EmbeddingStoreAgent and RetrieverAgent.
    Agents are passive - they only execute when methods are called.
    """
    print("🚀 LangChain ADK - Teacher AI Agent Demo (Terminal Mode)\n")
    
    # Initialize agents (passive - no execution on init)
    print("📦 Initializing agents...")
    embedding_agent = EmbeddingStoreAgent()
    retriever_agent = RetrieverAgent()
    print("✅ Agents initialized (ready to use)\n")
    
    # Configuration - UPDATE THESE FOR YOUR USE CASE
    class_ = "10th"
    subject = "Science"
    # file_paths = ["/path/to/your/file.pdf"]  # Uncomment and update with your file paths
    
    # Example 1: Store embeddings (commented out - uncomment when you have valid file paths)
    # print("\n" + "="*60)
    # print("📦 Example 1: Storing Embeddings in Atlas")
    # print("="*60)
    # 
    # try:
    #     summary = embedding_agent.store_embeddings(
    #         file_paths=file_paths,
    #         db_name=class_,
    #         collection_name=subject,
    #         original_filenames=None
    #     )
    #     print(f"\n✅ Successfully stored embeddings!")
    #     print(f"   - Total chunks: {summary['num_chunks']}")
    #     print(f"   - New chunks inserted: {summary['inserted_chunks']}")
    #     print(f"   - Files processed: {len(summary['file_names'])}")
    # except Exception as e:
    #     print(f"❌ Error storing embeddings: {e}")
    #     return
    
    # Example 2: Retrieve and generate response
    print("\n" + "="*60)
    print("🔍 Example 2: Retrieving Information and Generating Response")
    print("="*60)
    
    # Query loop
    print("\nEntering query loop (type 'exit' or 'quit' to stop)...")
    while True:
        try:
            query = input("\n🔍 Enter your search query: ").strip()
            if query.lower() in ["exit", "quit"]:
                print("Exiting query loop.")
                break
            
            if not query:
                print("Please enter a valid query.")
                continue
            
            # Agent only executes when this method is called
            response = retriever_agent.chunk_retriever(
                query=query,
                db_name=class_,
                collection_name=subject
            )
            
            print("\n" + "-"*60)
            print("📝 LLM Response:")
            print("-"*60)
            print(response)
            print("-"*60)
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Exiting.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()

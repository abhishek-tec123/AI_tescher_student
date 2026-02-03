import logging
from embaddings.VectorStoreInAtls import create_vector_and_store_in_atlas
from search.SimilaritySearch import retrieve_and_generate_llm_response
from langchain_huggingface import HuggingFaceEmbeddings
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from model_cache import model_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# -----------------------------
# DB/Collection Mapping Utility
# -----------------------------
def map_to_db_and_collection(class_: str, subject: str):
    db_name = class_.strip().lower()
    collection_name = subject.strip()
    return db_name, collection_name

def load_embedding_model():
    logger.info("[*] Loading embedding model...")
    model = model_cache.get_embedding_model("sentence-transformers/all-MiniLM-L6-v2")
    logger.info("[+] Embedding model loaded.")
    return model

def main():
    # Setup
    class_ = "10th"
    subject = "Science"
    file_inputs = ["/Users/abhishek/Desktop/tutorAi/data/class12/lech2dd"]
    db_name, collection_name = map_to_db_and_collection(class_, subject)

    # Load model once
    embedding_model = load_embedding_model()

    # Create vector and store
    # logger.info("Creating and storing vectors...")
    # create_vector_and_store_in_atlas(
    #     file_inputs=file_inputs,
    #     db_name=db_name,
    #     collection_name=collection_name,
    #     embedding_model=embedding_model
    # )

    # Query loop
    print("\nEntering query loop (type 'exit' or 'quit' to stop)...")
    while True:
        try:
            query = input("\n🔍 Enter your search query: ").strip()
            if query.lower() in ["exit", "quit"]:
                print("Exiting query loop.")
                break

            response = retrieve_and_generate_llm_response(
                query=query,
                db_name=db_name,
                collection_name=collection_name,
                embedding_model=embedding_model
            )
            print("\n--- LLM Response ---")
            print(response)
        except KeyboardInterrupt:
            print("\nInterrupted. Exiting.")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
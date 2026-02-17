import os
import json
import logging
from typing import List
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from langchain_huggingface import HuggingFaceEmbeddings
from embaddings.runForEmbeding import get_vectors_and_details

# ----------------------------
# Configure Logging
# ----------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ----------------------------
# Load .env
# ----------------------------
load_dotenv()

# ----------------------------
# MongoDB Utility Functions
# ----------------------------
def insert_chunks_to_db(embedding_json, collection):
    operations = []

    for entry in embedding_json:
        # ✅ FIX: unique_chunk_id is nested
        unique_chunk_id = entry["chunk"]["unique_chunk_id"]

        operations.append(
            UpdateOne(
                {"chunk.unique_chunk_id": unique_chunk_id},
                {"$setOnInsert": entry},
                upsert=True
            )
        )

    if not operations:
        return 0

    result = collection.bulk_write(operations, ordered=False)
    inserted_count = result.upserted_count

    logger.info(
        f"Bulk upserted {len(operations)} chunks. "
        f"Inserted new: {inserted_count}, matched existing: {result.matched_count}"
    )

    return inserted_count


def get_mongo_collection(db_name: str = None, collection_name: str = None):
    """Return a MongoDB collection object using provided or environment values."""
    MONGODB_URI = os.environ.get("MONGODB_URI")
    if not MONGODB_URI:
        raise ValueError("Please set MONGODB_URI environment variable.")

    db_name = db_name or os.environ.get("DB_NAME")
    collection_name = collection_name or os.environ.get("COLLECTION_NAME")

    if not db_name or not collection_name:
        raise ValueError(
            "DB name and Collection name must be provided either as arguments or in environment variables."
        )

    client = MongoClient(MONGODB_URI)
    logger.info(f"Connected to MongoDB: {db_name}.{collection_name}")
    return client[db_name][collection_name], collection_name


import random
import string

def generate_subject_agent_id():
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"agent_{random_part}"
# ----------------------------
# Main Processing Function
# ----------------------------
def create_vector_and_store_in_atlas(
    file_inputs,
    db_name,
    collection_name,
    embedding_model,
    original_filenames,
    agent_metadata: dict | None = None,
    subject_agent_id: str | None = None, 
):
    if embedding_model is None:
        raise ValueError("No embedding model provided. This function requires a pre-loaded embedding model.")

    embedding_model_name = getattr(embedding_model, "model_name", "provided_model")

    logger.info("Generating vectors and extracting metadata from files...")
    vector, doc_ids = get_vectors_and_details(
        file_inputs=file_inputs,
        embedding_model=embedding_model,
        original_filenames=original_filenames,
        subject_agent_id=subject_agent_id,  # ✅ pass down
        agent_metadata=agent_metadata,
    )

    logger.info(f"Generated embeddings for {len(vector)} chunks")

    # ✅ FIX: Only generate for NEW agent
    if subject_agent_id is None:
        subject_agent_id = generate_subject_agent_id()
        logger.info(f"Generated new subject_agent_id: {subject_agent_id}")
    else:
        logger.info(f"Using existing subject_agent_id: {subject_agent_id}")

    for entry in vector:
        entry["subject_agent_id"] = subject_agent_id
    # ✅ Attach agent metadata safely
    if agent_metadata:
        logger.info(f"Attaching agent metadata: {agent_metadata}")
        for entry in vector:
            entry["agent_metadata"] = agent_metadata

    collection, used_collection_name = get_mongo_collection(db_name, collection_name)

    logger.info("Inserting chunks into MongoDB...")
    inserted_count = insert_chunks_to_db(vector, collection)

    logger.info(
        f"✅ Inserted {inserted_count} new chunks into MongoDB collection '{used_collection_name}'."
    )

    # ✅ FIX: file_name is nested under document
    unique_file_names = list({
        e["document"]["file_name"]
        for e in vector
        if e.get("document") and e["document"].get("file_name")
    })

    summary = {
        "subject_agent_id": subject_agent_id,
        "num_chunks": len(vector),
        "inserted_chunks": inserted_count,
        "file_names": unique_file_names,
        "embedding_model": embedding_model_name,
        "doc_unique_ids": doc_ids,
        "original_filenames": original_filenames,
        "agent_metadata": agent_metadata,
        "vector_unique_ids": [c["chunk"]["unique_chunk_id"] for c in vector],
    }

    logger.info("Summary of operation:")
    logger.info(json.dumps(summary, indent=2, ensure_ascii=False))

    return summary


# ----------------------------
# Example usage (uncomment to run directly)
# ----------------------------
# if __name__ == "__main__":
#     files = ["doc1.txt", "doc2.txt"]
#     create_vector_and_store_in_atlas(files, db_name="myDatabase", collection_name="myCollection")


# ----------------------------
# Entry Point
# ----------------------------
# if __name__ == "__main__":
#     file_inputs = ["/Users/abhishek/Desktop/tutorAi/data/jesc1dd"]
#     create_vector_and_store_in_atlas(file_inputs)

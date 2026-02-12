# update_agent_data.py
import os
from typing import List, Optional
from fastapi import UploadFile, HTTPException
from pymongo import MongoClient

async def update_agent_data(
    subject_agent_id: str,
    class_: Optional[str],
    subject: Optional[str],
    agent_type: Optional[str],
    agent_name: Optional[str],
    description: Optional[str],
    teaching_tone: Optional[str],
    files: Optional[List[UploadFile]],
    embedding_model,
    create_vectors_service,
):
    """Update agent metadata and optionally replace documents."""

    MONGODB_URI = os.environ.get("MONGODB_URI")
    if not MONGODB_URI:
        raise HTTPException(status_code=500, detail="MongoDB URI not configured")

    client = MongoClient(MONGODB_URI)

    found_collection = None
    found_db_name = None
    found_collection_name = None

    # -------------------------------
    # Search agent across all DBs
    # -------------------------------
    for db_name in client.list_database_names():
        if db_name in ["admin", "local", "config"]:
            continue

        db = client[db_name]

        for collection_name in db.list_collection_names():
            collection = db[collection_name]

            existing = collection.find_one({"subject_agent_id": subject_agent_id})
            if existing is not None:
                found_collection = collection
                found_db_name = db_name
                found_collection_name = collection_name
                break

        if found_collection is not None:
            break

    if found_collection is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    # -------------------------------
    # Update agent metadata
    # -------------------------------
    update_fields = {
        k: v for k, v in {
            "agent_metadata.agent_type": agent_type,
            "agent_metadata.agent_name": agent_name,
            "agent_metadata.description": description,
            "agent_metadata.teaching_tone": teaching_tone,
        }.items() if v is not None
    }

    if update_fields:
        found_collection.update_many(
            {"subject_agent_id": subject_agent_id},
            {"$set": update_fields}
        )

    # -------------------------------
    # Replace documents if new files uploaded
    # -------------------------------
    if files:
        summary = await create_vectors_service(
            class_=found_db_name,
            subject=found_collection_name,
            files=files,
            embedding_model=embedding_model,
            agent_metadata={
                "agent_type": agent_type,
                "agent_name": agent_name,
                "description": description,
                "teaching_tone": teaching_tone,
            },
            subject_agent_id=subject_agent_id,
        )

        if not summary:
            raise HTTPException(status_code=500, detail="Failed to create new embeddings")

        delete_result = found_collection.delete_many(
            {
                "subject_agent_id": subject_agent_id,
                "chunk.unique_chunk_id": {"$nin": summary["vector_unique_ids"]}
            }
        )

        return {
            "message": "Agent updated and documents replaced successfully",
            "new_chunks": summary.get("num_chunks", 0),
            "deleted_old_chunks": delete_result.deleted_count,
            "subject_agent_id": subject_agent_id
        }

    return {
        "message": "Agent metadata updated successfully",
        "subject_agent_id": subject_agent_id
    }

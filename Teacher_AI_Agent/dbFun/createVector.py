import os
import tempfile
from typing import List, Optional
from fastapi import UploadFile, HTTPException

from embaddings.VectorStoreInAtls import create_vector_and_store_in_atlas
from embaddings.utility import generate_subject_agent_id

def map_to_db_and_collection(class_: str, subject: str):
    return class_.strip(), subject.strip()


async def create_vectors_service(
    class_: str,
    subject: str,
    files: Optional[List[UploadFile]] = None,
    embedding_model=None,
    agent_metadata: dict | None = None,
    subject_agent_id: str | None = None,
):
    db_name, collection_name = map_to_db_and_collection(class_, subject)

    # Handle: no files OR empty list
    if not files:
        return {
            "status": "skipped",
            "message": "No files provided",
            "db": db_name,
            "collection": collection_name,
        }

    file_inputs: List[str] = []
    original_filenames: List[str] = []

    for file in files:
        # Extra safety: skip invalid uploads
        if not file or not file.filename:
            continue

        suffix = os.path.splitext(file.filename)[-1] or ".tmp"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()

            # Skip empty file content
            if not content:
                continue

            tmp.write(content)
            file_inputs.append(tmp.name)
            original_filenames.append(file.filename)

    # After filtering, still nothing usable
    if not file_inputs:
        return {
            "status": "skipped",
            "message": "No valid files to process",
            "db": db_name,
            "collection": collection_name,
        }

    # ✅ Generate ID only if new agent
    if not subject_agent_id:
        subject_agent_id = generate_subject_agent_id()

    return create_vector_and_store_in_atlas(
        subject_agent_id=subject_agent_id,
        file_inputs=file_inputs,
        db_name=db_name,
        collection_name=collection_name,
        embedding_model=embedding_model,
        original_filenames=original_filenames,
        agent_metadata=agent_metadata,
    )

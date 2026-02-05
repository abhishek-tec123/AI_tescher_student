import os
import tempfile
from typing import List
from fastapi import UploadFile
from embaddings.VectorStoreInAtls import create_vector_and_store_in_atlas

def map_to_db_and_collection(class_: str, subject: str):
    return class_.strip(), subject.strip()

async def create_vectors_service(
    class_: str,
    subject: str,
    files: List[UploadFile],
    embedding_model
):
    db_name, collection_name = map_to_db_and_collection(class_, subject)

    file_inputs = []
    original_filenames = []

    for file in files:
        suffix = os.path.splitext(file.filename)[-1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            file_inputs.append(tmp.name)
            original_filenames.append(file.filename)

    return create_vector_and_store_in_atlas(
        file_inputs=file_inputs,
        db_name=db_name,
        collection_name=collection_name,
        embedding_model=embedding_model,
        original_filenames=original_filenames
    )

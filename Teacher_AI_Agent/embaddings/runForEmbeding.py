from langchain_huggingface import HuggingFaceEmbeddings
from embaddings.utility import (
    load_documents,
    split_documents,
    embed_chunks,
    build_embedding_json_for_db
)

def get_vectors_and_details(
    file_inputs,
    embedding_model=None,
    original_filenames=None,
    subject_agent_id: str | None = None,
    agent_metadata: dict | None = None
):
    # 📂 Step 1: Load documents
    print("[*] Loading documents...")
    docs = load_documents(file_inputs)

    # 📏 Step 2: Split documents
    print(f"[*] Splitting {len(docs)} documents into chunks...")
    chunks = split_documents(docs, chunk_size=1000, chunk_overlap=200)

    # 🤖 Step 3: Embed chunks
    if embedding_model is None:
        raise ValueError("No embedding model provided.")
    model_name = getattr(embedding_model, 'model_name', 'provided_model')

    print(f"[*] Embedding {len(chunks)} chunks...")
    embeddings = embed_chunks(chunks, embedding_model)

    # 🧱 Step 4: Build JSON for DB
    embedding_json, doc_ids = build_embedding_json_for_db(
        chunks, embeddings, embedding_model_name=model_name, original_filenames=original_filenames
    )

    # ✅ Step 5: Attach subject_agent_id and agent_metadata if provided
    if subject_agent_id:
        for entry in embedding_json:
            entry["subject_agent_id"] = subject_agent_id
    if agent_metadata:
        for entry in embedding_json:
            entry["agent_metadata"] = agent_metadata

    print(f"[✅] Processed {len(embedding_json)} embeddings from {len(doc_ids)} documents.")
    return embedding_json, doc_ids

# # Example usage
# if __name__ == "__main__":
#     import json
#     file_inputs = [
#         "/Users/abhishek/Desktop/tutorAi/data/jemh1dd/jemh1a1.pdf",
#         "/Users/abhishek/Desktop/tutorAi/data/jemh1dd/jemh1a2.pdf"
#     ]
#     vector = get_vectors_and_details(file_inputs)
#     print(json.dumps(vector, indent=3, ensure_ascii=False))  # Just for visualization

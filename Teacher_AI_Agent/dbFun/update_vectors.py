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
    global_prompt_enabled: bool,
    global_rag_enabled: bool,
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
            "agent_metadata.global_prompt_enabled": global_prompt_enabled,
            "agent_metadata.global_rag_enabled": global_rag_enabled,
        }.items() if v is not None or k in [
            "agent_metadata.global_prompt_enabled",
            "agent_metadata.global_rag_enabled"
        ]
    }

    if update_fields:
        found_collection.update_many(
            {"subject_agent_id": subject_agent_id},
            {"$set": update_fields}
        )
    
    # ✅ Auto-enable/disable shared documents based on global_rag_enabled setting
    auto_result = {"auto_enabled_shared_documents": 0, "auto_disabled_shared_documents": 0, "shared_documents": []}
    
    try:
        from Teacher_AI_Agent.dbFun.shared_knowledge import shared_knowledge_manager
        import logging
        logger = logging.getLogger(__name__)
        
        # Get all available shared documents
        shared_docs_result = shared_knowledge_manager.list_shared_documents()
        
        if shared_docs_result.get("status") == "success" and shared_docs_result.get("documents"):
            if global_rag_enabled:
                # Enable shared documents for this agent
                enabled_count = 0
                for doc in shared_docs_result["documents"]:
                    try:
                        # Get agent details from updated metadata or existing data
                        agent_doc = found_collection.find_one({"subject_agent_id": subject_agent_id})
                        agent_metadata = agent_doc.get("agent_metadata", {}) if agent_doc else {}
                        agent_name_from_db = agent_metadata.get("agent_name", "")
                        class_name_from_db = found_db_name
                        subject_name_from_db = found_collection_name
                        
                        success = shared_knowledge_manager.enable_document_for_agent(
                            doc["document_id"], 
                            subject_agent_id,
                            agent_name=agent_name_from_db,
                            class_name=class_name_from_db,
                            subject=subject_name_from_db
                        )
                        if success:
                            enabled_count += 1
                            logger.info(f"✅ Auto-enabled shared document '{doc['document_name']}' for agent {subject_agent_id}")
                    except Exception as e:
                        logger.warning(f"Failed to enable document {doc['document_id']} for agent {subject_agent_id}: {e}")
                
                # Get the updated list of enabled documents
                try:
                    enabled_docs = shared_knowledge_manager.get_agent_enabled_documents(subject_agent_id)
                    auto_result["shared_documents"] = enabled_docs
                except Exception as e:
                    logger.warning(f"Failed to get enabled documents list: {e}")
                    auto_result["shared_documents"] = []
                
                if enabled_count > 0:
                    auto_result["auto_enabled_shared_documents"] = enabled_count
                    auto_result["shared_documents_status"] = "enabled"
                    
            else:
                # Disable shared documents for this agent
                disabled_count = 0
                for doc in shared_docs_result["documents"]:
                    try:
                        # Check if this agent is using this document
                        if any(agent.get("agent_id") == subject_agent_id for agent in doc.get("used_by_agents", [])):
                            success = shared_knowledge_manager.disable_document_for_agent(
                                doc["document_id"], 
                                subject_agent_id
                            )
                            if success:
                                disabled_count += 1
                                logger.info(f"✅ Auto-disabled shared document '{doc['document_name']}' for agent {subject_agent_id}")
                    except Exception as e:
                        logger.warning(f"Failed to disable document {doc['document_id']} for agent {subject_agent_id}: {e}")
                
                # Get the updated list of enabled documents (should be empty)
                try:
                    enabled_docs = shared_knowledge_manager.get_agent_enabled_documents(subject_agent_id)
                    auto_result["shared_documents"] = enabled_docs
                except Exception as e:
                    logger.warning(f"Failed to get enabled documents list: {e}")
                    auto_result["shared_documents"] = []
                
                if disabled_count > 0:
                    auto_result["auto_disabled_shared_documents"] = disabled_count
                    auto_result["shared_documents_status"] = "disabled"
                    
    except Exception as e:
        logger.warning(f"Failed to auto-enable/disable shared documents for agent {subject_agent_id}: {e}")
        auto_result["shared_documents_status"] = "error"

    # Add full prompt information to response
    prompt_info = {
        "enabled": global_prompt_enabled,
        "global_prompt_content": None,
        "full_prompt": None
    }
    
    if global_prompt_enabled:
        try:
            from studentProfileDetails.global_prompts import get_highest_priority_enabled_prompt
            from studentProfileDetails.prompt_templates import build_teacher_prompt
            
            global_prompt = get_highest_priority_enabled_prompt()
            if global_prompt:
                prompt_info["global_prompt_content"] = global_prompt.get("content", "")
                
                # Build the full prompt that will be used by the agent
                sample_student_profile = {
                    "level": "intermediate",
                    "tone": "friendly", 
                    "learning_style": "step-by-step",
                    "response_length": "long",
                    "include_example": True,
                    "common_mistakes": []
                }
                
                full_prompt = build_teacher_prompt(
                    student_profile=sample_student_profile,
                    class_name=found_db_name or "Sample Class",
                    subject=found_collection_name,
                    confusion_type="NO_CONFUSION",
                    session_context="Previous Q: What is biology?\nPrevious A: Biology is the study of living organisms.",
                    current_query="What is photosynthesis?",
                    agent_metadata={"global_prompt_enabled": True}
                )
                
                prompt_info["full_prompt"] = full_prompt
        except ImportError:
            # If modules are not available, skip
            pass
    else:
        # When disabled, show the regular prompt without global content
        try:
            from studentProfileDetails.prompt_templates import build_teacher_prompt
            
            sample_student_profile = {
                "level": "intermediate",
                "tone": "friendly",
                "learning_style": "step-by-step", 
                "response_length": "long",
                "include_example": True,
                "common_mistakes": []
            }
            
            full_prompt = build_teacher_prompt(
                student_profile=sample_student_profile,
                class_name=found_db_name or "Sample Class",
                subject=found_collection_name,
                confusion_type="NO_CONFUSION",
                session_context="Previous Q: What is biology?\nPrevious A: Biology is the study of living organisms.",
                current_query="What is photosynthesis?",
                agent_metadata={"global_prompt_enabled": False}
            )
            
            prompt_info["full_prompt"] = full_prompt
        except ImportError:
            # If modules are not available, skip
            pass
    
    auto_result["prompt"] = prompt_info

    # Log activity for agent update
    try:
        from studentProfileDetails.activity_tracker import log_agent_updated
        
        # Determine what was changed
        changes = []
        if agent_type:
            changes.append("agent_type")
        if agent_name:
            changes.append("agent_name")
        if description:
            changes.append("description")
        if teaching_tone:
            changes.append("teaching_tone")
        if files:
            changes.append("documents")
        # Always include global settings in changes since they're always updated
        changes.extend(["global_prompt_enabled", "global_rag_enabled"])
        
        # Get the agent name for logging
        agent_doc = found_collection.find_one({"subject_agent_id": subject_agent_id})
        agent_metadata = agent_doc.get("agent_metadata", {}) if agent_doc else {}
        agent_name_for_log = agent_metadata.get("agent_name") or agent_name or found_collection_name
        
        if changes:
            log_agent_updated(
                agent_id=subject_agent_id,
                agent_name=agent_name_for_log,
                subject=found_collection_name,
                class_name=found_db_name,
                changes=changes
            )
            print(f"✅ Logged agent update activity for {subject_agent_id}")
        
    except Exception as e:
        print(f"❌ Failed to log agent update activity: {e}")

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

        # Check if summary contains vector_unique_ids (only present when files are actually processed)
        if "vector_unique_ids" not in summary:
            # No new vectors were created, nothing to delete
            return {
                "message": "Agent updated but no new documents were processed",
                "new_chunks": 0,
                "deleted_old_chunks": 0,
                "subject_agent_id": subject_agent_id,
                **auto_result
            }

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
            "subject_agent_id": subject_agent_id,
            **auto_result
        }

    return {
        "message": "Agent metadata updated successfully",
        "subject_agent_id": subject_agent_id,
        **auto_result
    }

async def delete_vectors(subject_agent_id: str):
    """
    Delete all vector documents in MongoDB for a given subject_agent_id.
    """
    MONGODB_URI = os.environ.get("MONGODB_URI")
    if not MONGODB_URI:
        raise HTTPException(status_code=500, detail="MongoDB URI not configured")

    client = MongoClient(MONGODB_URI)

    deleted_count_total = 0

    # Search all databases for the agent
    for db_name in client.list_database_names():
        if db_name in ["admin", "local", "config"]:
            continue
        db = client[db_name]

        for collection_name in db.list_collection_names():
            collection = db[collection_name]

            delete_result = collection.delete_many({"subject_agent_id": subject_agent_id})
            deleted_count_total += delete_result.deleted_count

    print(f"Deleted {deleted_count_total} vector documents for agent {subject_agent_id}")
    return {
        "deleted": True,
        "deleted_chunks": deleted_count_total
    }

async def delete_agent_data(subject_agent_id: str) -> dict:
    """
    Delete an agent and all its vectors/documents from MongoDB.
    """
    deleted_chunks = await delete_vectors(subject_agent_id)

    if deleted_chunks == 0:
        return {"deleted": False, "deleted_chunks": 0}

    return {"deleted": True, "deleted_chunks": deleted_chunks, "subject_agent_id": subject_agent_id}
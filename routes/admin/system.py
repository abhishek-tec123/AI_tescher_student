"""
Admin system configuration routes
Handles shared knowledge documents, agent settings, and system configuration
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, Request, HTTPException
import os
import logging
from studentProfileDetails.auth.dependencies import require_role
from pydantic import BaseModel
from Teacher_AI_Agent.dbFun.shared_knowledge import shared_knowledge_manager

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# =====================================================
# SHARED KNOWLEDGE DOCUMENTS MANAGEMENT
# =====================================================

class SharedDocumentRequest(BaseModel):
    document_name: str
    description: str = ""

class AgentDocumentRequest(BaseModel):
    agent_id: str
    agent_name: str = ""
    class_name: str = ""
    subject: str = ""

class AgentGlobalSettingsRequest(BaseModel):
    agent_id: str
    global_prompt_enabled: bool = False
    global_rag_enabled: bool = False

@router.post("/shared-knowledge/upload")
async def upload_shared_document(
    request: Request,
    document_name: str = Form(...),
    description: str = Form(""),
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(require_role("admin"))
):
    """Upload shared knowledge documents accessible by all agents."""
    try:
        result = shared_knowledge_manager.upload_shared_document(
            files=files,
            document_name=document_name,
            description=description,
            embedding_model=request.app.state.embedding_model
        )
        return result
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shared-knowledge")
def list_shared_documents(current_user: dict = Depends(require_role("admin"))):
    """List all shared knowledge documents with their status and usage."""
    return shared_knowledge_manager.list_shared_documents()

@router.delete("/shared-knowledge/{document_id}")
def delete_shared_document(
    document_id: str,
    current_user: dict = Depends(require_role("admin"))
):
    """Delete a shared knowledge document."""
    try:
        return shared_knowledge_manager.delete_shared_document(document_id)
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=e.status_code if hasattr(e, 'status_code') else 500, detail=str(e))

@router.post("/shared-knowledge/{document_id}/enable")
def enable_document_for_agent(
    document_id: str,
    payload: AgentDocumentRequest,
    current_user: dict = Depends(require_role("admin"))
):
    """Enable a shared document for a specific agent."""
    try:
        return shared_knowledge_manager.enable_document_for_agent(
            document_id=document_id,
            agent_id=payload.agent_id,
            agent_name=payload.agent_name,
            class_name=payload.class_name,
            subject=payload.subject
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=e.status_code if hasattr(e, 'status_code') else 500, detail=str(e))

@router.post("/shared-knowledge/{document_id}/disable")
def disable_document_for_agent(
    document_id: str,
    payload: AgentDocumentRequest,
    current_user: dict = Depends(require_role("admin"))
):
    """Disable a shared document for a specific agent."""
    try:
        return shared_knowledge_manager.disable_document_for_agent(
            document_id=document_id,
            agent_id=payload.agent_id
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=e.status_code if hasattr(e, 'status_code') else 500, detail=str(e))

@router.get("/shared-knowledge/agent/{agent_id}")
def get_agent_enabled_documents(
    agent_id: str,
    current_user: dict = Depends(require_role("admin"))
):
    """Get all shared documents enabled for a specific agent."""
    return {
        "status": "success",
        "documents": shared_knowledge_manager.get_agent_enabled_documents(agent_id)
    }

@router.get("/global-rag-knowledge")
def list_global_rag_knowledge(current_user: dict = Depends(require_role("admin"))):
    """List all global RAG knowledge including settings and shared documents."""
    try:
        from studentProfileDetails.global_settings import get_global_rag_settings
        
        # Get global RAG settings
        global_settings = get_global_rag_settings()
        
        # Get shared knowledge documents
        shared_documents_result = shared_knowledge_manager.list_shared_documents()
        
        # Prepare response
        response = {
            "status": "success",
            "global_settings": {
                "enabled": global_settings["enabled"],
                "content_length": len(global_settings["content"]) if global_settings["enabled"] else 0,
                "content_preview": global_settings["content"][:200] + "..." if global_settings["enabled"] and len(global_settings["content"]) > 200 else global_settings["content"] if global_settings["enabled"] else "",
                "last_updated": "N/A"  # Could add timestamp tracking if needed
            },
            "shared_documents": {
                "total_documents": shared_documents_result.get("total_documents", 0),
                "total_chunks": sum(doc.get("indexed_chunks", 0) for doc in shared_documents_result.get("documents", [])),
                "total_agents_using": sum(doc.get("used_by_count", 0) for doc in shared_documents_result.get("documents", [])),
                "documents": shared_documents_result.get("documents", [])
            },
            "summary": {
                "total_knowledge_sources": (1 if global_settings["enabled"] else 0) + shared_documents_result.get("total_documents", 0),
                "active_sources": (1 if global_settings["enabled"] else 0) + len([doc for doc in shared_documents_result.get("documents", []) if doc.get("status") == "indexed"]),
                "total_content_size": len(global_settings["content"]) if global_settings["enabled"] else 0
            }
        }
        
        return response
        
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to list global RAG knowledge: {str(e)}")

# =====================================================
# AGENT GLOBAL SETTINGS MANAGEMENT
# =====================================================

@router.post("/agents/{agent_id}/global-settings")
def update_agent_global_settings(
    agent_id: str,
    payload: AgentGlobalSettingsRequest,
    current_user: dict = Depends(require_role("admin"))
):
    """Update global settings for a specific agent."""
    try:
        from Teacher_AI_Agent.dbFun.get_agent_data import get_agent_data
        from pymongo import MongoClient
        
        # Get agent data to find the database and collection
        agent_data = get_agent_data(agent_id)
        if not agent_data:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Update agent metadata with global settings
        mongodb_uri = os.environ.get("MONGODB_URI")
        if not mongodb_uri:
            raise HTTPException(status_code=500, detail="MongoDB URI not configured")
        
        client = MongoClient(mongodb_uri)
        db = client[agent_data["class"]]
        collection = db[agent_data["subject"]]
        
        # Update all documents for this agent with new global settings
        result = collection.update_many(
            {"subject_agent_id": agent_id},
            {
                "$set": {
                    "agent_metadata.global_prompt_enabled": payload.global_prompt_enabled,
                    "agent_metadata.global_rag_enabled": payload.global_rag_enabled
                }
            }
        )
        
        # ✅ Auto-enable/disable shared documents based on new global_rag_enabled setting
        auto_result = {"auto_enabled_shared_documents": 0, "auto_disabled_shared_documents": 0}
        
        try:
            # Get all available shared documents
            shared_docs_result = shared_knowledge_manager.list_shared_documents()
            
            if shared_docs_result.get("status") == "success" and shared_docs_result.get("documents"):
                if payload.global_rag_enabled:
                    # Enable shared documents for this agent
                    enabled_count = 0
                    for doc in shared_docs_result["documents"]:
                        try:
                            # Get agent details from updated payload or agent data
                            agent_name = agent_data.get("agent_metadata", {}).get("agent_name", "")
                            class_name = agent_data.get("class", "")
                            subject_name = agent_data.get("subject", "")
                            
                            success = shared_knowledge_manager.enable_document_for_agent(
                                doc["document_id"], 
                                agent_id,
                                agent_name=agent_name,
                                class_name=class_name,
                                subject=subject_name
                            )
                            if success:
                                enabled_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to enable document {doc['document_id']} for agent {agent_id}: {e}")
                    
                    if enabled_count > 0:
                        auto_result["auto_enabled_shared_documents"] = enabled_count
                        auto_result["shared_documents_status"] = "enabled"
                        
                else:
                    # Disable shared documents for this agent
                    disabled_count = 0
                    for doc in shared_docs_result["documents"]:
                        try:
                            # Check if this agent is using this document
                            if any(agent.get("agent_id") == agent_id for agent in doc.get("used_by_agents", [])):
                                success = shared_knowledge_manager.disable_document_for_agent(
                                    doc["document_id"], 
                                    agent_id
                                )
                                if success:
                                    disabled_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to disable document {doc['document_id']} for agent {agent_id}: {e}")
                    
                    if disabled_count > 0:
                        auto_result["auto_disabled_shared_documents"] = disabled_count
                        auto_result["shared_documents_status"] = "disabled"
                        
        except Exception as e:
            logger.warning(f"Failed to auto-enable/disable shared documents for agent {agent_id}: {e}")
            auto_result["shared_documents_status"] = "error"
        
        return {
            "status": "success",
            "message": f"Updated global settings for agent {agent_id}",
            "matched_documents": result.matched_count,
            "modified_documents": result.modified_count,
            "global_prompt_enabled": payload.global_prompt_enabled,
            "global_rag_enabled": payload.global_rag_enabled,
            **auto_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update agent global settings: {str(e)}")

@router.get("/agents/{agent_id}/global-settings")
def get_agent_global_settings(
    agent_id: str,
    current_user: dict = Depends(require_role("admin"))
):
    """Get current global settings for a specific agent."""
    try:
        from Teacher_AI_Agent.dbFun.get_agent_data import get_agent_data
        
        # Get agent data
        agent_data = get_agent_data(agent_id)
        if not agent_data:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Extract global settings from agent metadata
        agent_metadata = agent_data.get("agent_metadata", {})
        
        return {
            "status": "success",
            "agent_id": agent_id,
            "global_prompt_enabled": agent_metadata.get("global_prompt_enabled", False),
            "global_rag_enabled": agent_metadata.get("global_rag_enabled", False),
            "agent_metadata": agent_metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent global settings: {str(e)}")

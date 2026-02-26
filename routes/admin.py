from fastapi import APIRouter, Depends, UploadFile, File, Form, Request
from studentProfileDetails.agents.mainAgent import (
    get_base_prompt,
    update_base_prompt_handler,
    UpdatePromptRequest,
)
from studentProfileDetails.auth.dependencies import require_role
from studentProfileDetails.managers.admin_manager import AdminManager
from studentProfileDetails.db_utils import StudentManager
from Teacher_AI_Agent.dbFun.collections import list_all_collections
from pydantic import BaseModel
from typing import Optional
from studentProfileDetails.global_settings import (
    get_global_rag_settings,
    enable_global_rag as enable_global_rag_setting,
    disable_global_rag as disable_global_rag_setting
)
from studentProfileDetails.prompt_templates import (
    get_sample_student_profile,
    get_sample_session_context,
    get_fallback_base_prompt,
    create_fallback_prompt_with_rag,
    get_prompt_components_for_response,
    build_teacher_prompt
)
from Teacher_AI_Agent.dbFun.shared_knowledge import shared_knowledge_manager

router = APIRouter()

# Dummy data constants for prompt demonstration
DUMMY_CLASS_NAME = "Sample Class"
DUMMY_SUBJECT = "Sample Subject"
DUMMY_QUERY = "What is photosynthesis?"

class GlobalRagRequest(BaseModel):
    content: str

@router.post("/update-base-prompt")
def update_base_prompt(
    payload: UpdatePromptRequest,
    current_user: dict = Depends(require_role("admin"))
):
    return update_base_prompt_handler(payload)

@router.get("/current-base-prompt")
def get_current_prompt(current_user: dict = Depends(require_role("admin"))):
    return {
        "base_prompt": get_base_prompt()
    }

@router.get("/list-admins")
def list_admins(current_user: dict = Depends(require_role("admin"))):
    """List all admins (admin only)."""
    admin_manager = AdminManager()
    admins = admin_manager.list_admins()
    return {
        "total": len(admins),
        "admins": admins
    }

@router.get("/dashboard-counts")
def get_dashboard_stats(current_user: dict = Depends(require_role("admin"))):
    """Get dashboard statistics: all students, total agents, and total conversations."""
    # Get all students
    student_manager = StudentManager()
    students = student_manager.list_students()
    
    # Get all agents with their conversation counts
    agents_data = list_all_collections()
    total_agents = 0
    total_conversations = 0
    
    if agents_data["status"] == "success":
        agents = agents_data.get("agents", [])
        total_agents = len(agents)
        total_conversations = sum(agent.get("total_conversations", 0) for agent in agents)
    
    return {
        "students": {
            "total": len(students)
        },
        "agents": {
            "total": total_agents,
            "total_conversations": total_conversations
        }
    }

# Global prompt management routes
@router.post("/global-prompt/enable")
def enable_global_rag(
    payload: GlobalRagRequest,
    current_user: dict = Depends(require_role("admin"))
):
    """Enable global RAG with custom content and show complete prompt examples."""
    enable_global_rag_setting(payload.content)
    
    settings = get_global_rag_settings()
    
    # Import the build_teacher_prompt function to create realistic full prompts
    try:
        # Get sample data from templates
        sample_student_profile = get_sample_student_profile()
        sample_session_context = get_sample_session_context()
        
        # Build the complete base prompt (without RAG)
        base_prompt = build_teacher_prompt(
            student_profile=sample_student_profile,
            class_name=DUMMY_CLASS_NAME,
            subject=DUMMY_SUBJECT,
            confusion_type="NO_CONFUSION",
            session_context=sample_session_context,
            current_query=DUMMY_QUERY,
            agent_metadata=None
        )
        
        # Build the complete enhanced prompt (with RAG)
        enhanced_prompt = build_teacher_prompt(
            student_profile=sample_student_profile,
            class_name=DUMMY_CLASS_NAME,
            subject=DUMMY_SUBJECT,
            confusion_type="NO_CONFUSION",
            session_context=sample_session_context,
            current_query=DUMMY_QUERY,
            agent_metadata=None
        )
            
    except Exception:
        # Fallback to modular prompts if import fails
        base_prompt = get_fallback_base_prompt()
        enhanced_prompt = create_fallback_prompt_with_rag(settings["content"]) if settings["enabled"] else None
    
    return {
        "status": "success",
        "message": "Global RAG enabled successfully",
        "enabled": True,
        "content_preview": settings["content"][:200] + "..." if len(settings["content"]) > 200 else settings["content"],
        "rag_content_length": len(settings["content"]),
        "prompts": {
            "base_prompt": base_prompt,
            "rag_enhanced_prompt": enhanced_prompt
        },
        "prompt_components": get_prompt_components_for_response()
    }

@router.post("/global-prompt/disable")
def disable_global_rag(current_user: dict = Depends(require_role("admin"))):
    """Disable global RAG and show complete prompt examples."""
    disable_global_rag_setting()
    
    # Import the build_teacher_prompt function to create realistic full prompts
    try:
        # Get sample data from templates
        sample_student_profile = get_sample_student_profile()
        sample_session_context = get_sample_session_context()
        
        # Build the complete base prompt (without RAG)
        base_prompt = build_teacher_prompt(
            student_profile=sample_student_profile,
            class_name=DUMMY_CLASS_NAME,
            subject=DUMMY_SUBJECT,
            confusion_type="NO_CONFUSION",
            session_context=sample_session_context,
            current_query=DUMMY_QUERY,
            agent_metadata=None
        )
            
    except Exception:
        # Fallback to modular prompts if import fails
        base_prompt = get_fallback_base_prompt()
    
    return {
        "status": "success",
        "message": "Global RAG disabled successfully",
        "enabled": False,
        "rag_content_length": 0,
        "prompts": {
            "base_prompt": base_prompt,
            "rag_enhanced_prompt": None
        },
        "prompt_components": get_prompt_components_for_response()
    }

@router.get("/global-prompt/status")
def get_global_rag_status(current_user: dict = Depends(require_role("admin"))):
    """Get current global RAG status and content with full prompt examples."""
    settings = get_global_rag_settings()
    
    # Import the build_teacher_prompt function to create realistic full prompts
    try:
        # Get sample data from templates
        sample_student_profile = get_sample_student_profile()
        sample_session_context = get_sample_session_context()
        
        # Build the complete base prompt (without RAG)
        base_prompt = build_teacher_prompt(
            student_profile=sample_student_profile,
            class_name=DUMMY_CLASS_NAME,
            subject=DUMMY_SUBJECT,
            confusion_type="NO_CONFUSION",
            session_context=sample_session_context,
            current_query=DUMMY_QUERY,
            agent_metadata=None
        )
        
        # Build the complete enhanced prompt (with RAG if enabled)
        if settings["enabled"]:
            enhanced_prompt = build_teacher_prompt(
                student_profile=sample_student_profile,
                class_name=DUMMY_CLASS_NAME,
                subject=DUMMY_SUBJECT,
                confusion_type="NO_CONFUSION",
                session_context=sample_session_context,
                current_query=DUMMY_QUERY,
                agent_metadata=None
            )
        else:
            enhanced_prompt = None
            
    except ImportError:
        # Fallback to modular prompts if import fails
        base_prompt = get_fallback_base_prompt()
        enhanced_prompt = create_fallback_prompt_with_rag(settings["content"]) if settings["enabled"] else None
    
    return {
        "enabled": settings["enabled"],
        "content": settings["content"] if settings["enabled"] else "",
        "content_length": len(settings["content"]) if settings["enabled"] else 0,
        "rag_content_length": len(settings["content"]) if settings["enabled"] else 0,
        "prompts": {
            "base_prompt": base_prompt,
            "rag_enhanced_prompt": enhanced_prompt
        },
        "prompt_components": get_prompt_components_for_response()
    }

# =====================================================
# SHARED KNOWLEDGE DOCUMENTS MANAGEMENT
# =====================================================

class SharedDocumentRequest(BaseModel):
    document_name: str
    description: str = ""

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

class AgentDocumentRequest(BaseModel):
    agent_id: str
    agent_name: str = ""
    class_name: str = ""
    subject: str = ""

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

"""
Student document preview routes
Handles document listing, preview, and metadata for agent knowledge base
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from typing import List, Optional
import os
import mimetypes
from pathlib import Path

from studentProfileDetails.auth.dependencies import get_current_user
from Teacher_AI_Agent.dbFun.file_storage import document_storage
from Teacher_AI_Agent.embaddings.VectorStoreInAtls import get_mongo_collection
from pydantic import BaseModel

router = APIRouter()

# Pydantic models
class DocumentInfo(BaseModel):
    document_id: str
    file_name: str
    file_type: str
    file_size: Optional[int] = None
    upload_date: Optional[str] = None
    preview_available: bool
    chunk_count: Optional[int] = None

class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total: int
    page: int
    limit: int
    total_pages: int
    agent_id: str

def get_student_agent_ids(student_id: str) -> List[str]:
    """
    Get list of agent IDs that a student has access to
    This would typically come from student profile or enrollment data
    """
    try:
        # For now, we'll implement a simple check
        # In a real implementation, this would check student enrollments
        from studentProfileDetails.dbutils import StudentManager
        from Teacher_AI_Agent.dbFun.collections import get_all_agents_of_class

        student_manager = StudentManager()
        student_data = student_manager.get_student(student_id)

        if not student_data:
            return []

        accessible_agents: List[str] = []

        # Get basic student details
        student_details = student_data.get("student_details", {}) or {}
        student_class = student_details.get("class", "")

        # Get subject_agent from student details
        subject_agent = student_details.get("subject_agent", "")

        # Helper to extract an agent ID from a dict entry
        def _extract_agent_id(agent_dict: dict) -> Optional[str]:
            # 1) Direct ID fields (preferred)
            agent_id = (
                agent_dict.get("subject_agent_id")
                or agent_dict.get("agent_id")
                or agent_dict.get("id")
            )
            if agent_id:
                return agent_id

            # 2) Fallback: resolve by subject name using class agents
            subject_name = agent_dict.get("subject")
            if subject_name and student_class:
                try:
                    agents_response = get_all_agents_of_class(student_class)
                    # agents_response may be a dict or direct list depending on implementation
                    agents = agents_response.get("agents") if isinstance(agents_response, dict) else agents_response
                    if isinstance(agents, list):
                        for agent in agents:
                            if isinstance(agent, dict) and agent.get("subject") == subject_name:
                                resolved_id = agent.get("subject_agent_id")
                                if resolved_id:
                                    print(
                                        f"Resolved agent ID '{resolved_id}' for student {student_id} "
                                        f"from subject '{subject_name}' and class '{student_class}'"
                                    )
                                    return resolved_id
                except Exception as e:
                    print(f"Error resolving agent_id by subject for student {student_id}: {e}")

            # 3) No ID could be resolved
            if subject_name:
                print(
                    f"Warning: subject_agent entry for student {student_id} "
                    f"has subject '{subject_name}' but no agent ID field and could not be resolved"
                )
            return None

        # Handle different data structures from student_details.subject_agent
        if subject_agent:
            if isinstance(subject_agent, str):
                # Treat plain strings as direct agent IDs
                accessible_agents.append(subject_agent)
            elif isinstance(subject_agent, dict):
                agent_id = _extract_agent_id(subject_agent)
                if agent_id:
                    accessible_agents.append(agent_id)
            elif isinstance(subject_agent, list):
                for agent in subject_agent:
                    if isinstance(agent, str):
                        # Treat plain strings as direct agent IDs
                        accessible_agents.append(agent)
                    elif isinstance(agent, dict):
                        agent_id = _extract_agent_id(agent)
                        if agent_id:
                            accessible_agents.append(agent_id)

        # Also derive accessible agents from conversation history (where subject_agent_id is stored)
        conversation_history = student_data.get("conversation_history", {})
        if isinstance(conversation_history, dict):
            for subject_conversations in conversation_history.values():
                if isinstance(subject_conversations, list):
                    for conv in subject_conversations:
                        if isinstance(conv, dict):
                            additional_data = conv.get("additional_data", {}) or {}
                            conv_agent_id = (
                                additional_data.get("subject_agent_id")
                                or additional_data.get("agent_id")
                                or additional_data.get("id")
                            )
                            if conv_agent_id and conv_agent_id not in accessible_agents:
                                accessible_agents.append(conv_agent_id)

        # Optional debug log to see what we resolved
        print(f"Resolved accessible agents for student {student_id}: {accessible_agents}")

        return accessible_agents

    except Exception as e:
        print(f"Error getting student agents: {e}")
        return []

def validate_student_agent_access(student_id: str, agent_id: str) -> bool:
    """
    Validate that a student has access to a specific agent
    """
    student_agents = get_student_agent_ids(student_id)
    return agent_id in student_agents

def get_agent_documents_from_db(agent_id: str) -> List[dict]:
    """
    Get unique documents for an agent from the database
    """
    try:
        # We need to find which database/collection contains this agent
        # Use central collections utilities to resolve the correct location
        from Teacher_AI_Agent.dbFun.collections import list_all_collections

        agent_location = None
        try:
            all_agents = list_all_collections()
            if isinstance(all_agents, dict):
                for agent in all_agents.get("agents", []):
                    if (
                        isinstance(agent, dict)
                        and agent.get("subject_agent_id") == agent_id
                    ):
                        agent_location = {
                            "class": agent.get("class"),
                            "subject": agent.get("subject"),
                        }
                        break
        except Exception as e:
            print(f"Error resolving agent location for {agent_id}: {e}")

        if not agent_location:
            # Fallback: try generic 'general' database as before
            possible_locations = [("general", "general")]
        else:
            possible_locations = [
                (agent_location["class"], agent_location["subject"])
            ]

        for db_name, collection_name in possible_locations:
            try:
                collection, used_collection_name = get_mongo_collection(
                    db_name, collection_name
                )

                # Find all unique documents for this agent
                pipeline = [
                    {"$match": {"subject_agent_id": agent_id}},
                    {
                        "$group": {
                            "_id": "$document.doc_unique_id",
                            "file_name": {"$first": "$document.file_name"},
                            "file_type": {"$first": "$document.file_type"},
                            "storage_path": {"$first": "$document.storage_path"},
                            "preview_available": {
                                "$first": "$document.preview_available"
                            },
                            "file_size": {"$first": "$document.file_size"},
                            "upload_date": {"$first": "$document.upload_date"},
                            "chunk_count": {"$sum": 1},
                        }
                    },
                    {"$sort": {"upload_date": -1}},
                ]

                documents = list(collection.aggregate(pipeline))

                if documents:
                    # Convert _id to document_id
                    for doc in documents:
                        doc["document_id"] = doc.pop("_id")

                    return documents

            except Exception as e:
                print(f"Error checking collection {db_name}.{collection_name}: {e}")
                continue

        return []
        
    except Exception as e:
        print(f"Error getting agent documents: {e}")
        return []

@router.get("/{student_id}/agents/{agent_id}/documents", response_model=DocumentListResponse)
def get_student_agent_documents(
    student_id: str,
    agent_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Number of documents per page"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get list of documents available for a student's agent
    Students can only access documents from agents they have access to
    """
    # Security: Students can only access their own documents
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied: You can only access your own documents")
    
    # Validate student has access to this agent
    if not validate_student_agent_access(student_id, agent_id):
        raise HTTPException(status_code=403, detail="Access denied: You don't have access to this agent")
    
    try:
        # Get documents from database
        all_documents = get_agent_documents_from_db(agent_id)
        
        # Apply pagination
        total = len(all_documents)
        total_pages = (total + limit - 1) // limit
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_documents = all_documents[start_idx:end_idx]
        
        # Convert to response model
        document_list = []
        for doc in paginated_documents:
            document_list.append(DocumentInfo(
                document_id=doc.get("document_id", ""),
                file_name=doc.get("file_name", ""),
                file_type=doc.get("file_type", ""),
                file_size=doc.get("file_size"),
                upload_date=doc.get("upload_date"),
                preview_available=doc.get("preview_available", False),
                chunk_count=doc.get("chunk_count", 0)
            ))
        
        return DocumentListResponse(
            documents=document_list,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            agent_id=agent_id
        )
        
    except Exception as e:
        print(f"Error getting documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve documents")

@router.get("/{student_id}/agents/{agent_id}/documents/{document_id}")
def get_document_metadata(
    student_id: str,
    agent_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed metadata for a specific document
    """
    # Security: Students can only access their own documents
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied: You can only access your own documents")
    
    # Validate student has access to this agent
    if not validate_student_agent_access(student_id, agent_id):
        raise HTTPException(status_code=403, detail="Access denied: You don't have access to this agent")
    
    try:
        # Get all documents for the agent
        all_documents = get_agent_documents_from_db(agent_id)
        
        # Find the specific document
        target_doc = None
        for doc in all_documents:
            if doc.get("document_id") == document_id:
                target_doc = doc
                break
        
        if not target_doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get additional details from storage if available
        storage_info = None
        if target_doc.get("preview_available") and target_doc.get("storage_path"):
            try:
                file_path = target_doc["storage_path"]
                if os.path.exists(file_path):
                    file_stat = os.stat(file_path)
                    storage_info = {
                        "file_exists": True,
                        "file_size": file_stat.st_size,
                        "last_modified": file_stat.st_mtime,
                        "mime_type": mimetypes.guess_type(file_path)[0] or "application/octet-stream"
                    }
                else:
                    storage_info = {"file_exists": False}
            except Exception as e:
                storage_info = {"file_exists": False, "error": str(e)}
        
        return {
            "document": target_doc,
            "storage_info": storage_info,
            "agent_id": agent_id,
            "student_id": student_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting document metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document metadata")

@router.get("/{student_id}/agents/{agent_id}/documents/{document_id}/preview")
def preview_document(
    student_id: str,
    agent_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Preview/download the original document file
    """
    # Security: Students can only access their own documents
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied: You can only access your own documents")
    
    # Validate student has access to this agent
    if not validate_student_agent_access(student_id, agent_id):
        raise HTTPException(status_code=403, detail="Access denied: You don't have access to this agent")
    
    try:
        # Get document metadata to find storage path
        all_documents = get_agent_documents_from_db(agent_id)
        
        target_doc = None
        for doc in all_documents:
            if doc.get("document_id") == document_id:
                target_doc = doc
                break
        
        if not target_doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if not target_doc.get("preview_available", False):
            raise HTTPException(status_code=400, detail="Document preview not available")
        
        storage_path = target_doc.get("storage_path")
        if not storage_path or not os.path.exists(storage_path):
            raise HTTPException(status_code=404, detail="Document file not found")
        
        # Determine MIME type
        mime_type = mimetypes.guess_type(storage_path)[0]
        if not mime_type:
            # Default based on file extension
            ext = os.path.splitext(storage_path)[1].lower()
            mime_map = {
                '.pdf': 'application/pdf',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.doc': 'application/msword',
                '.txt': 'text/plain',
                '.html': 'text/html',
                '.htm': 'text/html',
                '.csv': 'text/csv',
                '.json': 'application/json'
            }
            mime_type = mime_map.get(ext, 'application/octet-stream')
        
        # Return file for preview/download
        return FileResponse(
            path=storage_path,
            filename=target_doc.get("file_name", f"document_{document_id}"),
            media_type=mime_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error previewing document: {e}")
        raise HTTPException(status_code=500, detail="Failed to preview document")

@router.get("/{student_id}/shared-documents/{document_id}")
def get_shared_document_metadata(
    student_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get metadata for a shared document (if accessible by student's agents)
    """
    # Security: Students can only access their own data
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied: You can only access your own data")
    
    try:
        from Teacher_AI_Agent.dbFun.shared_knowledge import shared_knowledge_manager
        
        # Get the shared document metadata
        metadata = shared_knowledge_manager.get_shared_document_metadata(document_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Shared document not found")
        
        # Check if student has access to any agent that uses this shared document
        student_agents = get_student_agent_ids(student_id)
        has_access = any(
            agent_id in metadata.get("used_by_agents", []) 
            for agent_id in student_agents
        )
        
        if not has_access and current_user["role"] == "student":
            raise HTTPException(status_code=403, detail="Access denied: This shared document is not available to your agents")
        
        return {
            "status": "success",
            "document": metadata,
            "student_id": student_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting shared document metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve shared document metadata")

@router.get("/{student_id}/shared-documents/{document_id}/preview")
def preview_shared_document(
    student_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Preview/download a shared document file (if accessible by student's agents)
    """
    # Security: Students can only access their own data
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied: You can only access your own data")
    
    try:
        from Teacher_AI_Agent.dbFun.shared_knowledge import shared_knowledge_manager
        
        # Get the shared document metadata to check access
        metadata = shared_knowledge_manager.get_shared_document_metadata(document_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Shared document not found")
        
        # Check if student has access to any agent that uses this shared document
        student_agents = get_student_agent_ids(student_id)
        has_access = any(
            agent_id in metadata.get("used_by_agents", []) 
            for agent_id in student_agents
        )
        
        if not has_access and current_user["role"] == "student":
            raise HTTPException(status_code=403, detail="Access denied: This shared document is not available to your agents")
        
        # Get file path for the shared document
        storage_path = shared_knowledge_manager.get_shared_document_file_path(document_id)
        if not storage_path:
            raise HTTPException(status_code=404, detail="Document file not found or not available for preview")
        
        if not os.path.exists(storage_path):
            raise HTTPException(status_code=404, detail="Document file not found on disk")
        
        # Determine MIME type
        mime_type = mimetypes.guess_type(storage_path)[0]
        if not mime_type:
            # Default based on file extension
            ext = os.path.splitext(storage_path)[1].lower()
            mime_map = {
                '.pdf': 'application/pdf',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.doc': 'application/msword',
                '.txt': 'text/plain',
                '.html': 'text/html',
                '.htm': 'text/html',
                '.csv': 'text/csv',
                '.json': 'application/json'
            }
            mime_type = mime_map.get(ext, 'application/octet-stream')
        
        # Return file for preview/download
        filename = metadata.get("document_name", f"shared_document_{document_id}")
        return FileResponse(
            path=storage_path,
            filename=filename,
            media_type=mime_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error previewing shared document: {e}")
        raise HTTPException(status_code=500, detail="Failed to preview shared document")

@router.get("/{student_id}/documents/storage-info")
def get_storage_info(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get storage information (for admin/debugging purposes)
    """
    # Security: Students can only access their own info
    if current_user["role"] == "student" and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Only allow admins or the student themselves
    if current_user["role"] not in ["admin", "teacher"] and current_user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        storage_info = document_storage.get_storage_info()
        
        # Add student-specific info
        student_agents = get_student_agent_ids(student_id)
        student_documents = []
        
        for agent_id in student_agents:
            agent_docs = get_agent_documents_from_db(agent_id)
            for doc in agent_docs:
                if doc.get("preview_available"):
                    student_documents.append({
                        "agent_id": agent_id,
                        "document_id": doc.get("document_id"),
                        "file_name": doc.get("file_name"),
                        "file_size": doc.get("file_size")
                    })
        
        return {
            "global_storage": storage_info,
            "student_documents": student_documents,
            "accessible_agents": student_agents
        }
        
    except Exception as e:
        print(f"Error getting storage info: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve storage info")

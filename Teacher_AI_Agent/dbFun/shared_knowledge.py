import os
import tempfile
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import UploadFile, HTTPException
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from embaddings.VectorStoreInAtls import create_vector_and_store_in_atlas
from embaddings.runForEmbeding import get_vectors_and_details

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SharedKnowledgeManager:
    """Manages shared knowledge documents accessible by all agents."""
    
    def __init__(self):
        self.mongodb_uri = os.environ.get("MONGODB_URI")
        if not self.mongodb_uri:
            raise ValueError("MONGODB_URI environment variable is not set")
        
        self.client = MongoClient(self.mongodb_uri)
        self.db = self.client["teacher_ai"]
        self.collection = self.db["shared_knowledge"]
    
    def upload_shared_document(
        self,
        files: List[UploadFile],
        document_name: str,
        description: str = "",
        embedding_model=None
    ) -> Dict[str, Any]:
        """Upload and process shared knowledge documents."""
        
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        if not document_name:
            raise HTTPException(status_code=400, detail="Document name is required")
        
        # Check if document name already exists
        existing = self.collection.find_one({"document_name": document_name})
        if existing:
            # Return existing document instead of creating duplicate
            logger.info(f"Document '{document_name}' already exists, returning existing document")
            return {
                "status": "success",
                "message": f"Document '{document_name}' already exists",
                "document_id": existing.get("document_id"),
                "document_name": existing.get("document_name"),
                "description": existing.get("description", ""),
                "upload_date": existing.get("upload_date"),
                "status": existing.get("status", "indexed"),
                "indexed_chunks": existing.get("indexed_chunks", 0),
                "total_chunks": existing.get("total_chunks", 0),
                "file_count": len(existing.get("file_names", [])),
                "file_names": existing.get("file_names", []),
                "estimated_size": existing.get("estimated_size", "Unknown"),
                "used_by_count": len(existing.get("used_by_agents", [])),
                "used_by_agents": existing.get("used_by_agents", []),
                "is_existing": True
            }
        
        # Process files
        file_inputs = []
        original_filenames = []
        
        for file in files:
            if not file or not file.filename:
                continue
            
            suffix = os.path.splitext(file.filename)[-1] or ".tmp"
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = file.file.read()
                
                if not content:
                    continue
                
                tmp.write(content)
                file_inputs.append(tmp.name)
                original_filenames.append(file.filename)
        
        if not file_inputs:
            raise HTTPException(status_code=400, detail="No valid files to process")
        
        # Generate unique document ID
        document_id = f"shared_doc_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{len(file_inputs)}"
        
        # Create vectors and store in shared collection
        try:
            result = create_vector_and_store_in_atlas(
                file_inputs=file_inputs,
                db_name="teacher_ai",
                collection_name="shared_knowledge",
                embedding_model=embedding_model,
                original_filenames=original_filenames,
                agent_metadata={
                    "document_type": "shared_knowledge",
                    "document_name": document_name,
                    "description": description,
                    "upload_date": datetime.utcnow().isoformat(),
                    "document_id": document_id
                },
                subject_agent_id=document_id
            )
            
            # Update document metadata
            self.collection.update_many(
                {"subject_agent_id": document_id},
                {
                    "$set": {
                        "document_name": document_name,
                        "description": description,
                        "upload_date": datetime.utcnow().isoformat(),
                        "document_id": document_id,
                        "status": "indexed",
                        "indexed_chunks": result.get("inserted_chunks", 0),
                        "total_chunks": result.get("num_chunks", 0),
                        "file_names": result.get("file_names", []),
                        "used_by_agents": []
                    }
                }
            )
            
            # Clean up temporary files
            for file_path in file_inputs:
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {file_path}: {e}")
            
            logger.info(f"Successfully uploaded shared document: {document_name}")
            
            return {
                "status": "success",
                "document_id": document_id,
                "document_name": document_name,
                "description": description,
                "upload_date": datetime.utcnow().isoformat(),
                "total_chunks": result.get("num_chunks", 0),
                "indexed_chunks": result.get("inserted_chunks", 0),
                "file_names": result.get("file_names", []),
                "status": "indexed"
            }
            
        except Exception as e:
            # Clean up temporary files on error
            for file_path in file_inputs:
                try:
                    os.unlink(file_path)
                except Exception:
                    pass
            
            logger.error(f"Failed to upload shared document: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")
    
    def list_shared_documents(self) -> Dict[str, Any]:
        """List all shared knowledge documents with their status and usage."""
        try:
            documents = []
            
            # Get unique documents by document_id
            pipeline = [
                {"$match": {"document_id": {"$exists": True}}},
                {"$group": {
                    "_id": "$document_id",
                    "document_name": {"$first": "$document_name"},
                    "description": {"$first": "$description"},
                    "upload_date": {"$first": "$upload_date"},
                    "status": {"$first": "$status"},
                    "indexed_chunks": {"$first": "$indexed_chunks"},
                    "total_chunks": {"$first": "$total_chunks"},
                    "file_names": {"$first": "$file_names"},
                    "used_by_agents": {"$first": "$used_by_agents"},
                    "subject_agent_id": {"$first": "$subject_agent_id"}
                }},
                {"$sort": {"upload_date": -1}}
            ]
            
            for doc in self.collection.aggregate(pipeline):
                # Calculate file sizes (approximate)
                total_size = 0
                for file_name in doc.get("file_names", []):
                    # Estimate size based on file type
                    if file_name.endswith('.pdf'):
                        total_size += 4.2 * 1024 * 1024  # ~4.2 MB average
                    elif file_name.endswith('.docx'):
                        total_size += 2.8 * 1024 * 1024  # ~2.8 MB average
                    else:
                        total_size += 1.5 * 1024 * 1024  # ~1.5 MB average
                
                # Format file size
                if total_size >= 1024 * 1024:
                    size_str = f"{total_size / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{total_size / 1024:.1f} KB"
                
                documents.append({
                    "document_id": doc["_id"],
                    "document_name": doc["document_name"],
                    "description": doc.get("description", ""),
                    "upload_date": doc["upload_date"],
                    "status": doc.get("status", "pending"),
                    "indexed_chunks": doc.get("indexed_chunks", 0),
                    "total_chunks": doc.get("total_chunks", 0),
                    "file_count": len(doc.get("file_names", [])),
                    "file_names": doc.get("file_names", []),
                    "estimated_size": size_str,
                    "used_by_count": len(doc.get("used_by_agents", [])),
                    "used_by_agents": doc.get("used_by_agents", [])
                })
            
            return {
                "status": "success",
                "total_documents": len(documents),
                "documents": documents
            }
            
        except Exception as e:
            logger.error(f"Failed to list shared documents: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def delete_shared_document(self, document_id: str) -> Dict[str, Any]:
        """Delete a shared knowledge document."""
        try:
            # Check if document exists
            doc = self.collection.find_one({"document_id": document_id})
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Delete all chunks for this document
            result = self.collection.delete_many({"document_id": document_id})
            
            logger.info(f"Deleted shared document {document_id}: {result.deleted_count} chunks")
            
            return {
                "status": "success",
                "message": f"Document '{doc.get('document_name', document_id)}' deleted successfully",
                "deleted_chunks": result.deleted_count,
                "document_id": document_id
            }
            
        except Exception as e:
            logger.error(f"Failed to delete shared document {document_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
    
    def enable_document_for_agent(
        self, 
        document_id: str, 
        agent_id: str,
        agent_name: str = "",
        class_name: str = "",
        subject: str = ""
    ) -> Dict[str, Any]:
        """Enable a shared document for a specific agent."""
        try:
            # Check if document exists
            doc = self.collection.find_one({"document_id": document_id})
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Add agent to used_by list if not already present
            agent_info = {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "class_name": class_name,
                "subject": subject,
                "enabled_date": datetime.utcnow().isoformat()
            }
            
            # Check if agent is already enabled
            existing_agents = doc.get("used_by_agents", [])
            agent_already_enabled = any(
                agent.get("agent_id") == agent_id for agent in existing_agents
            )
            
            if agent_already_enabled:
                return {
                    "status": "success",
                    "message": "Document already enabled for this agent",
                    "document_id": document_id,
                    "agent_id": agent_id
                }
            
            # Add agent to used_by list
            result = self.collection.update_many(
                {"document_id": document_id},
                {
                    "$push": {"used_by_agents": agent_info}
                }
            )
            
            logger.info(f"Enabled shared document {document_id} for agent {agent_id}")
            
            return {
                "status": "success",
                "message": f"Document '{doc.get('document_name')}' enabled for agent",
                "document_id": document_id,
                "agent_id": agent_id,
                "document_name": doc.get("document_name")
            }
            
        except Exception as e:
            logger.error(f"Failed to enable document {document_id} for agent {agent_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to enable document: {str(e)}")
    
    def disable_document_for_agent(self, document_id: str, agent_id: str) -> Dict[str, Any]:
        """Disable a shared document for a specific agent."""
        try:
            # Check if document exists
            doc = self.collection.find_one({"document_id": document_id})
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Remove agent from used_by list
            result = self.collection.update_many(
                {"document_id": document_id},
                {
                    "$pull": {"used_by_agents": {"agent_id": agent_id}}
                }
            )
            
            logger.info(f"Disabled shared document {document_id} for agent {agent_id}")
            
            return {
                "status": "success",
                "message": f"Document '{doc.get('document_name')}' disabled for agent",
                "document_id": document_id,
                "agent_id": agent_id,
                "document_name": doc.get("document_name")
            }
            
        except Exception as e:
            logger.error(f"Failed to disable document {document_id} for agent {agent_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to disable document: {str(e)}")
    
    def get_agent_enabled_documents(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get all shared documents enabled for a specific agent."""
        try:
            pipeline = [
                {"$match": {"used_by_agents.agent_id": agent_id}},
                {"$unwind": "$used_by_agents"},
                {"$match": {"used_by_agents.agent_id": agent_id}},
                {"$group": {
                    "_id": "$document_id",
                    "document_name": {"$first": "$document_name"},
                    "description": {"$first": "$description"},
                    "upload_date": {"$first": "$upload_date"},
                    "status": {"$first": "$status"},
                    "indexed_chunks": {"$first": "$indexed_chunks"},
                    "total_chunks": {"$first": "$total_chunks"},
                    "enabled_date": {"$first": "$used_by_agents.enabled_date"}
                }},
                {"$sort": {"enabled_date": -1}}
            ]
            
            documents = []
            for doc in self.collection.aggregate(pipeline):
                # Use the _id field which is the document_id in this aggregation
                doc_id = doc["_id"]
                logger.debug(f"Found enabled document for agent {agent_id}: {doc['document_name']} (ID: {doc_id})")
                
                documents.append({
                    "document_id": doc_id,  # This is the correct document_id
                    "document_name": doc["document_name"],
                    "description": doc.get("description", ""),
                    "upload_date": doc["upload_date"],
                    "status": doc.get("status", "pending"),
                    "indexed_chunks": doc.get("indexed_chunks", 0),
                    "total_chunks": doc.get("total_chunks", 0),
                    "enabled_date": doc["enabled_date"]
                })
            
            logger.info(f"Returning {len(documents)} enabled shared documents for agent {agent_id}")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to get enabled documents for agent {agent_id}: {e}")
            return []

# Global instance
shared_knowledge_manager = SharedKnowledgeManager()

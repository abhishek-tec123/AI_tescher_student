from fastapi import APIRouter, HTTPException
from studentProfileDetails.agents.vector_performance_updater import get_vector_performance
from studentProfileDetails.agents.agent_performance_monitor import AgentPerformanceMonitor
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

router = APIRouter(tags=["agents"])

def get_all_agent_performance():
    """Get performance details for all agents from vector documents."""
    try:
        # Connect to MongoDB
        client = MongoClient(os.environ.get("MONGODB_URI"))
        
        all_agents_performance = []
        processed_agent_ids = set()
        
        # Scan all databases and collections for agents
        for db_name in client.list_database_names():
            if db_name in ["admin", "local", "config", "teacher_ai"]:
                continue
                
            db = client[db_name]
            
            for collection_name in db.list_collection_names():
                collection = db[collection_name]
                
                # Find all documents with subject_agent_id
                cursor = collection.find({"subject_agent_id": {"$exists": True}})
                
                for doc in cursor:
                    agent_id = doc.get("subject_agent_id")
                    
                    if agent_id and agent_id not in processed_agent_ids:
                        processed_agent_ids.add(agent_id)
                        
                        # Get performance data from this document
                        performance = doc.get("performance", {})
                        agent_metadata = doc.get("agent_metadata", {})
                        
                        # Create agent performance object
                        agent_performance = {
                            "subject_agent_id": agent_id,
                            "database": db_name,
                            "collection": collection_name,
                            "agent_metadata": agent_metadata,
                            "performance": performance,
                            "document_id": str(doc.get("_id"))
                        }
                        
                        all_agents_performance.append(agent_performance)
        
        client.close()
        return all_agents_performance
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving agent performance: {str(e)}"
        )

@router.get("/agents/all-agents-performance")
async def get_all_agents_performance():
    """
    Get performance details for all agents separately.
    
    Returns performance data from vector documents for each agent.
    Each agent includes:
    - subject_agent_id
    - database and collection info
    - agent metadata
    - complete performance matrix
    - document ID
    """
    try:
        all_agents = get_all_agent_performance()
        
        return {
            "success": True,
            "message": f"Found {len(all_agents)} agents",
            "total_agents": len(all_agents),
            "agents": all_agents
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving all agents performance: {str(e)}"
        )

@router.get("/agents/agent-performance/{agent_id}")
async def get_single_agent_performance(agent_id: str):
    """
    Get performance details for a specific agent.
    
    Returns complete performance matrix from vector documents.
    """
    try:
        # Get performance from vector documents
        vector_performance = get_vector_performance(agent_id)
        
        if not vector_performance or vector_performance.get("total_conversations", 0) == 0:
            # Try to get from agent performance summary as fallback
            monitor = AgentPerformanceMonitor()
            summary = monitor.get_agent_performance_summary(agent_id)
            
            if summary:
                return {
                    "success": True,
                    "message": f"Performance data for {agent_id}",
                    "agent_id": agent_id,
                    "source": "summary_collection",
                    "performance": summary
                }
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Agent {agent_id} not found"
                )
        
        return {
            "success": True,
            "message": f"Performance data for {agent_id}",
            "agent_id": agent_id,
            "source": "vector_documents",
            "performance": vector_performance
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving agent performance: {str(e)}"
        )

from fastapi import APIRouter, HTTPException, Depends
from studentProfileDetails.agents.vector_performance_updater import get_vector_performance
from studentProfileDetails.agents.agent_performance_monitor import AgentPerformanceMonitor
from studentProfileDetails.auth.dependencies import require_any_role
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

@router.get("/all-agents-performance")
async def get_all_agents_performance(
    current_user: dict = Depends(require_any_role(["admin", "teacher"]))
):
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
        print(f"🚀 User {current_user.get('user_id')} requesting all agents performance")
        
        # Use the optimized AgentPerformanceMonitor instead of direct MongoDB scan
        monitor = AgentPerformanceMonitor()
        overview_data = monitor.get_all_agents_overview(30)  # Use default 30 days
        
        print(f"📋 Got overview for {len(overview_data)} agents, building detailed response...")
        
        # Transform overview data to match expected format WITHOUT individual database calls
        all_agents = []
        for agent in overview_data:
            # Use cached overview data instead of individual database calls
            agent_performance = {
                "subject_agent_id": agent["agent_id"],
                "database": agent["class_name"],
                "collection": agent["subject"],
                "agent_metadata": {
                    "agent_name": agent["agent_name"]
                },
                "performance": {
                    # Use overview metrics instead of detailed performance summary
                    "overall_score": agent["overall_score"],
                    "performance_level": agent["performance_level"],
                    "total_conversations": agent["total_conversations"],
                    "health_status": agent["health_status"]
                },
                "document_id": agent.get("agent_id", ""),  # Using agent_id as fallback
                "overall_score": agent["overall_score"],
                "performance_level": agent["performance_level"],
                "total_conversations": agent["total_conversations"],
                "health_status": agent["health_status"]
            }
            
            all_agents.append(agent_performance)
        
        print(f"✅ Built response for {len(all_agents)} agents without individual DB calls")
        
        return {
            "success": True,
            "message": f"Found {len(all_agents)} agents",
            "total_agents": len(all_agents),
            "agents": all_agents
        }
        
    except Exception as e:
        print(f"❌ Error retrieving all agents performance: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving all agents performance: {str(e)}"
        )

@router.get("/agent-performance/{agent_id}")
async def get_single_agent_performance(
    agent_id: str,
    current_user: dict = Depends(require_any_role(["admin", "teacher"]))
):
    """
    Get performance details for a specific agent.
    
    Returns complete performance matrix from vector documents.
    """
    try:
        print(f"🚀 User {current_user.get('user_id')} requesting performance for agent {agent_id}")
        
        # Get performance from vector documents
        vector_performance = get_vector_performance(agent_id)
        
        if not vector_performance or vector_performance.get("total_conversations", 0) == 0:
            # Try to get from agent performance summary as fallback
            print(f"📦 Vector performance empty for {agent_id}, using monitor fallback")
            monitor = AgentPerformanceMonitor()
            summary = monitor.get_agent_performance_summary(agent_id)
            
            if summary:
                print(f"✅ Retrieved performance summary for {agent_id}")
                return {
                    "success": True,
                    "message": f"Performance data for {agent_id}",
                    "agent_id": agent_id,
                    "source": "summary_collection",
                    "performance": summary
                }
            else:
                print(f"❌ No performance data found for agent {agent_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Agent {agent_id} not found"
                )
        
        print(f"✅ Retrieved vector performance for {agent_id}")
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
        print(f"❌ Error retrieving agent performance for {agent_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving agent performance: {str(e)}"
        )

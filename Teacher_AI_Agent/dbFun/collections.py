import logging
import os
from pymongo import MongoClient

logger = logging.getLogger("collections")
MONGODB_URI = os.environ.get("MONGODB_URI")

SYSTEM_DBS = {"admin", "local", "config", "teacher_ai"}

def list_all_collections():
    try:
        client = MongoClient(MONGODB_URI)
        result = []

        for db_name in client.list_database_names():
            if db_name in SYSTEM_DBS:
                continue

            db = client[db_name]

            for collection_name in db.list_collection_names():
                collection = db[collection_name]

                # Get first document where agent_metadata.description exists
                doc = collection.find_one(
                    {"agent_metadata.description": {"$exists": True}},
                    {"agent_metadata.agent_name": 1,
                     "agent_metadata.agent_type": 1,
                     "agent_metadata.description": 1}
                )

                if not doc:
                    continue

                agent = doc.get("agent_metadata", {})

                result.append({
                    "class": db_name,
                    "subject": collection_name,
                    "agent_name": agent.get("agent_name"),
                    "agent_type": agent.get("agent_type"),
                    "description": agent.get("description")
                })

        return {
            "status": "success",
            "agents": result
        }

    except Exception as e:
        logger.error(f"❌ Error fetching agents: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

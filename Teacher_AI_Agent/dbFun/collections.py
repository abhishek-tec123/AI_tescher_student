import logging
import os
from pymongo import MongoClient

logger = logging.getLogger("collections")
MONGODB_URI = os.environ.get("MONGODB_URI")

SYSTEM_DBS = {"admin", "local", "config"}

def list_all_collections():
    try:
        client = MongoClient(MONGODB_URI)
        cluster_info = {}

        for db_name in client.list_database_names():
            if db_name in SYSTEM_DBS:
                continue
            cluster_info[db_name] = client[db_name].list_collection_names()

        return {
            "status": "success",
            "databases": cluster_info
        }

    except Exception as e:
        logger.error(f"❌ Error fetching collections: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

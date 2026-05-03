import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ.get("MONGODB_URI"))
db = client[os.environ.get("DB_NAME", "tutor_ai")]

db.students.update_many(
    {},
    {
        "$push": {
            "conversation_history.Science": {
                "$each": [],
                "$slice": 10
            }
        }
    }
)

print("Cleanup done")

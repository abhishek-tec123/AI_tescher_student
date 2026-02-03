from pymongo import MongoClient

client = MongoClient("mongodb+srv://abhishek1233445:A0t24VdRZzQ0eJSa@cluster0.fgmkf.mongodb.net/")
db = client["teacher_ai"]

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

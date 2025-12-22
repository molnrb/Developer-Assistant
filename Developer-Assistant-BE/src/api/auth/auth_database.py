import os

from pymongo import MongoClient
from pymongo.collection import Collection

client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017/mydb"))
db = client["app_db"]


def get_user_collection() -> Collection:
    return db["users"]

import os
from typing import Dict, List

from dotenv import load_dotenv
from pymongo import MongoClient

from src.api.database.database_dto import ChatMessage, ProjectFile

load_dotenv()
client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017/mydb"))
db = client["app_db"]
projects = db["projects"]


def update_project_summary(project_id: str, summary: dict, username: str) -> None:
    projects.update_one(
        {"_id": project_id, "owner": username},
        {"$set": {"metadata.project_summary": summary}},
    )


def update_dependency_graph(project_id: str, graph: dict, username: str) -> None:
    projects.update_one(
        {"_id": project_id, "owner": username},
        {"$set": {"metadata.dependency_graph": graph}},
    )


def load_project_summary(project_id: str, username: str) -> dict:
    doc = projects.find_one({"_id": project_id, "owner": username})
    return doc.get("summary", {})


def load_dependency_graph(project_id: str, username: str) -> dict:
    doc = projects.find_one({"_id": project_id, "owner": username})
    return doc.get("dependency_graph", {}) if doc else {}


def load_files(project_id: str, filenames: List[str], username: str) -> Dict[str, str]:
    doc = projects.find_one({"_id": project_id, "owner": username})
    file_map = {}

    if doc and "files" in doc:
        target_set = set(name.strip() for name in filenames)

        for f in doc["files"]:
            name = f.get("name", "").strip()
            if name in target_set:
                file_map[name] = f.get("content", "")
            else:
                print(f"Not matched: '{name}'")

    return file_map


def message_count_in_project(project_id: str, username: str) -> int:
    doc = projects.find_one({"_id": project_id, "owner": username})
    if not doc or "messages" not in doc:
        return 0
    return len(doc["messages"])


def load_all_files(project_id: str, username: str) -> Dict[str, str]:
    """Load all files from a project."""
    doc = projects.find_one({"_id": project_id, "owner": username})
    if not doc:
        raise ValueError(f"Project with id {project_id} not found for user {username}.")

    file_map = {}
    if doc and "files" in doc:
        for f in doc["files"]:
            name = f.get("name", "").strip()
            content = f.get("content", "")
            if name:
                file_map[name] = content

    return file_map


def get_project_title(project_id: str, username: str) -> str:
    doc = projects.find_one({"_id": project_id, "owner": username})
    if not doc:
        raise ValueError(f"Project with id {project_id} not found for user {username}.")

    return doc["title"]


def update_files_in_project(
    project_id: str, updated_files: List[ProjectFile], username: str
) -> None:
    for name, content in updated_files.items():
        result = projects.update_one(
            {"_id": project_id, "owner": username, "files.name": name},
            {"$set": {"files.$.content": content}},
        )

        if result.matched_count == 0:
            print(f"No matching document found for file: {name}")
        else:
            print(f"File {name} updated successfully.")


def add_messages_to_project(
    project_id: str, messages: List[ChatMessage], username: str
) -> None:
    messages_docs = [m.dict() for m in messages]
    projects.update_one(
        {"_id": project_id, "owner": username},
        {"$push": {"messages": {"$each": messages_docs}}},
    )


def replace_project_files(
    project_id: str, new_files: List[ProjectFile], username: str
) -> None:
    projects.update_one(
        {"_id": project_id, "owner": username},
        {"$set": {"files": [file.__dict__ for file in new_files]}},
    )


def replace_project_manifest(
    project_id: str, manifest: List[Dict], username: str
) -> None:
    projects.update_one(
        {"_id": project_id, "owner": username},
        {"$set": {"summary": manifest}},
    )

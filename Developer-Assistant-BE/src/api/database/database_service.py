import os
from datetime import datetime
from typing import List

from bson import ObjectId
from fastapi import HTTPException
from pymongo import MongoClient

from src.api.database.database_dto import (
    ChatMessage,
    FullProjectResponse,
    ListProjectsResponse,
    ProjectCreateRequest,
    ProjectFile,
    RenameFileRequest,
    UpdateFileContentRequest,
    newProjectResponse,
)

client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017/mydb"))
db = client["app_db"]
projects_collection = db["projects"]


class DatabaseService:
    def __init__(self):
        self.client = MongoClient(
            os.getenv("MONGO_URL", "mongodb://localhost:27017/mydb")
        )
        self.db = self.client["app_db"]
        self.projects_collection = self.db["projects"]

    def add_project(self, data: ProjectCreateRequest, current_user: str) -> str:
        """
        Add a new project to the database.
        """
        try:
            project = {
                "_id": data.id,
                "owner": current_user,
                "title": data.title,
                "files": [file.dict() for file in data.files],
                "summary": data.summary,
                "messages": [msg.dict() for msg in data.messages],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            self.projects_collection.insert_one(project)
            return str(project["_id"])
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to add project: {str(e)}"
            )

    def get_projects(self, current_user: str) -> ListProjectsResponse:
        """
        Get all projects from the database regarding current user.
        """
        try:
            projects = list(self.projects_collection.find({"owner": current_user}))
            projectsResponse: List[newProjectResponse] = []
            for p in projects:
                projectsResponse.append(
                    newProjectResponse(
                        id=str(p["_id"]), title=p.get("title", "Untitled Project")
                    )
                )
            return ListProjectsResponse(projects=projectsResponse)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve projects: {str(e)}"
            )

    def get_project(self, project_id: str, current_user: str) -> FullProjectResponse:
        """
        Get a project from the database regarding current user.
        """
        try:
            project = self.projects_collection.find_one(
                {"_id": project_id, "owner": current_user}
            )
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            project["id"] = str(project["_id"])
            del project["_id"]
            return FullProjectResponse(
                id=project["id"],
                title=project["title"],
                files=[ProjectFile(**file) for file in project["files"]],
                messages=[ChatMessage(**msg) for msg in project["messages"]],
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve project: {str(e)}"
            )

    def update_project(
        self, project_id: str, data: ProjectCreateRequest, current_user: str
    ) -> None:
        """
        Update a project in the database regarding current user.
        """
        try:
            project = self.projects_collection.find_one(
                {"_id": project_id, "owner": current_user}
            )
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            updated_project = {
                "title": data.title,
                "files": [file.dict() for file in data.files],
                "messages": [msg.dict() for msg in data.messages],
                "updated_at": datetime.utcnow(),
            }
            self.projects_collection.update_one(
                {"_id": project_id}, {"$set": updated_project}
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to update project: {str(e)}"
            )

    def update_project_title(
        self, project_id: str, data: str, current_user: str
    ) -> None:
        """
        Update a project's title in db with current user.
        """
        try:
            project = self.projects_collection.find_one(
                {"_id": project_id, "owner": current_user}
            )
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            updated_project = {"title": data, "updated_at": datetime.utcnow()}
            self.projects_collection.update_one(
                {"_id": project_id}, {"$set": updated_project}
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to update project: {str(e)}"
            )

    def delete_project(self, project_id: str, current_user: str) -> None:
        """
        Delete a project from the database regarding current user.
        """
        try:
            project = self.projects_collection.find_one(
                {"_id": project_id, "owner": current_user}
            )
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.projects_collection.delete_one({"_id": project_id})
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to delete project: {str(e)}"
            )

    def update_file_content(
        self,
        project_id: str,
        file_name: str,
        data: UpdateFileContentRequest,
        current_user: str,
    ) -> None:
        """
        Update the content of a file in the project safely.
        """
        try:
            res = self.projects_collection.update_one(
                {"_id": project_id, "owner": current_user, "files.name": file_name},
                {
                    "$set": {
                        "files.$.content": data.content,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            if res.matched_count == 0:
                proj = self.projects_collection.find_one(
                    {"_id": ObjectId(project_id), "owner": current_user}
                )
                if not proj:
                    raise HTTPException(status_code=404, detail="Project not found")
                raise HTTPException(status_code=404, detail="File not found in project")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to update file content: {str(e)}"
            )

    def rename_file(
        self, project_id: str, old_name: str, data: RenameFileRequest, current_user: str
    ) -> None:
        """
        Rename a file in the project safely.
        """
        try:
            existing = self.projects_collection.find_one(
                {"_id": project_id, "owner": current_user, "files.name": data.new_name}
            )
            if existing:
                raise HTTPException(
                    status_code=409, detail="A file with the new name already exists"
                )

            res = self.projects_collection.update_one(
                {"_id": project_id, "owner": current_user, "files.name": old_name},
                {
                    "$set": {
                        "files.$.name": data.new_name,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            if res.matched_count == 0:
                proj = self.projects_collection.find_one(
                    {"_id": project_id, "owner": current_user}
                )
                if not proj:
                    raise HTTPException(status_code=404, detail="Project not found")
                raise HTTPException(status_code=404, detail="File not found in project")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to rename file: {str(e)}"
            )

    def delete_file(self, project_id: str, file_name: str, current_user: str) -> None:
        """
        Delete a file from the project.
        """
        try:
            res = self.projects_collection.update_one(
                {"_id": project_id, "owner": current_user},
                {
                    "$pull": {"files": {"name": file_name}},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            if res.matched_count == 0:
                proj = self.projects_collection.find_one(
                    {"_id": project_id, "owner": current_user}
                )
                if not proj:
                    raise HTTPException(status_code=404, detail="Project not found")
            if res.modified_count == 0:
                raise HTTPException(status_code=404, detail="File not found in project")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to delete file: {str(e)}"
            )

    def add_file(
        self,
        project_id: str,
        file_name: str,
        data: UpdateFileContentRequest,
        current_user: str,
    ) -> None:
        """
        Add a new file to the project.
        """
        try:
            existing = self.projects_collection.find_one(
                {"_id": project_id, "owner": current_user, "files.name": file_name}
            )
            if existing:
                raise HTTPException(
                    status_code=409, detail="A file with the same name already exists"
                )

            res = self.projects_collection.update_one(
                {"_id": project_id, "owner": current_user},
                {
                    "$push": {"files": {"name": file_name, "content": data.content}},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            if res.matched_count == 0:
                proj = self.projects_collection.find_one(
                    {"_id": project_id, "owner": current_user}
                )
                if not proj:
                    raise HTTPException(status_code=404, detail="Project not found")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add file: {str(e)}")

    def rename_project(
        self, project_id: str, new_title: str, current_user: str
    ) -> None:
        """
        Rename a project safely.
        """
        try:
            project = self.projects_collection.find_one(
                {"_id": project_id, "owner": current_user}
            )
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            updated_project = {"title": new_title, "updated_at": datetime.utcnow()}
            self.projects_collection.update_one(
                {"_id": project_id}, {"$set": updated_project}
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to rename project: {str(e)}"
            )

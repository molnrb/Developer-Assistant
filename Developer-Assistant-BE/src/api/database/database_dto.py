from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ProjectFile(BaseModel):
    name: str = Field(..., description="The name of the file, including its extension.")
    content: str = Field(..., description="The content of the file as a string.")


class ChatMessage(BaseModel):
    id: int = Field(..., description="Unique identifier for the message.")
    content: str = Field(..., description="The content of the message.")
    fromUser: bool = Field(
        ..., description="Indicates if the message is from the user."
    )


class ProjectCreateRequest(BaseModel):
    id: str = Field(..., description="The unique identifier of the project.")
    title: str = Field(..., description="The title of the project.")
    summary: List[Dict[str, Any]] = Field(..., description="summmary")
    files: List[ProjectFile] = Field(..., description="List of files in the project.")
    messages: List[ChatMessage] = Field(
        ..., description="List of chat messages related to the project."
    )


class newProjectResponse(BaseModel):
    id: str = Field(..., description="The unique identifier of the project.")
    title: str = Field(
        ..., description="A message indicating the result of the operation."
    )


class ProjectResponse(BaseModel):
    id: str = Field(..., description="The unique identifier of the project.")
    title: str = Field(
        ..., description="A message indicating the result of the operation."
    )
    files: List[ProjectFile] = Field(..., description="List of files in the project.")
    messages: List[ChatMessage] = Field(
        ..., description="List of chat messages related to the project."
    )


class FullProjectResponse(ProjectResponse):
    files: List[ProjectFile] = Field(..., description="List of files in the project.")
    messages: List[ChatMessage] = Field(
        ..., description="List of chat messages related to the project."
    )


class ListProjectsResponse(BaseModel):
    projects: List[newProjectResponse] = Field(
        ..., description="List of projects associated with the user."
    )


class UpdateFileContentRequest(BaseModel):
    content: str = Field(..., description="New content for the file")


class RenameFileRequest(BaseModel):
    new_name: str = Field(..., description="New file name with extension")

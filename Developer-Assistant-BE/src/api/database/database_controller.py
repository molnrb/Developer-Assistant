from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer

from src.api.database.database_dto import (
    FullProjectResponse,
    ListProjectsResponse,
    ProjectCreateRequest,
    RenameFileRequest,
    UpdateFileContentRequest,
)
from src.api.database.database_service import DatabaseService
from src.utils.auth import get_current_user

router = APIRouter(
    tags=["Database"],
    prefix="/database",
)

security = HTTPBearer()


def get_database_service() -> DatabaseService:
    return DatabaseService()


@router.post(
    "/add_project",
    response_model=str,
    summary="Add a new project to the database",
)
async def add_project(
    body: ProjectCreateRequest,
    current_user: str = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> str:
    return db_service.add_project(body, current_user)


@router.get(
    "/get_projects",
    response_model=ListProjectsResponse,
    summary="Get all projects from the database regarding current user",
)
async def get_projects(
    current_user: str = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> ListProjectsResponse:
    return db_service.get_projects(current_user)


@router.get(
    "/get_project/{project_id}",
    response_model=FullProjectResponse,
    summary="Get a project from the database regarding current user",
)
async def get_project(
    project_id: str,
    current_user: str = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> FullProjectResponse:
    return db_service.get_project(project_id, current_user)


@router.put(
    "/update_project/{project_id}",
    response_model=None,
    summary="Update a project in the database regarding current user",
)
async def update_project(
    project_id: str,
    body: ProjectCreateRequest,
    current_user: str = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> None:
    return db_service.update_project(project_id, body, current_user)


@router.put(
    "/update_project_title/{project_id}",
    response_model=None,
    summary="Update a project's title in db with current user",
)
async def update_project_title(
    project_id: str,
    body: str,
    current_user: str = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> None:
    return db_service.update_project_title(project_id, body, current_user)


@router.delete(
    "/delete_project/{project_id}",
    response_model=None,
    summary="Delete a project from the database regarding current user",
)
async def delete_project(
    project_id: str,
    current_user: str = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> None:
    return db_service.delete_project(project_id, current_user)


@router.patch(
    "/projects/{project_id}/files",
    response_model=None,
    summary="Update a single file's content safely (filename in body)",
)
async def update_file_content(
    project_id: str,
    body: dict,
    current_user: str = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_database_service),
) -> None:
    file_name = body.get("name")
    content = body.get("content")
    if not file_name or content is None:
        raise HTTPException(status_code=400, detail="Missing file name or content")
    return db_service.update_file_content(
        project_id, file_name, UpdateFileContentRequest(content=content), current_user
    )


@router.patch(
    "/projects/{project_id}/files/rename",
    response_model=None,
    summary="Rename a file safely (old_name, new_name in body)",
)
async def rename_file(
    project_id: str,
    body: dict,
    current_user: str = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_database_service),
):
    old_name = body.get("old_name")
    new_name = body.get("new_name")
    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="Missing file names")
    return db_service.rename_file(
        project_id, old_name, RenameFileRequest(new_name=new_name), current_user
    )


@router.patch(
    "/projects/{project_id}/files/delete",
    response_model=None,
    summary="Delete a file safely (filename in body)",
)
async def delete_file(
    project_id: str,
    body: dict,
    current_user: str = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_database_service),
):
    file_name = body.get("name")
    if not file_name:
        raise HTTPException(status_code=400, detail="Missing file name")
    return db_service.delete_file(project_id, file_name, current_user)


@router.patch(
    "/projects/{project_id}/files/add",
    response_model=None,
    summary="Add a new file safely (filename, content in body)",
)
async def add_file(
    project_id: str,
    body: dict,
    current_user: str = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_database_service),
):
    file_name = body.get("name")
    content = body.get("content")
    if not file_name or content is None:
        raise HTTPException(status_code=400, detail="Missing file name or content")
    return db_service.add_file(
        project_id, file_name, UpdateFileContentRequest(content=content), current_user
    )


@router.patch(
    "projects/{project_id}/rename_project",
    response_model=None,
    summary="Rename a project safely (new title in body)",
)
async def rename_project(
    project_id: str,
    body: str,
    current_user: str = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_database_service),
):
    new_title = body.get("title")
    if not new_title:
        raise HTTPException(status_code=400, detail="Missing new title")
    return db_service.update_project_title(project_id, new_title, current_user)

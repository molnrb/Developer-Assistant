import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from dotenv import load_dotenv

from src.api.auth.auth import router as auth_router
from src.api.database.database_controller import router as database_router
from src.api.agent_pipeline import event_controller
from src.api.preview import router as preview_router

load_dotenv()

app = FastAPI()


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="WebGenAI API",
        version="1.0.0",
        description="Project & Chat API with Auth",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"OAuth2PasswordBearer": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(auth_router)
app.include_router(database_router)
app.include_router(event_controller.router)
app.include_router(preview_router.router)
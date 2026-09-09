from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api import documents
from app.api import facts
from app.api import issues
from app.api import relations
from app.api import upload
from app.config import settings
from app.db.database import initialize_database
STATIC_DIR = Path(__file__).resolve().parent / "static"
@asynccontextmanager
async def lifespan(application: FastAPI):
    Path(settings.upload_dir).mkdir(
        parents=True,
        exist_ok=True,
    )
    initialize_database()
    yield
app = FastAPI(
    title="Fact Knowledge Layer",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)
app.include_router(upload.router)
app.include_router(documents.router)
app.include_router(facts.router)
app.include_router(relations.router)
app.include_router(issues.router)
@app.get("/", include_in_schema=False)
def serve_frontend() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "index.html"
    )
@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "fact-knowledge-layer",
    }
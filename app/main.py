from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import get_settings, load_version
from .runtime import ensure_data_dirs, path_exists

settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_data_dirs(settings)
    yield


app = FastAPI(title="video-review", version=load_version(), lifespan=lifespan)


def service_info() -> dict:
    return {
        "service": settings.app_name,
        "version": load_version(),
        "data_dir": str(settings.data_dir),
        "database_path": str(settings.database_path),
        "screenshot_dir": str(settings.screenshot_dir),
        "jobs_dir": str(settings.jobs_dir),
        "logs_dir": str(settings.logs_dir),
        "download_root": str(settings.download_root),
        "download_root_exists": path_exists(settings.download_root),
        "library_root": str(settings.library_root),
        "library_root_exists": path_exists(settings.library_root),
        "auth_mode": settings.auth_mode,
        "public_base_url": settings.public_base_url,
        "integration_mode": "generic-service-with-optional-hermes-orchestration",
        "capabilities": {
            "review_web": True,
            "healthcheck": True,
            "scan_jobs": False,
            "screenshot_batches": False,
            "execution_plans": False,
            "media_mutation": False,
        },
        "safety": {
            "review_only": True,
            "moves_files": False,
            "deletes_files": False,
        },
    }


@app.get("/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "service": settings.app_name,
        "version": load_version(),
    }


@app.get("/api/v1/info")
def info() -> dict:
    return service_info()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "version": load_version(),
            "app_settings": settings,
            "service_info": service_info(),
        },
    )

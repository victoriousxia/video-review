from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import get_settings, load_version
from .runtime import ensure_data_dirs, path_exists

settings = get_settings()
templates = Jinja2Templates(directory="app/templates")

app = FastAPI(title="video-review", version=load_version())


@app.on_event("startup")
def startup() -> None:
    ensure_data_dirs(settings)


@app.get("/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "service": settings.app_name,
        "version": load_version(),
    }


@app.get("/api/v1/info")
def info() -> dict:
    return {
        "service": settings.app_name,
        "version": load_version(),
        "data_dir": str(settings.data_dir),
        "database_path": str(settings.database_path),
        "screenshot_dir": str(settings.screenshot_dir),
        "download_root": str(settings.download_root),
        "download_root_exists": path_exists(settings.download_root),
        "library_root": str(settings.library_root),
        "library_root_exists": path_exists(settings.library_root),
        "auth_mode": settings.auth_mode,
        "public_base_url": settings.public_base_url,
        "integration_mode": "generic-service-with-optional-hermes-orchestration",
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "version": load_version(),
            "settings": settings,
        },
    )

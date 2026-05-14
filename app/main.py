from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import get_settings, load_version
from .database import get_database, path_is_under
from .runtime import ensure_data_dirs, path_exists
from .scanner import scan_directory
from .schemas import CreateJobRequest, JobDetailResponse, JobListResponse, ReviewJob

settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_data_dirs(settings)
    get_database().init()
    yield


app = FastAPI(title="video-review", version=load_version(), lifespan=lifespan)


def service_info() -> dict:
    return {
        "service": settings.app_name,
        "version": load_version(),
        "data_dir": str(settings.data_dir),
        "database_path": str(settings.database_path),
        "database": get_database().schema_info(),
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
            "scan_jobs": True,
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


def validate_scan_path(scan_path: str) -> str:
    candidate = Path(scan_path)
    allowed_roots = (settings.download_root, settings.library_root)
    if not candidate.is_absolute():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scan_path must be absolute")
    if not any(path_is_under(candidate, root) for root in allowed_roots):
        roots = ", ".join(str(root) for root in allowed_roots)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"scan_path must be under allowed media roots: {roots}",
        )
    return str(candidate)


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


@app.get("/api/v1/jobs", response_model=JobListResponse)
def list_jobs() -> dict:
    return {"jobs": get_database().list_jobs()}


@app.post("/api/v1/jobs", response_model=ReviewJob, status_code=status.HTTP_201_CREATED)
def create_job(request: CreateJobRequest) -> dict:
    scan_path = validate_scan_path(request.scan_path)
    return get_database().create_job(name=request.name, scan_path=scan_path, notes=request.notes)


@app.get("/api/v1/jobs/{job_id}", response_model=JobDetailResponse)
def get_job_detail(job_id: str) -> dict:
    database = get_database()
    job = database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review job not found")
    return {"job": job, "items": database.list_items(job_id)}


@app.post("/api/v1/jobs/{job_id}/scan", response_model=JobDetailResponse)
def scan_job(job_id: str) -> dict:
    database = get_database()
    job = database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review job not found")
    if job["status"] not in ("pending", "ready", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"job is currently '{job['status']}', cannot start scan",
        )

    scan_path = Path(job["scan_path"])
    allowed_roots = (settings.download_root, settings.library_root)

    database.update_job_status(job_id, "running")
    try:
        scanned = scan_directory(scan_path, allowed_roots)
        items_data = [asdict(f) for f in scanned]
        database.insert_items(job_id, items_data)
        database.update_job_status(job_id, "ready", total_items=len(items_data))
    except Exception as exc:
        database.update_job_status(job_id, "failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"scan failed: {exc}",
        )

    job = database.get_job(job_id)
    return {"job": job, "items": database.list_items(job_id)}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    jobs = get_database().list_jobs()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "version": load_version(),
            "app_settings": settings,
            "service_info": service_info(),
            "jobs": jobs[:5],
        },
    )


@app.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request):
    return templates.TemplateResponse(
        request,
        "jobs.html",
        {
            "version": load_version(),
            "app_settings": settings,
            "jobs": get_database().list_jobs(),
        },
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail_page(request: Request, job_id: str):
    database = get_database()
    job = database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review job not found")
    return templates.TemplateResponse(
        request,
        "job_detail.html",
        {
            "version": load_version(),
            "app_settings": settings,
            "job": job,
            "items": database.list_items(job_id),
        },
    )

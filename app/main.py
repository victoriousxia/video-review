from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import get_settings, load_version
from .database import get_database, path_is_under
from .runtime import ensure_data_dirs, path_exists
from .scanner import scan_directory
from .schemas import CreateJobRequest, JobDetailResponse, JobListResponse, PatchItemRequest, ReviewItem, ReviewJob

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


def validate_dir_param(dir_param: str | None) -> str | None:
    if dir_param is None or dir_param == "":
        return None
    if dir_param.startswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="dir must be a relative path")
    if ".." in dir_param.split("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="dir must not contain '..'")
    return dir_param


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
def get_job_detail(job_id: str, dir: str | None = None) -> dict:
    validated_dir = validate_dir_param(dir)
    database = get_database()
    job = database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review job not found")
    if validated_dir is not None:
        folder = job["scan_path"].rstrip("/") + "/" + validated_dir
        items = database.list_items(job_id, folder_prefix=folder)
    else:
        items = database.list_items(job_id)
    return {"job": job, "items": items}


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
        database.replace_items(job_id, items_data)
        database.update_job_status(job_id, "ready", total_items=len(items_data))
    except Exception as exc:
        database.update_job_status(job_id, "failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"scan failed: {exc}",
        )

    job = database.get_job(job_id)
    return {"job": job, "items": database.list_items(job_id)}


@app.patch("/api/v1/items/{item_id}", response_model=ReviewItem)
def patch_item(item_id: str, body: PatchItemRequest) -> dict:
    database = get_database()
    item = database.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")

    updates = {}
    if body.review_status is not None:
        updates["review_status"] = body.review_status.value
    if body.user_action is not None:
        updates["user_action"] = body.user_action
    if body.user_notes is not None:
        updates["user_notes"] = body.user_notes

    updated = database.update_item(item_id, updates)
    return updated


@app.get("/api/v1/browse")
def browse_directories(path: str | None = None) -> dict:
    allowed_roots = (settings.download_root, settings.library_root)
    if path is None or path == "":
        roots = []
        for root in allowed_roots:
            if path_exists(root):
                roots.append({"name": root.name, "path": str(root)})
        return {"current": None, "dirs": roots}

    target = Path(path)
    if not target.is_absolute():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="path must be absolute")
    if ".." in target.parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="path must not contain '..'")
    if not any(path_is_under(target, root) for root in allowed_roots):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="path not under allowed roots")
    if not target.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="directory not found")

    dirs = sorted(
        [{"name": d.name, "path": str(d)} for d in target.iterdir() if d.is_dir() and not d.name.startswith(".")],
        key=lambda x: x["name"],
    )
    return {"current": str(target), "dirs": dirs}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    jobs = get_database().list_jobs()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "version": load_version(),
            "jobs": jobs,
            "download_root": str(settings.download_root),
            "library_root": str(settings.library_root),
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
def job_detail_page(request: Request, job_id: str, dir: str | None = None):
    validated_dir = validate_dir_param(dir)
    database = get_database()
    job = database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review job not found")

    if validated_dir is not None:
        current_folder = job["scan_path"].rstrip("/") + "/" + validated_dir
    else:
        current_folder = job["scan_path"].rstrip("/")

    items = database.list_items(job_id, folder_prefix=current_folder)
    subdirs = database.directory_stats(job_id, current_folder)

    return templates.TemplateResponse(
        request,
        "job_detail.html",
        {
            "version": load_version(),
            "app_settings": settings,
            "job": job,
            "items": items,
            "subdirs": subdirs,
            "current_dir": validated_dir or "",
        },
    )


@app.post("/jobs")
def create_job_form(
    name: str = Form(""),
    scan_path: str = Form(""),
    notes: str = Form(""),
    scan_now: str = Form(""),
):
    if not name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")
    validated_path = validate_scan_path(scan_path)
    job = get_database().create_job(name=name.strip(), scan_path=validated_path, notes=notes.strip())
    job_id = job["job_id"]

    if scan_now == "true":
        _run_scan(job_id)

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/jobs/{job_id}/scan")
def scan_job_web(job_id: str):
    _run_scan(job_id)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=status.HTTP_303_SEE_OTHER)


def _run_scan(job_id: str) -> None:
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
        database.replace_items(job_id, items_data)
        database.update_job_status(job_id, "ready", total_items=len(items_data))
    except Exception:
        database.update_job_status(job_id, "failed")
        raise

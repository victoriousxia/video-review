from contextlib import asynccontextmanager
from dataclasses import asdict
import os
from pathlib import Path
import resource
import subprocess as sp

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings, load_version
from .database import get_database, path_is_under
from .frame_worker import FrameWorker
from .frames import list_frames
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

_frames_dir = settings.frames_dir
try:
    _frames_dir.mkdir(parents=True, exist_ok=True)
except OSError:
    import tempfile
    _frames_dir = Path(tempfile.mkdtemp())

app.mount("/frames", StaticFiles(directory=str(_frames_dir)), name="frames")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

frame_worker = FrameWorker(
    frames_dir=_frames_dir,
    max_workers=settings.frames_workers,
    default_count=settings.frames_count,
    default_quality=settings.frames_quality,
    default_max_width=settings.frames_max_width,
    default_skip_percent=settings.frames_skip_percent,
    default_timeout=settings.frames_timeout,
)


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
            "media_mutation": True,
        },
        "safety": {
            "review_only": False,
            "moves_files": False,
            "deletes_files": True,
            "delete_confirmation": "browser-confirm-dialog",
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


@app.post("/api/v1/items/{item_id}/frames")
def generate_item_frames(item_id: str, force: bool = False) -> dict:
    database = get_database()
    item = database.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")

    video_path = item["original_path"]
    if not Path(video_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="video file not found on disk")

    return frame_worker.submit(item_id, video_path, force=force)


@app.get("/api/v1/items/{item_id}/frames")
def get_item_frames(item_id: str) -> dict:
    database = get_database()
    item = database.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")

    return frame_worker.get_status(item_id)


@app.get("/api/v1/items/{item_id}/video")
def stream_video(item_id: str):
    database = get_database()
    item = database.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")

    video_path = Path(item["original_path"])
    if not video_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="video file not found on disk")

    ext = video_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".ts": "video/mp2t",
        ".flv": "video/x-flv",
    }
    media_type = media_types.get(ext, "video/mp4")
    return FileResponse(video_path, media_type=media_type)


@app.get("/api/v1/frame-tasks")
def list_frame_tasks() -> dict:
    database = get_database()
    with frame_worker._lock:
        active_ids = [
            (item_id, task.status, task.progress_current, task.progress_total)
            for item_id, task in frame_worker._tasks.items()
            if task.status in ("queued", "generating")
        ]
    active = []
    for item_id, task_status, progress_current, progress_total in active_ids:
        item = database.get_item(item_id)
        file_name = item["file_name"] if item else item_id
        active.append({
            "item_id": item_id,
            "file_name": file_name,
            "status": task_status,
            "progress_current": progress_current,
            "progress_total": progress_total,
        })
    return {"tasks": active, "count": len(active)}


@app.delete("/api/v1/frame-tasks/{item_id}")
def cancel_frame_task(item_id: str) -> dict:
    ok = frame_worker.cancel(item_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no active task for this item")
    return {"cancelled": item_id}


@app.delete("/api/v1/frame-tasks")
def cancel_all_frame_tasks() -> dict:
    count = frame_worker.cancel_all()
    return {"cancelled": count}


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
    delete_count = database.count_items_by_status(job_id, "delete_later", folder_prefix=current_folder)

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
            "delete_count": delete_count,
        },
    )


@app.post("/jobs")
def create_job_form(
    name: str = Form(""),
    scan_path: str = Form(""),
    notes: str = Form(""),
    scan_now: str = Form(""),
):
    validated_path = validate_scan_path(scan_path)
    job_name = name.strip() or Path(validated_path).name
    if not job_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")
    job = get_database().create_job(name=job_name, scan_path=validated_path, notes=notes.strip())
    job_id = job["job_id"]

    if scan_now == "true":
        _run_scan(job_id)

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/jobs/{job_id}/scan")
def scan_job_web(job_id: str):
    _run_scan(job_id)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.delete("/api/v1/jobs/{job_id}")
def delete_job_api(job_id: str) -> dict:
    database = get_database()
    job = database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review job not found")
    database.delete_job(job_id)
    return {"deleted": job_id}


@app.post("/jobs/{job_id}/delete")
def delete_job_web(job_id: str):
    database = get_database()
    job = database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review job not found")
    database.delete_job(job_id)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/api/v1/jobs/{job_id}/delete-files")
def delete_marked_files(job_id: str, dir: str | None = None) -> dict:
    database = get_database()
    job = database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review job not found")

    validated_dir = validate_dir_param(dir)
    if validated_dir is not None:
        folder_prefix = job["scan_path"].rstrip("/") + "/" + validated_dir
    else:
        folder_prefix = job["scan_path"].rstrip("/")

    items = database.list_items_by_status(job_id, "delete_later", folder_prefix=folder_prefix)

    deleted = []
    failed = []
    for item in items:
        file_path = Path(item["original_path"])
        try:
            if file_path.exists():
                file_path.unlink()
                deleted.append(item["item_id"])
            else:
                deleted.append(item["item_id"])
        except OSError as e:
            failed.append({"item_id": item["item_id"], "error": str(e)})

    if deleted:
        database.remove_items(deleted)

    return {"deleted": len(deleted), "failed": len(failed), "errors": failed}


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


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    frames_dir = settings.frames_dir
    frames_size = 0
    frames_count = 0
    if frames_dir.exists():
        for f in frames_dir.rglob("*.jpg"):
            frames_size += f.stat().st_size
            frames_count += 1
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "version": load_version(),
            "settings": {
                "frames_count": settings.frames_count,
                "frames_quality": settings.frames_quality,
                "frames_workers": settings.frames_workers,
                "frames_max_width": settings.frames_max_width,
                "frames_skip_percent": settings.frames_skip_percent,
                "frames_timeout": settings.frames_timeout,
                "frames_dir": str(frames_dir),
                "frames_disk_size_mb": round(frames_size / 1048576, 1),
                "frames_disk_count": frames_count,
            },
        },
    )


@app.get("/api/v1/settings")
def get_settings_api() -> dict:
    frames_dir = settings.frames_dir
    frames_size = 0
    frames_file_count = 0
    item_dirs = 0
    if frames_dir.exists():
        for d in frames_dir.iterdir():
            if d.is_dir():
                item_dirs += 1
                for f in d.iterdir():
                    if f.suffix == ".jpg":
                        frames_size += f.stat().st_size
                        frames_file_count += 1
    return {
        "frames_count": settings.frames_count,
        "frames_quality": settings.frames_quality,
        "frames_workers": settings.frames_workers,
        "frames_max_width": settings.frames_max_width,
        "frames_skip_percent": settings.frames_skip_percent,
        "frames_timeout": settings.frames_timeout,
        "frames_dir": str(frames_dir),
        "frames_disk_size_mb": round(frames_size / 1048576, 1),
        "frames_disk_files": frames_file_count,
        "frames_disk_items": item_dirs,
    }


@app.patch("/api/v1/settings")
def update_settings_api(body: dict) -> dict:
    updated = {}
    if "frames_count" in body:
        val = int(body["frames_count"])
        if 1 <= val <= 30:
            settings.frames_count = val
            frame_worker._default_count = val
            updated["frames_count"] = val
    if "frames_quality" in body:
        val = int(body["frames_quality"])
        if 1 <= val <= 10:
            settings.frames_quality = val
            frame_worker._default_quality = val
            updated["frames_quality"] = val
    if "frames_workers" in body:
        val = int(body["frames_workers"])
        if 1 <= val <= 8:
            settings.frames_workers = val
            frame_worker._executor._max_workers = val
            updated["frames_workers"] = val
    if "frames_max_width" in body:
        val = int(body["frames_max_width"])
        if 0 <= val <= 3840:
            settings.frames_max_width = val
            frame_worker._default_max_width = val
            updated["frames_max_width"] = val
    if "frames_skip_percent" in body:
        val = int(body["frames_skip_percent"])
        if 0 <= val <= 45:
            settings.frames_skip_percent = val
            frame_worker._default_skip_percent = val
            updated["frames_skip_percent"] = val
    if "frames_timeout" in body:
        val = int(body["frames_timeout"])
        if 5 <= val <= 120:
            settings.frames_timeout = val
            frame_worker._default_timeout = val
            updated["frames_timeout"] = val
    return {"updated": updated}


@app.post("/api/v1/settings/clear-frames")
def clear_all_frames() -> dict:
    import shutil
    frames_dir = settings.frames_dir
    removed = 0
    if frames_dir.exists():
        for d in list(frames_dir.iterdir()):
            if d.is_dir():
                shutil.rmtree(d)
                removed += 1
    with frame_worker._lock:
        frame_worker._tasks.clear()
    return {"removed_items": removed}


@app.get("/api/v1/debug/memory")
def debug_memory() -> dict:
    if not settings.debug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    rusage = resource.getrusage(resource.RUSAGE_SELF)
    rss_bytes = rusage.ru_maxrss
    if os.uname().sysname == "Darwin":
        rss_mb = rss_bytes / 1048576
    else:
        rss_mb = rss_bytes / 1024

    cgroup_mem: dict = {}
    try:
        with open("/sys/fs/cgroup/memory.current") as f:
            cgroup_mem["current_mb"] = int(f.read().strip()) / 1048576
        with open("/sys/fs/cgroup/memory.stat") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2 and parts[0] in ("file", "anon", "inactive_file", "active_file"):
                    cgroup_mem[parts[0] + "_mb"] = int(parts[1]) / 1048576
    except FileNotFoundError:
        try:
            with open("/sys/fs/cgroup/memory/memory.usage_in_bytes") as f:
                cgroup_mem["current_mb"] = int(f.read().strip()) / 1048576
            with open("/sys/fs/cgroup/memory/memory.stat") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) == 2 and parts[0] in ("total_cache", "total_rss", "total_inactive_file", "total_active_file"):
                        cgroup_mem[parts[0] + "_mb"] = int(parts[1]) / 1048576
        except FileNotFoundError:
            cgroup_mem["error"] = "not running in cgroup"

    with frame_worker._lock:
        task_counts = {}
        for t in frame_worker._tasks.values():
            task_counts[t.status] = task_counts.get(t.status, 0) + 1
        total_tracked = len(frame_worker._tasks)

    try:
        result = sp.run(["pgrep", "ffmpeg"], stdout=sp.PIPE, stderr=sp.DEVNULL, text=True)
        ffmpeg_count = len(result.stdout.strip().splitlines()) if result.returncode == 0 else 0
    except FileNotFoundError:
        ffmpeg_count = 0
    return {
        "python_rss_mb": round(rss_mb, 1),
        "cgroup": {k: round(v, 1) if isinstance(v, float) else v for k, v in cgroup_mem.items()},
        "frame_worker": {
            "task_counts": task_counts,
            "total_tracked": total_tracked,
        },
        "ffmpeg_processes": ffmpeg_count,
    }

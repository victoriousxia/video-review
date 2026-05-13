# Changelog

## 0.2.0 - 2026-05-13

Docker/Lucky deployment flow and review-job foundation:
- Added SQLite initialization at service startup.
- Added `review_jobs`, `review_items`, and `schema_meta` tables.
- Added review job API endpoints:
  - `GET /api/v1/jobs`
  - `POST /api/v1/jobs`
  - `GET /api/v1/jobs/{job_id}`
- Added scan-path validation so jobs must stay under configured media roots.
- Added HTML pages for `/jobs` and `/jobs/{job_id}`.
- Updated the home page to show recent jobs, database path, public URL, and v0.2.0 safety state.
- Marked `scan_jobs: true` while keeping `media_mutation: false`.
- Verified Docker image build on NAS without changing global Docker daemon DNS.
- Verified a container can start, initialize SQLite, and create/read a smoke-test job from inside the container.
- Documented Lucky reverse proxy deployment flow.

Notes:
- v0.2.0 creates task records only; it does not scan real video files yet.
- v0.2.0 does not generate screenshots yet.
- v0.2.0 does not move, rename, or delete any media files.
- Host-to-container curl from the Hermes execution namespace still reports connection refused even when Docker publishes the port and the service works inside the container. Validate Lucky from NAS UI/host-side access, not only from this Hermes namespace.

## 0.1.0 - 2026-05-13

Runnable Docker/service foundation:
- Kept the project as a generic Docker service with optional Hermes orchestration.
- Added FastAPI app shell with `/`, `/healthz`, and `/api/v1/info`.
- Added explicit capability flags so clients can see which features are enabled.
- Added explicit safety flags showing this version is review-only and will not move or delete media.
- Added writable app data subdirectories for screenshots, jobs, and logs.
- Switched startup from deprecated FastAPI `on_event` to lifespan startup.
- Adjusted Dockerfile to avoid `apt-get` and global Docker daemon DNS changes.
- Verified Docker image build on the NAS using the locally available Open WebUI base image.
- Verified API/unit tests inside the existing Open WebUI Python environment.

Notes:
- v0.1.0 does not scan videos yet.
- v0.1.0 does not generate screenshots yet.
- v0.1.0 does not move, rename, or delete any media files.
- The Dockerfile currently defaults to `openwebui/open-webui:0.9.5` as a pragmatic NAS-local base image because the NAS Docker build environment cannot resolve external package indexes reliably. This is temporary and should be replaced by a purpose-built runtime image when network/build constraints are solved.

## 0.1.0-dev

Initial Docker project skeleton:
- FastAPI app shell
- health check
- configuration model
- project documentation
- Dockerfile and docker-compose

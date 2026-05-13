# Changelog

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

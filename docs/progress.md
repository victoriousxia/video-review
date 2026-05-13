# Progress

Current version: 0.2.0

## Completed

- Chosen repository path: `/nas/docker/video-review`
- Initialized Git repository on `main`
- Configured GitHub remote: `git@github.com:victoriousxia/video-review.git`
- Configured repository-scoped GitHub deploy key for NAS/Hermes push access
- Pushed initial `main` branch to GitHub
- Defined generic Docker-service-first architecture
- Defined optional Hermes integration boundary
- Added project docs skeleton
- Added FastAPI skeleton with `/`, `/healthz`, and `/api/v1/info`
- Added app-owned data subdirectories:
  - `/app/data/screenshots`
  - `/app/data/jobs`
  - `/app/data/logs`
- Added Dockerfile and `docker-compose.yml`
- Avoided global Docker daemon DNS changes after they disrupted Hermes/Open WebUI model connectivity
- Released v0.1.0 runnable service foundation
- Released v0.2.0 Docker/Lucky flow and review-job foundation
- Added SQLite startup initialization
- Added SQLite tables:
  - `schema_meta`
  - `review_jobs`
  - `review_items`
- Added API endpoints:
  - `GET /api/v1/jobs`
  - `POST /api/v1/jobs`
  - `GET /api/v1/jobs/{job_id}`
- Added scan-path validation limited to configured download/library roots
- Added web pages:
  - `/jobs`
  - `/jobs/{job_id}`
- Updated `/` to show recent jobs and deployment configuration
- Added Lucky deployment documentation

## In progress

- User-side Lucky reverse proxy validation for the running Docker service

## Pending

- Actual video file scanning
- Basic video item creation under a review job
- ffprobe metadata extraction
- screenshot batch generation and regeneration
- Review decisions
- execution dry-run plans
- Hermes-triggered notifications

## Last verification

- GitHub SSH deploy-key authentication previously succeeded for `victoriousxia/video-review`.
- `docker build -t video-review:v0.2.0 .` succeeded on the NAS without `apt-get` and without changing Docker daemon DNS.
- `docker run --name video-review-v020-test -p 18818:8818 ... video-review:v0.2.0` started successfully; logs showed Uvicorn running on `0.0.0.0:8818`.
- Inside the running container, `GET /healthz` returned OK and `GET /api/v1/jobs` returned an empty job list.
- Inside the running container, `POST /api/v1/jobs` created a smoke-test job and `GET /api/v1/jobs/{job_id}` read it back successfully.
- Unit tests passed inside the project image with the real host path mount: `8 passed`.

## Important environment note

Do not require or recommend changing NAS global Docker daemon DNS for this project. A previous daemon-level DNS change disrupted Hermes/Open WebUI/model connectivity and was reverted from backup. The project must use low-risk build/deploy strategies that do not alter existing container networking globally.

## Build note

The Dockerfile currently defaults to `openwebui/open-webui:0.9.5` as a temporary NAS-local base image because it already exists locally and contains FastAPI/Uvicorn/Jinja2/Pytest dependencies. This makes the current versions buildable without external package downloads. Replace with a lean purpose-built image later when package-index DNS/build reliability is solved.

## Network note

Host-to-container published-port probing from the Hermes execution namespace returned connection refused even when Docker showed `0.0.0.0:18818->8818/tcp` and the service worked inside the container. Treat Hermes-side curl against host-published ports as unreliable in this environment. Validate Lucky access from NAS UI, browser, or host-side network path.

# Progress

Current version: 0.1.0

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
- Added explicit API capability flags:
  - `review_web: true`
  - `healthcheck: true`
  - `scan_jobs: false`
  - `screenshot_batches: false`
  - `execution_plans: false`
  - `media_mutation: false`
- Added explicit API safety flags:
  - `review_only: true`
  - `moves_files: false`
  - `deletes_files: false`
- Added app-owned data subdirectories:
  - `/app/data/screenshots`
  - `/app/data/jobs`
  - `/app/data/logs`
- Added Dockerfile and `docker-compose.yml`
- Avoided global Docker daemon DNS changes after they disrupted Hermes/Open WebUI model connectivity
- Promoted version from `0.1.0-dev` to `0.1.0`

## In progress

- Preparing v0.2.0: SQLite initialization and scan job model

## Pending

- SQLite initialization
- scan job model
- video scanning
- ffprobe metadata
- screenshot batch generation and regeneration
- Review UI
- Lucky reverse proxy documentation

## Last verification

- GitHub SSH deploy-key authentication succeeded for `victoriousxia/video-review`.
- GitHub remote push previously succeeded; current v0.1.0 changes are ready to push.
- `python -m pytest tests -q` passed inside the existing `open-webui` container Python environment: `5 passed`.
- `docker build -t video-review:test .` succeeded on the NAS without `apt-get` and without changing Docker daemon DNS.
- A test container started with `docker run --name video-review-test -d -p 18818:8818 ... video-review:test` and Uvicorn logged successful startup on port 8818.
- Host-to-container published-port probing from inside the Hermes execution environment returned connection-refused despite container logs showing startup; this appears to be a host/network namespace probing limitation and needs separate investigation before relying on host-side curl from Hermes.

## Important environment note

Do not require or recommend changing NAS global Docker daemon DNS for this project. A previous daemon-level DNS change disrupted Hermes/Open WebUI/model connectivity and was reverted from backup. The project must use low-risk build/deploy strategies that do not alter existing container networking globally.

## Build note

The Dockerfile currently defaults to `openwebui/open-webui:0.9.5` as a temporary NAS-local base image because it already exists locally and contains FastAPI/Uvicorn/Jinja2/Pytest dependencies. This makes v0.1.0 buildable without external package downloads. Replace with a lean purpose-built image later when package-index DNS/build reliability is solved.

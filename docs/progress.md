# Progress

Current version: 0.1.0-dev

## Completed

- Chosen repository path: `/nas/docker/video-review`
- Initialized Git repository on `main`
- Configured GitHub remote: `git@github.com:victoriousxia/video-review.git`
- Configured repository-scoped GitHub deploy key for NAS/Hermes push access
- Pushed initial `main` branch to GitHub
- Defined generic Docker-service-first architecture
- Defined optional Hermes integration boundary
- Added project docs skeleton
- Added FastAPI skeleton with `/healthz`, `/api/v1/info`, and index page
- Added Dockerfile, `docker-compose.yml`, `.env.example`, and pytest skeleton

## In progress

- v0.1.0 verification in the NAS environment

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
- `git push -u origin main` succeeded; remote `main` points to commit `a4f73c29728bdfbc5d6d867b880e12913c476a04` before the collaboration-doc update.
- `python3 -m pytest -q` failed because the host Python lacks pytest.
- Creating a local virtual environment failed because the host Python lacks `ensurepip` / `python3.13-venv`.
- `docker compose config` and `docker-compose config` are unavailable in the Hermes container.
- `docker build -t video-review:test .` reached the Docker daemon but failed during `apt-get update` due DNS resolution failure for `deb.debian.org` inside the Docker build environment.
- Attempting to fix Docker build by changing global Docker daemon DNS disrupted existing containers' model/network access; do not require global Docker daemon DNS changes for this project.

These are environment/tooling blockers, not application-code test failures. Next implementation step is to make the Docker build avoid global daemon DNS assumptions, for example by using a base image that already contains required runtime dependencies or deferring ffmpeg checks to runtime.

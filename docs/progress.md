# Progress

Current version: 0.1.0-dev

## Completed

- Chosen repository path: `/nas/docker/video-review`
- Initialized Git repository on `main`
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

- `python3 -m pytest -q` failed because the host Python lacks pytest.
- Creating a local virtual environment failed because the host Python lacks `ensurepip` / `python3.13-venv`.
- `docker compose config` and `docker-compose config` are unavailable in the Hermes container.
- `docker build -t video-review:test .` reached the Docker daemon but failed during `apt-get update` due DNS resolution failure for `deb.debian.org` inside the Docker build environment.

These are environment/tooling blockers, not application-code test failures. Next implementation step is either fixing Docker build DNS / compose availability or using an existing base image with dependencies cached.

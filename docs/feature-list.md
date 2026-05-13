# Feature List

## Supported in 0.1.0

- Standard Git-managed Docker project structure
- GitHub collaboration workflow through `victoriousxia/video-review`
- FastAPI app shell
- Mobile-friendly placeholder index page
- `/healthz` health endpoint
- `/api/v1/info` service info endpoint
- Explicit capability flags for automation clients
- Explicit safety flags showing the service is review-only
- App-owned data directories for future screenshots, jobs, and logs
- Documented generic-service-first architecture
- Documented optional Hermes integration boundary
- Documented safety rules
- Docker image builds on the current NAS without changing global Docker daemon DNS

## Not supported yet

- Creating review jobs
- SQLite database initialization
- Video scanning
- ffprobe metadata extraction
- Screenshot generation
- Dynamic screenshot regeneration
- Review decisions
- Execution dry-run plans
- File move/rename/trash execution
- Hermes-triggered notifications
- Scheduled scans

## Planned

- video scanning
- metadata extraction
- screenshot batches
- dynamic screenshot regeneration
- review decisions
- safe dry-run plans
- safe execution with trash-first deletion
- Hermes-triggered notifications
- scheduled scans

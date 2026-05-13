# Feature List

## Supported in 0.2.0

- Standard Git-managed Docker project structure
- GitHub collaboration workflow through `victoriousxia/video-review`
- FastAPI app shell
- Mobile-friendly home page
- `/healthz` health endpoint
- `/api/v1/info` service info endpoint
- Explicit capability flags for automation clients
- Explicit safety flags showing the service is review-only
- App-owned data directories for future screenshots, jobs, and logs
- Documented generic-service-first architecture
- Documented optional Hermes integration boundary
- Documented safety rules
- Docker image builds on the current NAS without changing global Docker daemon DNS
- SQLite initialization on startup
- `review_jobs`, `review_items`, and `schema_meta` tables
- Review job creation API
- Review job list API
- Review job detail API
- Scan-path validation under configured media roots
- `/jobs` web page
- `/jobs/{job_id}` web page
- Lucky reverse proxy deployment flow documentation

## Not supported yet

- Actual recursive video scanning
- Populating `review_items` from real files
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

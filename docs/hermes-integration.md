# Hermes Integration

video-review is not strongly coupled to Hermes.

## Recommended model

The Docker service exposes standard HTTP endpoints and later a CLI. Hermes acts as an orchestrator:

- user says: scan a folder for review
- Hermes calls video-review API
- video-review returns job id and URL
- Hermes sends the URL to the same message channel
- user reviews in browser
- user says: generate plan or execute
- Hermes calls dry-run API, summarizes, and asks for explicit confirmation
- Hermes calls execution API only after confirmation

## Why not strong coupling

Strong coupling would make the app hard to use from Mac, cron, shell, or other services. It would also mix messaging credentials with media-management code.

## Standard API surface planned

- `GET /healthz`
- `GET /api/v1/info`
- `POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/progress`
- `POST /api/v1/items/{item_id}/screenshots/regenerate`
- `POST /api/v1/items/{item_id}/decision`
- `POST /api/v1/jobs/{job_id}/plan`
- `POST /api/v1/jobs/{job_id}/execute` guarded by confirmation token in later versions

## Notifications

video-review should not send Telegram/WeChat messages itself in V1. It returns machine-readable status and links; Hermes delivers the notification through the active channel.

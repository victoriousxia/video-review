# Hermes Integration

video-review is not strongly coupled to Hermes. Current deletion is handled inside the web app after browser confirmation; there is no Hermes approval workflow or HTTP hook in the current deployment.

## Recommended model

The Docker service exposes standard HTTP endpoints and later a CLI. Hermes acts as an orchestrator:

- user says: scan a folder for review
- Hermes calls video-review API
- video-review returns job id and URL
- Hermes sends the URL to the same message channel
- user reviews in browser
- user marks files as delete_later
- user clicks the delete button and confirms the browser dialog
- video-review deletes the marked files directly through its writable media mounts

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
- `POST /api/v1/jobs/{job_id}/delete-files`

## Notifications

video-review does not send Telegram/WeChat messages itself. In the current direct-delete mode, deletion confirmation happens in the browser instead of through Hermes chat approval.

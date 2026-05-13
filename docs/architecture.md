# Architecture

video-review is intentionally split into a generic Docker service and optional orchestrators.

## Core service

- FastAPI HTTP app
- SQLite database under data directory
- scanner module for filesystem discovery
- metadata module using ffprobe
- screenshot service using ffmpeg
- review UI and APIs
- execution planner and safe executor in later versions

## Hermes integration boundary

The service must not depend on Hermes internals.

Integration should happen through stable surfaces:

1. HTTP API
   - create scan job
   - query job status
   - get review progress
   - generate dry-run plan
   - apply confirmed plan in later versions

2. CLI wrapper
   - `video-review scan PATH`
   - `video-review job JOB_ID`
   - `video-review plan JOB_ID`

3. Notifications
   - Hermes sends messages to Telegram/WeChat/Open WebUI/etc.
   - video-review only returns status/link payloads

This makes the app usable from cron, shell, or another assistant, not only Hermes.

## Paths

Container defaults:

- `/media/download` read-only source downloads
- `/media/library` read-write library target
- `/app/data` application data

NAS defaults in compose:

- `/nas/download:/media/download:ro`
- `/nas/media:/media/library:rw`
- `./data:/app/data`

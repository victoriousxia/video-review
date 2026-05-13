# Lucky Reverse Proxy Deployment

video-review is a normal HTTP Docker service. Lucky should reverse proxy to the service port and provide HTTPS plus authentication.

## Recommended topology

External browser/channel link:

```text
https://video-review.example.com
```

Lucky target:

```text
http://NAS_IP:8818
```

or, if Lucky can reach Docker container names on the same Docker network:

```text
http://video-review:8818
```

## Authentication

Recommended for v0.x:

1. Lucky provides HTTPS and account/password access.
2. video-review runs with `VIDEO_REVIEW_AUTH_MODE=proxy`.
3. The application itself stays review-only until execution features are added.

Do not expose the service without Lucky/authentication.

## Start the service

On the NAS host or any environment with Docker Compose access:

```bash
cd /vol2/1000/Docker/video-review
cp .env.example .env
```

Edit `.env` if needed:

```text
VIDEO_REVIEW_PUBLIC_BASE_URL=https://video-review.example.com
VIDEO_REVIEW_DOWNLOAD_ROOT=/media/download
VIDEO_REVIEW_LIBRARY_ROOT=/media/library
VIDEO_REVIEW_AUTH_MODE=proxy
```

Start:

```bash
docker compose up -d --build
```

or:

```bash
docker-compose up -d --build
```

If Compose is unavailable, the equivalent manual run for validation is:

```bash
docker build -t video-review:local .
docker run -d \
  --name video-review \
  --restart unless-stopped \
  -p 8818:8818 \
  -e VIDEO_REVIEW_PUBLIC_BASE_URL=https://video-review.example.com \
  -v /vol2/1000/Docker/video-review/data:/app/data \
  -v /vol1/1000/Download:/media/download:ro \
  -v /vol1/1000/Media:/media/library:rw \
  video-review:local
```

## Validate before Lucky

From a browser or NAS host network path, open:

```text
http://NAS_IP:8818/
http://NAS_IP:8818/healthz
http://NAS_IP:8818/jobs
```

Expected:

- `/healthz` returns JSON with `ok: true`.
- `/` shows the service home page.
- `/jobs` shows an empty task list or created tasks.

## Create a smoke-test review job

```bash
curl -X POST http://NAS_IP:8818/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"name":"Lucky smoke test","scan_path":"/media/download","notes":"created to verify deployment"}'
```

Then open:

```text
http://NAS_IP:8818/jobs
```

## Current limitation

v0.2.0 only creates review-job records. It does not scan real videos, generate screenshots, move files, rename files, or delete files.

## Environment warning

Do not change the NAS global Docker daemon DNS for this project. A prior global Docker DNS change disrupted Hermes/Open WebUI/model connectivity. The project must be deployable without changing global Docker networking.

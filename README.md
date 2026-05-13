# video-review

NAS video organization review service.

It scans video folders, records metadata, generates screenshot batches, lets the user review organization decisions in a web UI, and later produces safe execution plans. The first versions are review-only and do not move or delete media.

## Design stance

video-review is a general Docker service first, with optional Hermes integration.

Core service responsibilities:
- scan configured media roots
- generate and regenerate screenshot batches
- store review jobs and decisions
- expose a mobile-friendly review web UI
- expose HTTP/CLI APIs for automation

Hermes responsibilities:
- trigger scans from chat commands
- send links/notifications through the current channel
- read review state
- ask for explicit confirmation before execution
- call the service API or CLI to generate/apply plans

This keeps the Docker service usable without Hermes while allowing Hermes to orchestrate it.

## Current version

See `VERSION`, `CHANGELOG.md`, `ROADMAP.md`, and `docs/progress.md`.

## Local Docker start

```bash
cp .env.example .env
# Use whichever compose command is installed on the NAS host:
docker compose up -d --build
# or:
docker-compose up -d --build
```

Open:

```text
http://NAS_IP:8818
```

Lucky reverse proxy should point to port 8818 and provide HTTPS + authentication.

## Mac development / pulling code

This repository lives on the NAS at:

```text
/nas/docker/video-review
```

Recommended options from Mac:

1. Use your NAS file sharing / SMB path and clone/copy from the shared Docker directory.
2. If SSH is enabled on the NAS, clone directly from the repository path:

```bash
git clone ssh://USER@NAS_IP/nas/docker/video-review
```

Depending on the NAS SSH server, the absolute path may need this form:

```bash
git clone USER@NAS_IP:/vol2/1000/Docker/video-review
```

3. Later, add a private Git remote such as Gitea/GitHub and push/pull normally.

Hermes will maintain Git commits locally in this repository so your changes can be merged/reviewed.

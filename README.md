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

Canonical remote repository:

```text
https://github.com/victoriousxia/video-review
```

Clone on Mac:

```bash
git clone git@github.com:victoriousxia/video-review.git
```

The NAS working copy lives at:

```text
/nas/docker/video-review
```

Collaboration rules:

1. Pull before editing or continuing work:

```bash
git pull --ff-only
```

2. Commit focused changes with clear messages.
3. Push to GitHub after each coherent milestone.
4. Hermes will also pull before modifying code to avoid overwriting Mac-side commits.
5. If both Mac and Hermes change the same files, resolve through normal Git merge/rebase rather than editing the NAS copy out of band.

NAS deploy key:

The NAS/Hermes environment uses a repository-scoped GitHub deploy key with write access, not a personal SSH key. This keeps access limited to `victoriousxia/video-review`.

Direct NAS-path cloning is no longer the recommended workflow. Use GitHub as the shared source of truth.

ARG BASE_IMAGE=openwebui/open-webui:0.9.5
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The temporary open-webui base image carries its own HEALTHCHECK. Disable it
# here so video-review health is controlled by docker-compose.yml and points to
# the video-review port instead of Open WebUI's default port.
HEALTHCHECK NONE

COPY pyproject.toml /app/pyproject.toml
COPY app /app/app
COPY VERSION /app/VERSION

RUN mkdir -p /app/data

EXPOSE 8818
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8818"]

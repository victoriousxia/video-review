#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-/vol2/1000/Docker/video-review}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.nas.yml}"
BRANCH="${BRANCH:-main}"
HEALTH_URL="${HEALTH_URL:-}"

# This repo may be operated from two environments:
# - NAS host:   /vol2/1000/Docker/hermes/data/... is visible
# - Hermes container: /opt/data/... is visible
# The repo-local git config may point at the container path, so the deploy script
# overrides it with whichever deploy key exists in the current environment.
DEPLOY_KEY="${DEPLOY_KEY:-}"

log() {
  printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"
}

configure_git_ssh() {
  if [ -n "$DEPLOY_KEY" ]; then
    :
  elif [ -f /vol2/1000/Docker/hermes/data/home/.ssh/video_review_github_deploy ]; then
    DEPLOY_KEY="/vol2/1000/Docker/hermes/data/home/.ssh/video_review_github_deploy"
  elif [ -f /opt/data/home/.ssh/video_review_github_deploy ]; then
    DEPLOY_KEY="/opt/data/home/.ssh/video_review_github_deploy"
  fi

  if [ -n "$DEPLOY_KEY" ]; then
    chmod 600 "$DEPLOY_KEY" 2>/dev/null || true
    export GIT_SSH_COMMAND="ssh -i $DEPLOY_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
    log "使用 GitHub deploy key: $DEPLOY_KEY"
  else
    log "未找到项目 deploy key，将使用当前用户默认 SSH/Git 凭据"
  fi
}

cd "$PROJECT_DIR"
configure_git_ssh

log "当前目录: $(pwd)"
log "检查 Git 状态"
git status --short --branch

if [ -n "$(git status --porcelain)" ]; then
  log "检测到本地未提交/未跟踪变更。为避免覆盖本地改动，已停止。"
  log "如果只有 _deploy_backups/，请确认 .gitignore 已包含 _deploy_backups/ 后重新执行。"
  git status --short
  exit 1
fi

log "拉取最新代码: origin/$BRANCH"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

log "部署: docker compose -f $COMPOSE_FILE up -d --build"
if docker compose version >/dev/null 2>&1; then
  docker compose -f "$COMPOSE_FILE" up -d --build
  log "容器状态"
  docker compose -f "$COMPOSE_FILE" ps
  log "最近日志"
  docker compose -f "$COMPOSE_FILE" logs --tail=80
else
  docker-compose -f "$COMPOSE_FILE" up -d --build
  log "容器状态"
  docker-compose -f "$COMPOSE_FILE" ps
  log "最近日志"
  docker-compose -f "$COMPOSE_FILE" logs --tail=80
fi

if [ -n "$HEALTH_URL" ]; then
  log "健康检查: $HEALTH_URL"
  curl -fsS "$HEALTH_URL"
  printf '\n'
fi

log "部署完成"

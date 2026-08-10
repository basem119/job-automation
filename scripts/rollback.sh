#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="/opt/apps/job-automation"
RELEASES_DIR="$APP_ROOT/releases"
CURRENT_LINK="$APP_ROOT/current"
SERVICE_NAME="job-automation.service"
TIMER_NAME="job-automation.timer"

log() {
  printf '[rollback] %s\n' "$1"
}

usage() {
  cat <<'EOF'
Usage:
  rollback.sh                 # Roll back to previous release automatically
  rollback.sh <release_id>    # Roll back to a specific release
EOF
}

if [[ ! -d "$RELEASES_DIR" ]]; then
  log "Releases directory does not exist: $RELEASES_DIR"
  exit 1
fi

if [[ ! -L "$CURRENT_LINK" ]]; then
  log "Current symlink does not exist: $CURRENT_LINK"
  exit 1
fi

current_target="$(readlink -f "$CURRENT_LINK")"
target_release=""

if [[ $# -gt 1 ]]; then
  usage
  exit 1
fi

if [[ $# -eq 1 ]]; then
  release_id="$1"
  target_release="$RELEASES_DIR/$release_id"
  if [[ ! -d "$target_release" ]]; then
    log "Release does not exist: $target_release"
    exit 1
  fi
else
  mapfile -t release_dirs < <(find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%P\n' | sort)
  for ((idx=${#release_dirs[@]}-1; idx>=0; idx--)); do
    candidate="$RELEASES_DIR/${release_dirs[$idx]}"
    if [[ "$candidate" != "$current_target" ]]; then
      target_release="$candidate"
      break
    fi
  done

  if [[ -z "$target_release" ]]; then
    log "No previous release available"
    exit 1
  fi
fi

if [[ "$target_release" == "$current_target" ]]; then
  log "Target release is already active: $target_release"
  exit 0
fi

ln -sfn "$target_release" "$APP_ROOT/current.new"
mv -Tf "$APP_ROOT/current.new" "$CURRENT_LINK"

sudo systemctl restart "$SERVICE_NAME"
result="$(sudo systemctl show "$SERVICE_NAME" -p Result --value)"

if [[ "$result" != "success" ]]; then
  log "Service restart after rollback failed with Result=$result"
  sudo systemctl status "$SERVICE_NAME" --no-pager || true
  exit 1
fi

if ! sudo systemctl is-active --quiet "$TIMER_NAME"; then
  log "Timer is not active after rollback: $TIMER_NAME"
  exit 1
fi

log "Rollback successful"
log "Current target: $(readlink -f "$CURRENT_LINK")"
log "Systemd execution result: $result"

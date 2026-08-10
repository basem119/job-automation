#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="/opt/apps/job-automation"
RELEASES_DIR="$APP_ROOT/releases"
CURRENT_LINK="$APP_ROOT/current"
SHARED_DIR="$APP_ROOT/shared"
VENV_PYTHON="$SHARED_DIR/venv/bin/python"
VENV_PIP="$SHARED_DIR/venv/bin/pip"
SERVICE_NAME="job-automation.service"
TIMER_NAME="job-automation.timer"

log() {
  printf '[deploy] %s\n' "$1"
}

usage() {
  cat <<'EOF'
Usage: deploy.sh --commit <sha> --archive <path-to-tar.gz>

Required arguments:
  --commit    Exact Git commit SHA being deployed
  --archive   Path to tracked-source tar.gz archive already present on server
EOF
}

COMMIT_SHA=""
ARCHIVE_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --commit)
      COMMIT_SHA="${2:-}"
      shift 2
      ;;
    --archive)
      ARCHIVE_PATH="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$COMMIT_SHA" || -z "$ARCHIVE_PATH" ]]; then
  usage
  exit 1
fi

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  log "Archive not found: $ARCHIVE_PATH"
  exit 1
fi

if [[ ! -x "$VENV_PYTHON" || ! -x "$VENV_PIP" ]]; then
  log "Production virtual environment is missing: $SHARED_DIR/venv"
  exit 1
fi

if [[ ! -d "$RELEASES_DIR" || ! -d "$SHARED_DIR" ]]; then
  log "Application root is not initialized: $APP_ROOT"
  exit 1
fi

for required_path in \
  "$SHARED_DIR/database" \
  "$SHARED_DIR/oauth" \
  "$SHARED_DIR/resumes" \
  "$SHARED_DIR/cache"; do
  if [[ ! -d "$required_path" ]]; then
    log "Required shared directory missing: $required_path"
    exit 1
  fi
done

for required_file in \
  "$SHARED_DIR/oauth/token.json" \
  "$SHARED_DIR/oauth/gmail_oauth_client.json" \
  "$SHARED_DIR/database/jobs.db"; do
  if [[ ! -f "$required_file" ]]; then
    log "Required shared file missing: $required_file"
    exit 1
  fi
done

release_id="$(date -u +%Y%m%d-%H%M%S)"
release_path="$RELEASES_DIR/$release_id"
release_parent="$(dirname "$release_path")"
previous_release=""
release_switched=0

if [[ -L "$CURRENT_LINK" ]]; then
  previous_release="$(readlink -f "$CURRENT_LINK")"
fi

rollback_to_previous() {
  if [[ "$release_switched" -eq 1 && -n "$previous_release" && -d "$previous_release" ]]; then
    log "Deployment failed after activation. Rolling back to previous release: $previous_release"
    ln -sfn "$previous_release" "$APP_ROOT/current.new"
    mv -Tf "$APP_ROOT/current.new" "$CURRENT_LINK"

    sudo systemctl restart "$SERVICE_NAME"
    rollback_result="$(sudo systemctl show "$SERVICE_NAME" -p Result --value || true)"
    log "Rollback service Result=$rollback_result"
  fi
}

on_error() {
  exit_code="$1"
  rollback_to_previous
  log "Deployment failed"
  log "Current release preserved"
  exit "$exit_code"
}

trap 'on_error "$?"' ERR

log "Deployment started"
log "Commit SHA: $COMMIT_SHA"
log "Release ID: $release_id"

mkdir -p "$release_parent"
mkdir -p "$release_path"

tar -xzf "$ARCHIVE_PATH" -C "$release_path"

if [[ -d "$release_path/.git" ]]; then
  log "Release archive unexpectedly contains .git directory"
  exit 1
fi

if [[ -d "$release_path/shared" || -L "$release_path/shared" ]]; then
  rm -rf "$release_path/shared"
fi
ln -s "$SHARED_DIR" "$release_path/shared"

if [[ ! -f "$release_path/requirements.txt" || ! -f "$release_path/app/main.py" ]]; then
  log "Release archive does not contain expected project files"
  exit 1
fi

log "Installing dependencies in shared venv"
"$VENV_PYTHON" -m pip install -r "$release_path/requirements.txt"

log "Running pip check"
"$VENV_PIP" check
log "Dependencies passed"

log "Running test suite"
(
  cd "$release_path"
  "$VENV_PYTHON" -m unittest discover -s tests -p "test_*.py"
)
log "Tests passed"

ln -sfn "$release_path" "$APP_ROOT/current.new"
mv -Tf "$APP_ROOT/current.new" "$CURRENT_LINK"
release_switched=1

current_target="$(readlink -f "$CURRENT_LINK")"
if [[ "$current_target" != "$release_path" ]]; then
  log "Current symlink activation check failed"
  exit 1
fi
if [[ ! -f "$CURRENT_LINK/app/main.py" ]]; then
  log "Activated release is missing app/main.py"
  exit 1
fi

log "Release activated"
log "Current target: $current_target"

"$VENV_PYTHON" --version
"$VENV_PIP" check

if ! sudo systemctl is-active --quiet "$TIMER_NAME"; then
  log "Timer is not active: $TIMER_NAME"
  exit 1
fi

sudo systemctl restart "$SERVICE_NAME"
service_result="$(sudo systemctl show "$SERVICE_NAME" -p Result --value)"
log "Systemd execution result: $service_result"

if [[ "$service_result" != "success" ]]; then
  sudo systemctl status "$SERVICE_NAME" --no-pager || true
  exit 1
fi

sudo journalctl -u "$SERVICE_NAME" -n 100 --no-pager || true

for readable_path in \
  "$SHARED_DIR/database/jobs.db" \
  "$SHARED_DIR/oauth/token.json" \
  "$SHARED_DIR/oauth/gmail_oauth_client.json"; do
  if [[ ! -r "$readable_path" ]]; then
    log "Cannot read required shared file: $readable_path"
    exit 1
  fi
done

mapfile -t release_dirs < <(find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%P\n' | sort)
keep_count=3
if (( ${#release_dirs[@]} > keep_count )); then
  delete_count=$(( ${#release_dirs[@]} - keep_count ))
  for ((i=0; i<delete_count; i++)); do
    old_release="$RELEASES_DIR/${release_dirs[$i]}"
    if [[ "$old_release" != "$current_target" ]]; then
      rm -rf "$old_release"
      log "Deleted old release: $old_release"
    fi
  done
fi

log "Deployment successful"

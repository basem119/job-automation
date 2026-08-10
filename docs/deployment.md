# Production Deployment via GitHub Actions

This project uses release-based deployment to Ubuntu VPS.

## Goals and Safety Guarantees

- Every deployment creates a new immutable release directory under `/opt/apps/job-automation/releases/<release_id>`.
- `current` switches only after dependency checks, tests, and validations pass.
- Runtime/persistent data under `/opt/apps/job-automation/shared/` is never overwritten.
- The existing production virtual environment is reused: `/opt/apps/job-automation/shared/venv`.
- Deployments are atomic and rollback-capable.
- `job-automation.timer` is preserved and must remain active.

## Files in this repository

- `.github/workflows/deploy.yml`
- `scripts/deploy.sh`
- `scripts/rollback.sh`

## Required GitHub Secrets

- `DEPLOY_HOST`: VPS host or IP
- `DEPLOY_USER`: deployment SSH user (for this setup: `deploy`)
- `DEPLOY_SSH_KEY`: private key matching the deploy public key installed on the VPS
- `DEPLOY_PORT` (optional): SSH port; defaults to `22`

## How deployment works

1. Push to `main` triggers `.github/workflows/deploy.yml`.
2. Workflow archives the exact triggering commit (`GITHUB_SHA`) using `git archive`.
3. Workflow uploads archive to `/tmp` on VPS over SSH.
4. Workflow invokes `/opt/apps/job-automation/deploy.sh --commit <sha> --archive <uploaded-archive>`.
5. Server script:
   - creates a timestamped release directory
   - extracts tracked files into the release
   - installs dependencies into shared venv
   - runs `pip check`
   - runs full unit test suite
   - atomically switches `current`
   - restarts and validates `job-automation.service`
   - verifies `job-automation.timer` remains active
   - keeps current + previous 2 releases and cleans older ones

If any pre-activation step fails, `current` is unchanged.
If post-activation execution fails, script rolls back `current` to previous release.

## VPS one-time setup

Run as a privileged admin user.

### 1) Ensure base directories exist

```bash
sudo mkdir -p /opt/apps/job-automation/{releases,logs,shared}
sudo mkdir -p /opt/apps/job-automation/shared/{cache,database,oauth,resumes}
```

### 2) Ensure ownership model

Recommended:
- application runtime owner: `automation`
- deployment SSH user: `deploy`
- both share group `automation`

```bash
sudo usermod -aG automation deploy
sudo chown -R automation:automation /opt/apps/job-automation/shared
sudo chmod -R o-rwx /opt/apps/job-automation/shared/oauth
sudo chmod -R g-rwx /opt/apps/job-automation/shared/oauth
sudo chown -R deploy:automation /opt/apps/job-automation/releases /opt/apps/job-automation/logs
sudo chown deploy:automation /opt/apps/job-automation
sudo chmod 2775 /opt/apps/job-automation/releases
```

Notes:
- Shared secrets remain owned by `automation`.
- Deploy process does not modify `shared` files.

### 3) Install deployment and rollback scripts

From repository root on VPS:

```bash
sudo install -o root -g root -m 0755 scripts/deploy.sh /opt/apps/job-automation/deploy.sh
sudo install -o root -g root -m 0755 scripts/rollback.sh /opt/apps/job-automation/rollback.sh
```

### 4) Configure minimal sudoers for deploy user

Create `/etc/sudoers.d/job-automation-deploy`:

```sudoers
Defaults:deploy !requiretty

deploy ALL=(root) NOPASSWD: /bin/systemctl restart job-automation.service

deploy ALL=(root) NOPASSWD: /bin/systemctl start job-automation.service

deploy ALL=(root) NOPASSWD: /bin/systemctl show job-automation.service -p Result --value

deploy ALL=(root) NOPASSWD: /bin/systemctl status job-automation.service --no-pager

deploy ALL=(root) NOPASSWD: /bin/systemctl is-active --quiet job-automation.timer

deploy ALL=(root) NOPASSWD: /bin/systemctl is-active job-automation.timer

deploy ALL=(root) NOPASSWD: /bin/journalctl -u job-automation.service -n 100 --no-pager
```

Validate and apply:

```bash
sudo visudo -cf /etc/sudoers.d/job-automation-deploy
```

### 5) SSH key installation for GitHub Actions

- Generate a dedicated key pair for deployment.
- Put private key into GitHub secret `DEPLOY_SSH_KEY`.
- Add public key to `~deploy/.ssh/authorized_keys`.

Lock down permissions:

```bash
sudo -u deploy mkdir -p /home/deploy/.ssh
sudo -u deploy chmod 700 /home/deploy/.ssh
sudo -u deploy chmod 600 /home/deploy/.ssh/authorized_keys
```

## First deployment procedure

1. Commit and push deployment files to `main`.
2. Confirm GitHub secrets are configured.
3. In GitHub Actions, open the deploy run.
4. Confirm log lines:
   - `Deployment started`
   - `Commit SHA: ...`
   - `Release ID: ...`
   - `Dependencies passed`
   - `Tests passed`
   - `Release activated`
   - `Systemd execution result: success`
   - `Deployment successful`

## Rollback

Automatic rollback:
- `deploy.sh` auto-rolls back if post-switch service execution fails.

Manual rollback to previous release:

```bash
/opt/apps/job-automation/rollback.sh
```

Manual rollback to specific release:

```bash
/opt/apps/job-automation/rollback.sh 20260810-123456
```

Rollback does not modify:
- `/opt/apps/job-automation/shared/database`
- `/opt/apps/job-automation/shared/oauth`
- `/opt/apps/job-automation/shared/resumes`
- `/opt/apps/job-automation/shared/cache`
- `/opt/apps/job-automation/shared/venv`

## Post-deploy checks on VPS

```bash
readlink -f /opt/apps/job-automation/current
test -f /opt/apps/job-automation/current/app/main.py
/opt/apps/job-automation/shared/venv/bin/python --version
/opt/apps/job-automation/shared/venv/bin/pip check
systemctl is-active job-automation.timer
systemctl start job-automation.service
systemctl show job-automation.service -p Result --value
journalctl -u job-automation.service -n 100 --no-pager
```

Expected service behavior:
- For one-shot service, `active` is transient.
- `inactive (dead)` is acceptable if `Result=success`.

## Data preservation guarantees

Deployments never overwrite these files:

- `/opt/apps/job-automation/shared/oauth/token.json`
- `/opt/apps/job-automation/shared/oauth/gmail_oauth_client.json`
- `/opt/apps/job-automation/shared/database/jobs.db`
- `/opt/apps/job-automation/shared/resumes/*`
- `/opt/apps/job-automation/shared/cache/*`
- `/opt/apps/job-automation/shared/venv/*`

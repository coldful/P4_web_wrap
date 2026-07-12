# P4 Web Wrap

`P4_web_wrap-main` combines three parts:

- `P4_web` - FastAPI backend
- `P4_web_client` - simple browser client
- `P4_legacy_runner` - adapter for running legacy operations from `P4_app`

This document explains how to set up and run the wrapper from scratch on a new machine.

## Prerequisites

- Linux/macOS shell with `bash`
- `python3` version 3.12 or newer
- `python3-venv`
- `docker`

The legacy `P4_app` project must also exist next to this directory, because
`run_p4_stack.sh` looks for it here by default:

```text
../P4_app/interface.py
```

Example directory layout:

```text
wp4/
├── P4_app/
└── P4_web_wrap-main/
```

## Prepare The Stack For `run_p4_stack.sh`

From the `P4_web_wrap-main` root:

```bash
chmod +x ./prepare_p4_stack.sh ./run_p4_stack.sh
./prepare_p4_stack.sh
```

`prepare_p4_stack.sh`:

- creates `P4_web/venv`
- installs Python dependencies from `requirements.txt`
- creates `P4_web/.env` from the template if it does not exist yet
- initializes the SQLite database through `p4web init-db`
- verifies that `P4_app` is available next to the wrapper and that Docker works

After this step, the wrapper is ready to launch with `run_p4_stack.sh`.

## Quick Start For The Full Stack

From the `P4_web_wrap-main` root:

```bash
./prepare_p4_stack.sh
./run_p4_stack.sh
```

After startup, these endpoints should be available:

- frontend: `http://127.0.0.1:5173`
- backend API: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`
- health check: `http://127.0.0.1:8000/api/health`

To stop everything, press `Ctrl+C` in the terminal where `run_p4_stack.sh` is running.

## What This Launcher Does

`run_p4_stack.sh`:

- finds `uvicorn` in `P4_web/venv`, `P4_web/.venv`, or `PATH`
- builds the Docker image for `P4_legacy_runner`
- starts the backend on `127.0.0.1:8000`
- starts the frontend on `127.0.0.1:5173`

## Backend + Frontend Only, Without Legacy

This mode is useful if you only want to open the web UI and API without running
legacy commands through Docker.

```bash
python3 -m venv P4_web/venv
P4_web/venv/bin/pip install -r requirements.txt
cp P4_web/.env.example P4_web/.env
cd P4_web
./venv/bin/p4web init-db
./venv/bin/uvicorn p4_web.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd P4_web_client
python3 -m http.server 5173 --bind 127.0.0.1
```

In this mode, the UI and API will work, but operations that depend on the
legacy runner will not be launched automatically through `run_p4_stack.sh`.

## Files And Configuration

- Shared Python dependencies for the wrapper are listed in [requirements.txt](requirements.txt).
- Base backend configuration is in [P4_web/.env.example](P4_web/.env.example).
- By default, the backend uses SQLite:
  `sqlite+aiosqlite:///./var/p4_web.db`
- Local backend data is stored under `P4_web/var/`.


## Production deploy

Configure once:

```bash
cp deploy/config.env.example deploy/config.env
# edit P4_DEPLOY_HOST and remote paths
```

A full deploy syncs frontend (including `/reduced/`), backend source,
`pyproject.toml`, legacy runner, rebuilds the Docker image, restarts services,
and runs a health check.

### A. Direct deploy (recommended)

```bash
./deploy/deploy.sh
```

### B. SFTP + staging

One-time server setup:

```bash
sudo ./deploy/setup_server.sh
```

Upload via SFTP (FileZilla / WinSCP) as user `p4deploy` to `/updates/`:

```text
updates/P4_web_wrap/P4_web_client/
updates/P4_web_wrap/P4_web/src/
updates/P4_web_wrap/P4_web/pyproject.toml
updates/P4_web_wrap/requirements.txt
updates/P4_web_wrap/P4_legacy_runner/
updates/P4_app/                     # optional
```

Then on the server:

```bash
/srv/p4/bin/apply-update all
```

Or upload + apply from your workstation:

```bash
./deploy/push_update.sh all
```

### Partial deploy

```bash
./deploy/deploy.sh frontend
./deploy/deploy.sh backend
./deploy/deploy.sh legacy
./deploy/deploy.sh p4-app
./deploy/deploy.sh scripts
```

Server `.env` is never overwritten. After the first install, make sure
`P4_web/.env` on the server has production values for legacy runner and CORS.

For nginx, use [deploy/nginx-p4.conf.example](deploy/nginx-p4.conf.example).
Project folder import requires `client_max_body_size` above the default 1 MB.



## Common Problems

### Project folder import fails on the server (`NetworkError`)

Browser import sends the whole selected folder to `POST /api/sync/import-upload`.
On production this usually fails for one of two reasons:

1. **nginx upload limit** — default `client_max_body_size` is 1 MB. A project with
   many files exceeds that and the browser shows `NetworkError`.

   Fix on the server:

   ```bash
   ./deploy/deploy.sh nginx
   ```

   Or manually:

   ```bash
   sudo /srv/p4/app/P4_web_wrap/deploy/apply_nginx_upload_limit.sh
   ```

   Small projects may upload under the default 1 MB limit; larger folders (many
   files or images) need this change. Check folder size locally with:

   ```bash
   du -sh /path/to/your/project
   ```

2. **Wrong API URL in the browser** — the reduced UI uses the same API base as the
   main client. On a server it must be `http://YOUR_SERVER/api` (same origin), not
   `http://localhost:8000/api`. New client builds auto-detect this, but clear stale
   localStorage if needed:

   ```javascript
   localStorage.removeItem('p4web.client.apiBase');
   location.reload();
   ```

   In the full client, use the connection field at the top and set the API base to
   `http://YOUR_SERVER/api` or `https://YOUR_DOMAIN/api`.

If the API is accessed directly on port `8000` instead of through nginx, add the
frontend origin to `P4_WEB_CORS_ORIGINS` in `/srv/p4/app/P4_web_wrap/P4_web/.env`
and restart `p4-web`.

### `Missing required path: ../P4_app/interface.py`

The launcher could not find the `P4_app` legacy directory next to the wrapper
project. Check the directory layout or set the override explicitly:

```bash
P4_STACK_LEGACY_APP_DIR=/abs/path/to/P4_app ./run_p4_stack.sh
```

### `Missing uvicorn`

The virtual environment was not created, or the Python dependencies were not installed.
Run `./prepare_p4_stack.sh`.

### Port `8000` or `5173` is already in use

Stop the existing process or choose different ports:

```bash
P4_STACK_BACKEND_PORT=8001 P4_STACK_FRONTEND_PORT=5174 ./run_p4_stack.sh
```

### Docker does not start

Make sure the Docker daemon is running and that the current user is allowed to use it.

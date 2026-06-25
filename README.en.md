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

## Common Problems

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

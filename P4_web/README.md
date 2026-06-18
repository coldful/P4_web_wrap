# P4 Web

P4 Web is the new cloud-ready backend for P4 publishing workflows. It is designed as
a clean platform around the existing P4 capabilities, not as a direct port of the
wxPython desktop UI.

The current repository layout keeps the legacy runtime isolated:

- `../../P4_app` remains read-only from this project.
- `../../P4_docker_linux` remains read-only from this project.
- `../P4_web_client` and `../P4_legacy_runner` live beside this backend inside
  the `P4_web_wrap` wrapper workspace.
- `P4_web` owns the new API, domain model, storage abstraction, job orchestration,
  sync skeleton, and future web UI integration.

## Local Development

```bash
cd P4_web_wrap/P4_web
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev,aws]"
cp .env.example .env
p4web init-db
uvicorn p4_web.main:app --reload
```

Open:

- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

## Architecture Direction

The service is built around explicit ports:

- Storage: local filesystem now, S3-compatible backend later.
- Runner: dry-run runner now, legacy P4 adapter next, native Python 3 runner later.
- Queue: in-process background task now, Redis/SQS/Celery/Temporal adapter later.
- Auth: single full-access user mode now, role model reserved in the schema.

Core concepts:

- Project
- ProjectVersion
- FileObject
- Job
- JobLog
- Artifact
- Approval
- ResourcePackage

See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the detailed
implementation plan.

## Manual Sync

```bash
p4web sync scan ../000_Marine_A
p4web sync import-local ../000_Marine_A --project-name "000 Marine A" --label "initial import"
```

There is also a shorter alias:

```bash
p4web import-local ../000_Marine_A --project-name "000 Marine A" --label "initial import"
```

See [docs/LOCAL_SYNC.md](docs/LOCAL_SYNC.md).

The same import flow is exposed through the web client via **Import local project**.
Use a path that is visible to the backend process.
Jobs run against the imported project version snapshot, not against the mutable
local source folder.

## Legacy PDF Runner

The default runner is still a dry run. To execute the legacy `generate_pdf` flow,
enable the legacy runner and point it at either a Python 2 runtime or a container
wrapper:

```bash
P4_WEB_ENABLE_LEGACY_RUNNER=true
P4_WEB_LEGACY_P4_APP_PATH=../../P4_app
P4_WEB_LEGACY_PYTHON_EXECUTABLE=python2.7
```

For container/script execution, set `P4_WEB_LEGACY_RUNNER_COMMAND`. Available
placeholders are `{python}`, `{interface}`, `{project_path}`, `{operation}`,
`{language}`, and `{app_path}`. The runner also exports
`P4_WEB_JOB_PARAMETERS` as JSON and `P4_WEB_JOB_KIND` as environment variables,
so one generic wrapper can serve multiple operations without one command template
per feature. Generated PDFs matching `P4_WEB_LEGACY_PDF_ARTIFACT_GLOBS` are
stored as job artifacts.

The dedicated CLI/container adapter lives in `../P4_legacy_runner`. For a local
generic wrapper:

```env
P4_WEB_LEGACY_RUNNER_COMMAND=../P4_legacy_runner/bin/p4-legacy-runner run-web-job --operation {operation} --project-path {project_path} --language {language}
```

For Docker:

```env
P4_WEB_LEGACY_RUNNER_COMMAND=docker run --rm -e P4_WEB_JOB_PARAMETERS -e P4_WEB_JOB_KIND -v /home/kirill/Projects/p4/P4_app:/opt/P4_app:ro -v {project_path}:/work/project p4-legacy-runner run-web-job --operation {operation} --project-path /work/project --language {language}
```

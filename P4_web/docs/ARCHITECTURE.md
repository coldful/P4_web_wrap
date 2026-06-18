# Architecture Notes

## Module Boundaries

`api`
: FastAPI routers and request/response schemas. Routers call services, not storage
or runners directly unless they are dependency-injected ports.

`domain`
: Stable enums and future pure domain rules. This layer should not import FastAPI,
SQLAlchemy, or AWS SDKs.

`persistence`
: SQLAlchemy models and session setup. This layer stores metadata, workflow state,
and audit-ready records.

`services`
: Application use cases: create project, create version, import local folder,
start job, approve version. Services coordinate persistence, storage, and runners.

`storage`
: Storage port plus adapters. Local storage is implemented now; S3-compatible
storage should implement the same port.

`runners`
: Processing port plus adapters. The dry-run runner is safe for early development.
The legacy runner shells out to the old P4 CLI in a separate runtime. Native
Python 3 runners can be added later without changing the API.

`sync`
: Local manifest and future sync conflict logic. The manual CLI uses this today;
a background agent should reuse it later.

`workers`
: Queue/worker entrypoints. The first API uses FastAPI background tasks, but
workers are already separated so a Redis/SQS/Temporal adapter can replace it.

## Replacement Points

| Concern | Current | Later |
| --- | --- | --- |
| Storage | Local filesystem | S3 / MinIO |
| Queue | FastAPI background task | Redis/Celery, SQS, or Temporal |
| Runner | Dry-run / shell adapter | Native Python 3 runner |
| Auth | Single full-access actor | Roles, OIDC, tenant isolation |
| DB | SQLite local / PostgreSQL compose | RDS PostgreSQL |

## Version Rule

Jobs must run against a `ProjectVersion`, never against a mutable local folder.
Local sync creates a new draft version. Approval applies to a full version.


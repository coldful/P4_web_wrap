# P4 Web Implementation Plan

This plan assumes a corporate service first, with a clean path to SaaS later.
The first release keeps one full-access role, manual sync, whole-version approval,
offline local work, and long-lived but managed retention.

## Principles

1. Keep `P4_app` and `P4_docker_linux` untouched.
2. Build a clean Python 3 core with explicit ports and adapters.
3. Treat every generation as an immutable operation over a specific project version.
4. Keep AWS useful but replaceable: Postgres, object storage, queue, and workers are
   behind interfaces.
5. Preserve current P4 feature coverage through adapters before rewriting internals.

## Target Components

### API Service

- FastAPI application.
- REST-first API with polling for logs and status.
- SSE can be added later without changing job semantics.
- Single full-access access mode in v1.
- Role and tenant tables reserved for future SaaS.

### Domain Core

- `Project`: logical document workspace.
- `ProjectVersion`: immutable snapshot of input files and configuration.
- `FileObject`: file in a version, stored by content hash and logical path.
- `Job`: long-running operation over a version.
- `Artifact`: produced PDF, HTML, XML, log bundle, or generated package.
- `Approval`: review decision for a whole project version.
- `ResourcePackage`: stylesheet, image set, template, global config bundle.

### Storage

- Local filesystem backend for development.
- S3-compatible backend planned.
- Storage keys are application-owned, not user-controlled paths.
- S3 versioning and lifecycle map to app-level retention policy.

### Worker Runtime

- Workers receive a job id.
- Worker checks out the exact project version into an isolated workspace.
- Runner executes the requested operation.
- Artifacts are uploaded back to storage.
- Logs are persisted continuously enough for polling.

### Sync

- Manual sync command first.
- Later: background local sync agent.
- Offline work is supported by local manifests.
- Conflicts are detected by base version plus content hashes.

## Delivery Phases

### Phase 0: Skeleton

- Project layout.
- Settings.
- Database models.
- Local storage adapter.
- FastAPI routes for health, projects, versions, jobs, approvals, artifacts.
- Dry-run runner and job executor.
- Manual manifest scanner.

### Phase 1: Legacy Compatibility

- Legacy runner adapter for current CLI operations:
  - PDF
  - HTML
  - Cut source
  - Translation import/export
  - Pack/unpack modules
- Add specialized adapters for current GUI-only helpers:
  - XSL-FO
  - Generate Lists
  - Check Index
- Containerize the legacy runtime separately.

### Phase 2: Local Sync

- CLI command: create project from local folder.
- CLI command: upload local changes as draft version.
- CLI command: download approved/published version.
- Conflict report with changed/added/deleted files.

### Phase 3: Review Workflow

- Submit version for review.
- Approve/reject whole version.
- Publish approved artifacts.
- Immutable audit trail.

### Phase 4: Scale

- External queue adapter.
- Worker autoscaling.
- Per-job resource limits.
- Retry policy.
- Cancellation.
- Backpressure and queue metrics.

### Phase 5: SaaS Readiness

- Organizations and roles.
- SSO/OIDC.
- Tenant-level storage prefixes.
- Billing/quota hooks.
- Regional deployment profile.

## AWS Baseline

- API and workers: ECS/Fargate.
- Database: RDS PostgreSQL.
- Files and artifacts: S3.
- Queue/cache/locks: Redis-compatible service or SQS adapter.
- Images: ECR.
- Logs/metrics: CloudWatch first, OpenTelemetry later.

## First Implementation Cut

The first code cut implements Phase 0 with clean interfaces and a dry-run runner.
It should be possible to create a project, create/import a version, start a job,
poll job logs, receive a placeholder artifact, submit a version for approval, and
approve/reject it.


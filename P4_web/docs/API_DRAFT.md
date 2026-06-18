# API Draft

All endpoints are versionless during early development and live under `/api`.

## Health

- `GET /api/health`

## Projects

- `POST /api/projects`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `GET /api/projects/{project_id}/versions`

## Versions

- `POST /api/projects/{project_id}/versions`
- `GET /api/versions/{version_id}`
- `GET /api/versions/{version_id}/files`

## Jobs

- `POST /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/logs`
- `POST /api/jobs/{job_id}/cancel`

## Artifacts

- `GET /api/projects/{project_id}/artifacts`
- `GET /api/versions/{version_id}/artifacts`

## Approvals

- `POST /api/versions/{version_id}/submit`
- `POST /api/versions/{version_id}/approve`
- `POST /api/versions/{version_id}/reject`

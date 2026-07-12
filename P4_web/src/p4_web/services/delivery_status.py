from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.core.config import Settings
from p4_web.domain.enums import JobKind
from p4_web.persistence.models import ProjectVersion
from p4_web.services.sync_import import import_workspace_version
from p4_web.services.workspaces import materialize_version_workspace
from p4_web.storage import StorageBackend

from p4_web.services.delivery_state import build_delivery_state, parse_delivery_state_from_runner_logs

__all__ = [
    "DeliveryStatusError",
    "LegacyRunnerUnavailableError",
    "advance_delivery_status",
    "build_delivery_state",
]


class DeliveryStatusError(Exception):
    pass


class LegacyRunnerUnavailableError(DeliveryStatusError):
    pass


async def advance_delivery_status(
    session: AsyncSession,
    storage: StorageBackend,
    settings: Settings,
    version_id: str,
    actor_id: str | None = None,
) -> ProjectVersion:
    from p4_web.runners import LegacyP4Runner, RunnerContext, RunnerExecutionError
    from p4_web.services.jobs import build_runner
    from p4_web.services.projects import enrich_version_for_legacy_delivery, get_version

    if not settings.enable_legacy_runner:
        raise LegacyRunnerUnavailableError("Legacy runner is not enabled")

    version = await get_version(session, version_id)
    runner = build_runner(settings)
    if not isinstance(runner, LegacyP4Runner):
        raise LegacyRunnerUnavailableError("Legacy runner is not enabled")

    workspace_dir = settings.workspace_root / f"delivery-{uuid.uuid4().hex}"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    try:
        project_path = await materialize_version_workspace(session, storage, version, workspace_dir)
        context = RunnerContext(
            job_id=f"delivery-{uuid.uuid4().hex}",
            project_id=version.project_id,
            version_id=version.id,
            kind=JobKind.ADVANCE_DELIVERY_STATUS,
            parameters={"project_path": str(project_path)},
            workspace_dir=workspace_dir,
            legacy_p4_app_path=settings.legacy_p4_app_path,
        )
        try:
            result = await runner.run(context)
        except RunnerExecutionError as exc:
            raise DeliveryStatusError(str(exc)) from exc

        runner_metadata = parse_delivery_state_from_runner_logs(result.logs)

        new_version = await import_workspace_version(
            session=session,
            storage=storage,
            root=project_path,
            project_id=version.project_id,
            label="delivery status advance",
            base_version_id=version.id,
            actor_id=actor_id,
            root_name=_manifest_root_name(version, project_path),
        )
        if runner_metadata:
            manifest = dict(new_version.manifest or {})
            metadata = dict(manifest.get("project_sheet_metadata") or {})
            metadata.update(runner_metadata)
            manifest["project_sheet_metadata"] = metadata
            new_version.manifest = manifest
            await session.flush()
        await session.commit()
        await session.refresh(new_version)
        return enrich_version_for_legacy_delivery(new_version, storage)
    finally:
        shutil.rmtree(workspace_dir, ignore_errors=True)


def _manifest_root_name(version: ProjectVersion, project_path: Path) -> str:
    root_name = version.manifest.get("root_name")
    if isinstance(root_name, str) and root_name.strip():
        return root_name
    return project_path.name

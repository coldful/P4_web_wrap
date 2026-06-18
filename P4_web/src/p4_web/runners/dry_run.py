import json

from p4_web.domain.enums import ArtifactKind
from p4_web.runners.ports import ArtifactSpec, RunnerContext, RunnerResult


class DryRunRunner:
    """Safe runner used until the legacy processing adapter is enabled."""

    async def run(self, context: RunnerContext) -> RunnerResult:
        payload = {
            "job_id": context.job_id,
            "project_id": context.project_id,
            "version_id": context.version_id,
            "kind": context.kind,
            "parameters": context.parameters,
        }
        report = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        return RunnerResult(
            logs=[
                "Dry-run runner selected.",
                f"Requested operation: {context.kind}",
                "No legacy P4 files were modified.",
            ],
            artifacts=[
                ArtifactSpec(
                    kind=ArtifactKind.REPORT,
                    path=f"dry-run/{context.job_id}.json",
                    content_type="application/json",
                    data=report,
                )
            ],
        )


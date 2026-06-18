import json
from pathlib import Path

from p4_web.domain.enums import JobKind
from p4_web.runners.legacy import LegacyP4Runner
from p4_web.runners.ports import RunnerContext


def test_legacy_runner_exports_job_parameters_in_environment() -> None:
    runner = LegacyP4Runner(command_template="echo ok")
    context = RunnerContext(
        job_id="job-1",
        project_id="project-1",
        version_id="version-1",
        kind=JobKind.PACK_MODULES,
        parameters={"language": "de", "schema": "proced.xsd"},
        workspace_dir=Path("/tmp/workspace"),
        legacy_p4_app_path=Path("/tmp/P4_app"),
    )

    env = runner._build_environment(context)

    assert env["P4_WEB_JOB_KIND"] == "pack_modules"
    assert json.loads(env["P4_WEB_JOB_PARAMETERS"]) == {
        "language": "de",
        "schema": "proced.xsd",
    }

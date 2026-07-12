import json
from pathlib import Path

from p4_web.domain.enums import ArtifactKind, JobKind
from p4_web.runners.legacy import LegacyP4Runner
from p4_web.runners.ports import RunnerContext, RunnerExecutionError


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


def test_legacy_runner_reports_missing_executable() -> None:
    runner = LegacyP4Runner(python_executable="python2.7-missing")
    context = RunnerContext(
        job_id="job-1",
        project_id="project-1",
        version_id="version-1",
        kind=JobKind.XSL_FO,
        parameters={"project_path": "/tmp/workspace/project"},
        workspace_dir=Path("/tmp/workspace"),
        legacy_p4_app_path=Path("/tmp/P4_app"),
    )

    try:
        runner._validate_command(["python2.7-missing", "/tmp/helper.py", "xsl-fo"])
    except RunnerExecutionError as exc:
        assert "python2.7-missing" in str(exc)
        assert exc.logs[0].startswith("Command:")
    else:
        raise AssertionError("Expected RunnerExecutionError")


def test_legacy_runner_builds_helper_command_for_generate_lists() -> None:
    runner = LegacyP4Runner(python_executable="python2.7")
    project_path = Path("/tmp/workspace/project")
    context = RunnerContext(
        job_id="job-1",
        project_id="project-1",
        version_id="version-1",
        kind=JobKind.GENERATE_LISTS,
        parameters={"language": "de", "xml_file": "001/source.xml"},
        workspace_dir=Path("/tmp/workspace"),
        legacy_p4_app_path=Path("/tmp/P4_app"),
    )

    command = runner._build_command(
        context,
        Path("/tmp/P4_app"),
        Path("/tmp/P4_app/interface.py"),
        project_path,
        "de",
    )

    assert command[:3] == ["python2.7", str(runner._legacy_helper_path()), "generate-lists"]
    assert "--p4-app-path" in command
    assert "--project-path" in command
    assert str(project_path / "001/source.xml") in command


def test_legacy_runner_builds_helper_command_for_texml_pdf() -> None:
    runner = LegacyP4Runner(python_executable="python2.7")
    project_path = Path("/tmp/workspace/project")
    context = RunnerContext(
        job_id="job-1",
        project_id="project-1",
        version_id="version-1",
        kind=JobKind.TEXML_PDF,
        parameters={"language": "de"},
        workspace_dir=Path("/tmp/workspace"),
        legacy_p4_app_path=Path("/tmp/P4_app"),
    )

    command = runner._build_command(
        context,
        Path("/tmp/P4_app"),
        Path("/tmp/P4_app/interface.py"),
        project_path,
        "de",
    )

    assert command[:3] == ["python2.7", str(runner._legacy_helper_path()), "texml-pdf"]
    assert "--project-path" in command
    assert str(project_path) in command


def test_legacy_runner_builds_interface_command_for_opmanual_files() -> None:
    runner = LegacyP4Runner(python_executable="python2.7")
    project_path = Path("/tmp/workspace/project")
    context = RunnerContext(
        job_id="job-1",
        project_id="project-1",
        version_id="version-1",
        kind=JobKind.CONVERT_OPMANUAL_TO_BIT_XML,
        parameters={
            "language": "de",
            "opmanual_files": ["docs/s_01.01_intro.xml", "docs/s_02.00_main.xml"],
        },
        workspace_dir=Path("/tmp/workspace"),
        legacy_p4_app_path=Path("/tmp/P4_app"),
    )

    command = runner._build_command(
        context,
        Path("/tmp/P4_app"),
        Path("/tmp/P4_app/interface.py"),
        project_path,
        "de",
    )

    assert "--opmanual-to-bitplant" in command
    assert command.count("--opmanual-file") == 2
    assert str(project_path / "docs/s_01.01_intro.xml") in command
    assert str(project_path / "docs/s_02.00_main.xml") in command


def test_legacy_runner_collects_result_artifact_from_helper_output(tmp_path: Path) -> None:
    runner = LegacyP4Runner()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    pdf_file = workspace / "result.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n")
    context = RunnerContext(
        job_id="job-1",
        project_id="project-1",
        version_id="version-1",
        kind=JobKind.XSL_FO,
        parameters={},
        workspace_dir=workspace,
        legacy_p4_app_path=tmp_path / "P4_app",
    )

    artifacts = runner._artifacts_from_result_logs(
        context,
        "RESULT {0}\n".format(pdf_file),
        workspace,
        workspace,
    )

    assert len(artifacts) == 1
    assert artifacts[0].kind == ArtifactKind.PDF
    assert artifacts[0].path == "result.pdf"


def test_legacy_runner_remaps_container_result_path_to_host_workspace(tmp_path: Path) -> None:
    runner = LegacyP4Runner()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    pdf_file = workspace / "example7_xslfo.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n")
    context = RunnerContext(
        job_id="job-1",
        project_id="project-1",
        version_id="version-1",
        kind=JobKind.XSL_FO,
        parameters={},
        workspace_dir=workspace,
        legacy_p4_app_path=tmp_path / "P4_app",
    )

    artifacts = runner._artifacts_from_result_logs(
        context,
        "RESULT /work/project/example7_xslfo.pdf\n",
        workspace,
        Path("/work/project"),
    )

    assert len(artifacts) == 1
    assert artifacts[0].kind == ArtifactKind.PDF
    assert artifacts[0].path == "example7_xslfo.pdf"
    assert artifacts[0].local_path == pdf_file


def test_legacy_runner_builds_helper_command_with_output_dir_for_xsl_fo() -> None:
    runner = LegacyP4Runner(python_executable="python2.7")
    project_path = Path("/tmp/workspace/project")
    context = RunnerContext(
        job_id="job-1",
        project_id="project-1",
        version_id="version-1",
        kind=JobKind.XSL_FO,
        parameters={"language": "de", "output_dir": "/tmp/workspace/project"},
        workspace_dir=Path("/tmp/workspace"),
        legacy_p4_app_path=Path("/tmp/P4_app"),
    )

    command = runner._build_command(
        context,
        Path("/tmp/P4_app"),
        Path("/tmp/P4_app/interface.py"),
        project_path,
        "de",
    )

    assert "--output-dir" in command
    assert "/tmp/workspace/project" in command


def test_legacy_runner_collects_texml_workspace_artifacts(tmp_path: Path) -> None:
    runner = LegacyP4Runner()
    project_path = tmp_path / "project"
    texml_tmp = project_path / "_texml_pdf" / "project_TeX_de" / "tmp"
    texml_out = project_path / "_texml_pdf" / "project_TeX_de" / "out"
    texml_tmp.mkdir(parents=True)
    texml_out.mkdir()
    (texml_out / "manual.pdf").write_bytes(b"%PDF-1.4\n")
    (texml_tmp / "manual.tex").write_text("\\section{Demo}\n", encoding="utf-8")
    (texml_tmp / "manual.texml").write_text("<TeXML />\n", encoding="utf-8")

    artifacts = runner._collect_artifacts(JobKind.TEXML_PDF, project_path)

    assert [artifact.path for artifact in artifacts] == [
        "_texml_pdf/project_TeX_de/out/manual.pdf",
        "_texml_pdf/project_TeX_de/tmp/manual.tex",
        "_texml_pdf/project_TeX_de/tmp/manual.texml",
    ]
    assert [artifact.kind for artifact in artifacts] == [
        ArtifactKind.PDF,
        ArtifactKind.REPORT,
        ArtifactKind.REPORT,
    ]

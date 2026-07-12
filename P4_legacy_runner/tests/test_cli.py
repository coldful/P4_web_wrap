from pathlib import Path

from p4_legacy_runner import cli


def build(argv, p4_app="/legacy/P4_app"):
    args = cli.parse_args(argv)
    config = cli.RunnerConfig(p4_app_path=p4_app, python_executable="python2.7")
    return cli.build_command(args, config)


def test_generate_pdf_builds_interface_command() -> None:
    command = build(["generate-pdf", "--project-path", "/work/project", "--language", "de"])

    assert command == [
        "python2.7",
        "/legacy/P4_app/interface.py",
        "--project-path",
        "/work/project",
        "--language",
        "de",
        "--topdf",
    ]


def test_generate_html_passes_noimages_and_include() -> None:
    command = build(
        [
            "generate-html",
            "--project-path",
            "/work/project",
            "--language",
            "en",
            "--noimages",
            "--include",
            "no",
        ]
    )

    assert command[-4:] == ["--tohtml", "--noimages", "--include", "no"]


def test_pack_modules_passes_schema() -> None:
    command = build(
        [
            "pack-modules",
            "--project-path",
            "/work/project",
            "--schema",
            "proced.xsd",
        ]
    )

    assert command[-3:] == ["--pack", "--schema", "proced.xsd"]


def test_run_web_job_maps_pack_modules_to_cli_command() -> None:
    args = cli.parse_args(
        [
            "run-web-job",
            "--operation",
            "pack_modules",
            "--project-path",
            "/work/project",
            "--parameters-json",
            '{"schema":"proced.xsd"}',
        ]
    )

    assert cli.build_web_job_argv(args) == [
        "pack-modules",
        "--project-path",
        "/work/project",
        "--language",
        "de",
        "--schema",
        "proced.xsd",
    ]


def test_run_web_job_maps_generate_pdf_to_cli_command() -> None:
    args = cli.parse_args(
        [
            "run-web-job",
            "--operation",
            "generate_pdf",
            "--project-path",
            "/work/project",
            "--language",
            "en",
        ]
    )

    assert cli.build_web_job_argv(args) == [
        "generate-pdf",
        "--project-path",
        "/work/project",
        "--language",
        "en",
    ]


def test_run_web_job_maps_texml_pdf_to_cli_command() -> None:
    args = cli.parse_args(
        [
            "run-web-job",
            "--operation",
            "texml_pdf",
            "--project-path",
            "/work/project",
            "--language",
            "de",
        ]
    )

    assert cli.build_web_job_argv(args) == [
        "texml-pdf",
        "--project-path",
        "/work/project",
        "--language",
        "de",
    ]


def test_texml_pdf_builds_helper_command() -> None:
    command = build(["texml-pdf", "--project-path", "/work/project", "--language", "de"])

    assert command[:3] == ["python2.7", cli.helper_path(), "texml-pdf"]
    assert "--p4-app-path" in command
    assert "--project-path" in command


def test_run_web_job_remaps_project_relative_helper_paths_to_container_workspace() -> None:
    args = cli.parse_args(
        [
            "run-web-job",
            "--operation",
            "xsl_fo",
            "--project-path",
            "/work/project",
            "--parameters-json",
            '{"project_path":"var/workspaces/job-1/project","xml_file":"docs/source.xml","output_dir":"var/workspaces/job-1/project"}',
        ]
    )

    assert cli.build_web_job_argv(args) == [
        "xsl-fo",
        "--project-path",
        "/work/project",
        "--language",
        "de",
        "--xml-file",
        "/work/project/docs/source.xml",
        "--output-dir",
        "/work/project",
    ]


def test_generate_lists_builds_helper_command() -> None:
    command = build(
        ["generate-lists", "--project-path", "/work/project", "--xml-file", "/work/project/a.xml"]
    )

    assert command[:3] == ["python2.7", cli.helper_path(), "generate-lists"]
    assert "--p4-app-path" in command
    assert "--project-path" in command
    assert "--xml-file" in command


def test_run_web_job_maps_advance_delivery_status() -> None:
    args = cli.parse_args(
        [
            "run-web-job",
            "--operation",
            "advance_delivery_status",
            "--project-path",
            "/work/project",
        ]
    )

    assert cli.build_web_job_argv(args) == [
        "advance-delivery-status",
        "--project-path",
        "/work/project",
        "--language",
        "de",
    ]


def test_advance_delivery_status_builds_helper_command() -> None:
    command = build(["advance-delivery-status", "--project-path", "/work/project"])

    assert command[:3] == ["python2.7", cli.helper_path(), "advance-delivery-status"]
    assert "--p4-app-path" in command
    assert "--project-path" in command


def test_run_web_job_maps_opmanual_files_to_cli_command() -> None:
    args = cli.parse_args(
        [
            "run-web-job",
            "--operation",
            "convert_opmanual_to_bit_xml",
            "--project-path",
            "/work/project",
            "--parameters-json",
            '{"opmanual_files":["docs/s_01.01_intro.xml","docs/s_02.00_main.xml"]}',
        ]
    )

    assert cli.build_web_job_argv(args) == [
        "opmanual-to-bit-xml",
        "--project-path",
        "/work/project",
        "--language",
        "de",
        "/work/project/docs/s_01.01_intro.xml",
        "/work/project/docs/s_02.00_main.xml",
    ]


def test_run_web_job_maps_convert_sap_paths_to_container_workspace() -> None:
    args = cli.parse_args(
        [
            "run-web-job",
            "--operation",
            "convert_sap_to_bit_xml",
            "--project-path",
            "/work/project",
            "--parameters-json",
            '{"etk_file":"imports/source.xml","output_file":"exports/result.xml"}',
        ]
    )

    assert cli.build_web_job_argv(args) == [
        "convert-sap-to-bit-xml",
        "--project-path",
        "/work/project",
        "--language",
        "de",
        "--etk-file",
        "/work/project/imports/source.xml",
        "--output-file",
        "/work/project/exports/result.xml",
    ]


def test_set_var_accepts_assignment() -> None:
    command = build(["set-var", "--project-path", "/work/project", "stage=review"])

    assert command[-2:] == ["--setvar", "stage=review"]


def test_opmanual_command_accepts_project_arguments() -> None:
    command = build(
        [
            "opmanual-to-bit-xml",
            "--project-path",
            "/work/project",
            "--language",
            "de",
            "docs/s_01.01_intro.xml",
        ]
    )

    assert "--project-path" in command
    assert "--language" in command
    assert "--opmanual-file" in command


def test_convert_sap_command_accepts_project_arguments() -> None:
    command = build(
        [
            "convert-sap-to-bit-xml",
            "--project-path",
            "/work/project",
            "--language",
            "de",
            "--etk-file",
            "/work/project/imports/source.xml",
        ]
    )

    assert "--project-path" in command
    assert "--language" in command
    assert "--etk-file" in command


def test_default_p4_app_path_points_to_repo_sibling() -> None:
    assert cli.resolve_p4_app_path().endswith("/p4/P4_app")


def test_no_exec_prints_command_without_python2(tmp_path: Path, capsys) -> None:
    p4_app = tmp_path / "P4_app"
    p4_app.mkdir()
    (p4_app / "interface.py").write_text("# fake legacy entrypoint\n", encoding="utf-8")

    exit_code = cli.main(
        [
            "--no-exec",
            "--p4-app-path",
            str(p4_app),
            "generate-pdf",
            "--project-path",
            "/work/project",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "interface.py" in out
    assert "--topdf" in out

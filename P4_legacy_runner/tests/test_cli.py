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


def test_generate_lists_builds_helper_command() -> None:
    command = build(
        ["generate-lists", "--project-path", "/work/project", "--xml-file", "/work/project/a.xml"]
    )

    assert command[:3] == ["python2.7", cli.helper_path(), "generate-lists"]
    assert "--p4-app-path" in command
    assert "--project-path" in command
    assert "--xml-file" in command


def test_set_var_accepts_assignment() -> None:
    command = build(["set-var", "--project-path", "/work/project", "stage=review"])

    assert command[-2:] == ["--setvar", "stage=review"]


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

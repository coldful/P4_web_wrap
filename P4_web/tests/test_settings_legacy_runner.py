from pathlib import Path

from p4_web.core.config import Settings, build_legacy_runner_docker_command


def test_build_legacy_runner_docker_command_uses_host_network_on_linux(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app_path = tmp_path / "P4_app"
    app_path.mkdir()
    (app_path / "interface.py").write_text("# legacy\n", encoding="utf-8")
    monkeypatch.setattr("p4_web.core.config.shutil.which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    monkeypatch.setattr("p4_web.core.config.sys.platform", "linux")

    command = build_legacy_runner_docker_command(app_path, image="p4-legacy-runner")

    assert command is not None
    assert "--network=host" in command
    assert f"-v {app_path.resolve()}:/opt/P4_app:ro" in command
    assert "{project_path}" in command
    assert "run-web-job" in command


def test_resolved_legacy_runner_command_falls_back_to_docker_without_python2(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app_path = tmp_path / "P4_app"
    app_path.mkdir()
    (app_path / "interface.py").write_text("# legacy\n", encoding="utf-8")
    monkeypatch.setattr("p4_web.core.config.shutil.which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    monkeypatch.setattr("p4_web.core.config.sys.platform", "linux")

    settings = Settings(
        enable_legacy_runner=True,
        legacy_p4_app_path=app_path,
        legacy_runner_command=None,
        legacy_python_executable="python2.7",
    )

    resolved = settings.resolved_legacy_runner_command()

    assert resolved is not None
    assert resolved.startswith("docker run")


def test_resolved_legacy_runner_command_keeps_explicit_override(
    tmp_path: Path,
) -> None:
    app_path = tmp_path / "P4_app"
    app_path.mkdir()
    settings = Settings(
        enable_legacy_runner=True,
        legacy_p4_app_path=app_path,
        legacy_runner_command="echo custom {operation}",
    )

    assert settings.resolved_legacy_runner_command() == "echo custom {operation}"

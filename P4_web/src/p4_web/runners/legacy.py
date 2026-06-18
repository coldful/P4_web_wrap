import asyncio
import json
import os
import shlex
from pathlib import Path

from p4_web.domain.enums import ArtifactKind, JobKind
from p4_web.runners.ports import ArtifactSpec, RunnerContext, RunnerExecutionError, RunnerResult


class LegacyP4Runner:
    """Adapter boundary for the existing P4 CLI/runtime.

    The adapter intentionally does not import modules from P4_app. The legacy runtime
    is expected to run in its own Python 2 compatible environment/container.
    """

    CLI_ARGS: dict[JobKind, list[str]] = {
        JobKind.GENERATE_PDF: ["--topdf"],
        JobKind.GENERATE_HTML: ["--tohtml"],
        JobKind.CUT_SOURCE: ["--cut-source"],
        JobKind.EXPORT_TRANSLATION: ["--export-translation"],
        JobKind.IMPORT_TRANSLATION: ["--import-translation"],
        JobKind.PACK_MODULES: ["--pack"],
        JobKind.UNPACK_MODULES: ["--unpack"],
    }
    ARTIFACT_PATTERNS: dict[JobKind, list[tuple[str, ArtifactKind, str | None]]] = {
        JobKind.PACK_MODULES: [
            ("packed.txt", ArtifactKind.REPORT, "text/plain"),
            ("**/packed.txt", ArtifactKind.REPORT, "text/plain"),
        ],
        JobKind.UNPACK_MODULES: [
            ("unpacked.txt", ArtifactKind.REPORT, "text/plain"),
            ("**/unpacked.txt", ArtifactKind.REPORT, "text/plain"),
        ],
    }

    def __init__(
        self,
        python_executable: str = "python2.7",
        command_template: str | None = None,
        timeout_seconds: int = 3600,
        pdf_artifact_globs: list[str] | None = None,
    ) -> None:
        self.python_executable = python_executable
        self.command_template = command_template
        self.timeout_seconds = timeout_seconds
        self.pdf_artifact_globs = pdf_artifact_globs or ["*.pdf", "**/*.pdf"]

    async def run(self, context: RunnerContext) -> RunnerResult:
        if context.legacy_p4_app_path is None:
            raise RuntimeError("Legacy P4 app path is not configured")
        if context.kind not in self.CLI_ARGS:
            raise NotImplementedError(f"Legacy CLI mapping is missing for {context.kind}")

        app_path = Path(context.legacy_p4_app_path).resolve()
        interface_py = app_path / "interface.py"
        project_path = Path(
            context.parameters.get("project_path") or context.workspace_dir
        ).resolve()
        language = str(context.parameters.get("language") or "de")
        command = self._build_command(context, app_path, interface_py, project_path, language)
        env = self._build_environment(context)

        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(app_path),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_seconds)
        except TimeoutError as exc:
            proc.kill()
            await proc.communicate()
            raise RunnerExecutionError(
                f"Legacy P4 process timed out after {self.timeout_seconds} seconds",
                logs=[f"Command: {shlex.join(command)}"],
            ) from exc
        output = stdout.decode("utf-8", errors="replace")
        logs = [f"Command: {shlex.join(command)}"]
        logs.extend(output.splitlines() or ["Legacy process produced no output."])
        if proc.returncode != 0:
            raise RunnerExecutionError(
                f"Legacy P4 process failed with exit code {proc.returncode}",
                logs=logs,
            )
        return RunnerResult(
            logs=logs,
            artifacts=self._collect_artifacts(context.kind, project_path),
        )

    def _build_command(
        self,
        context: RunnerContext,
        app_path: Path,
        interface_py: Path,
        project_path: Path,
        language: str,
    ) -> list[str]:
        if self.command_template:
            schema = str(context.parameters.get("schema") or "").strip()
            rendered = self.command_template.format(
                python=self.python_executable,
                interface=str(interface_py),
                project_path=str(project_path),
                operation=context.kind.value,
                language=language,
                schema=schema,
                app_path=str(app_path),
            )
            return shlex.split(rendered)

        command = [
            self.python_executable,
            str(interface_py),
            "--project-path",
            str(project_path),
            *self.CLI_ARGS[context.kind],
        ]
        if language:
            command.extend(["--language", language])
        if context.kind in {JobKind.PACK_MODULES, JobKind.UNPACK_MODULES}:
            schema = str(context.parameters.get("schema") or "").strip()
            if schema:
                command.extend(["--schema", schema])
        return command

    def _build_environment(self, context: RunnerContext) -> dict[str, str]:
        env = os.environ.copy()
        env["P4_WEB_JOB_KIND"] = context.kind.value
        env["P4_WEB_JOB_PARAMETERS"] = json.dumps(context.parameters)
        return env

    def _collect_artifacts(self, kind: JobKind, project_path: Path) -> list[ArtifactSpec]:
        seen: set[Path] = set()
        artifacts: list[ArtifactSpec] = []
        patterns = list(self.ARTIFACT_PATTERNS.get(kind, []))
        if kind == JobKind.GENERATE_PDF:
            patterns.extend(
                (pattern, ArtifactKind.PDF, "application/pdf")
                for pattern in self.pdf_artifact_globs
            )

        for pattern, artifact_kind, content_type in patterns:
            for path in sorted(project_path.glob(pattern)):
                if not path.is_file():
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                artifacts.append(
                    ArtifactSpec(
                        kind=artifact_kind,
                        path=path.relative_to(project_path).as_posix(),
                        content_type=content_type,
                        local_path=path,
                    )
                )
        return artifacts

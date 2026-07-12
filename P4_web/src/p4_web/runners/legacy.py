import asyncio
import configparser
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

    INTERFACE_ARGS: dict[JobKind, list[str]] = {
        JobKind.GENERATE_PDF: ["--topdf"],
        JobKind.GENERATE_HTML: ["--tohtml"],
        JobKind.CUT_SOURCE: ["--cut-source"],
        JobKind.EXPORT_TRANSLATION: ["--export-translation"],
        JobKind.IMPORT_TRANSLATION: ["--import-translation"],
        JobKind.PACK_MODULES: ["--pack"],
        JobKind.UNPACK_MODULES: ["--unpack"],
        JobKind.CONVERT_OPMANUAL_TO_BIT_XML: ["--opmanual-to-bitplant"],
    }
    HELPER_COMMANDS: dict[JobKind, str] = {
        JobKind.TEXML_PDF: "texml-pdf",
        JobKind.XSL_FO: "xsl-fo",
        JobKind.GENERATE_LISTS: "generate-lists",
        JobKind.CHECK_INDEX: "check-index",
        JobKind.CONVERT_SAP_TO_BIT_XML: "convert-sap-to-bit-xml",
        JobKind.ADVANCE_DELIVERY_STATUS: "advance-delivery-status",
    }
    ARTIFACT_PATTERNS: dict[JobKind, list[tuple[str, ArtifactKind, str | None]]] = {
        JobKind.GENERATE_HTML: [
            ("**/*.html", ArtifactKind.HTML, "text/html"),
            ("**/*.css", ArtifactKind.OTHER, "text/css"),
            ("**/*.js", ArtifactKind.OTHER, "text/javascript"),
        ],
        JobKind.PACK_MODULES: [
            ("packed.txt", ArtifactKind.REPORT, "text/plain"),
            ("**/packed.txt", ArtifactKind.REPORT, "text/plain"),
        ],
        JobKind.UNPACK_MODULES: [
            ("unpacked.txt", ArtifactKind.REPORT, "text/plain"),
            ("**/unpacked.txt", ArtifactKind.REPORT, "text/plain"),
        ],
        JobKind.TEXML_PDF: [
            ("_texml_pdf/**/*.pdf", ArtifactKind.PDF, "application/pdf"),
            ("_texml_pdf/**/*.tex", ArtifactKind.REPORT, "text/plain"),
            ("_texml_pdf/**/*.texml", ArtifactKind.REPORT, "application/xml"),
            ("_texml_pdf/**/*.log", ArtifactKind.REPORT, "text/plain"),
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
        if context.kind not in self.INTERFACE_ARGS and context.kind not in self.HELPER_COMMANDS:
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
        runtime_project_path = self._runtime_project_path(command, project_path)
        result_artifacts = self._artifacts_from_result_logs(
            context,
            output,
            project_path,
            runtime_project_path,
        )
        return RunnerResult(
            logs=logs,
            artifacts=self._merge_artifacts(
                result_artifacts,
                self._collect_artifacts(context.kind, project_path),
            ),
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

        if context.kind in self.INTERFACE_ARGS:
            command = [
                self.python_executable,
                str(interface_py),
                "--project-path",
                str(project_path),
                *self.INTERFACE_ARGS[context.kind],
            ]
            if language:
                command.extend(["--language", language])
            if context.kind in {JobKind.PACK_MODULES, JobKind.UNPACK_MODULES}:
                schema = str(context.parameters.get("schema") or "").strip()
                if schema:
                    command.extend(["--schema", schema])
            if context.kind == JobKind.CONVERT_OPMANUAL_TO_BIT_XML:
                opmanual_files = self._resolve_many_paths(
                    project_path,
                    context.parameters.get("opmanual_files"),
                )
                if not opmanual_files:
                    raise RuntimeError("convert_opmanual_to_bit_xml requires opmanual_files")
                for path in opmanual_files:
                    command.extend(["--opmanual-file", str(path)])
            return command

        helper_path = self._legacy_helper_path()
        command = [
            self.python_executable,
            str(helper_path),
            self.HELPER_COMMANDS[context.kind],
            "--p4-app-path",
            str(app_path),
            "--project-path",
            str(project_path),
        ]
        if language:
            command.extend(["--language", language])
        xml_file = self._resolve_optional_path(project_path, context.parameters.get("xml_file"))
        if xml_file is not None:
            command.extend(["--xml-file", str(xml_file)])
        output_dir = self._resolve_optional_path(project_path, context.parameters.get("output_dir"))
        if output_dir is not None:
            command.extend(["--output-dir", str(output_dir)])
        if context.kind == JobKind.CONVERT_SAP_TO_BIT_XML:
            etk_file = self._resolve_optional_path(project_path, context.parameters.get("etk_file"))
            if etk_file is None:
                raise RuntimeError("convert_sap_to_bit_xml requires etk_file")
            command.extend(["--etk-file", str(etk_file)])
            output_file = self._resolve_optional_path(
                project_path,
                context.parameters.get("output_file"),
            )
            if output_file is not None:
                command.extend(["--output-file", str(output_file)])
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

    def _artifacts_from_result_logs(
        self,
        context: RunnerContext,
        output: str,
        project_path: Path,
        runtime_project_path: Path,
    ) -> list[ArtifactSpec]:
        if context.kind in {JobKind.GENERATE_LISTS, JobKind.CHECK_INDEX}:
            return []
        artifacts: list[ArtifactSpec] = []
        seen: set[Path] = set()
        for path in self._result_paths_from_output(
            context.kind,
            output,
            context.legacy_p4_app_path,
        ):
            path = self._remap_runtime_result_path(path, runtime_project_path, project_path)
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            artifacts.append(
                ArtifactSpec(
                    kind=self._artifact_kind_for_path(path),
                    path=self._artifact_path(path, project_path),
                    content_type=self._content_type_for_path(path),
                    local_path=path,
                )
            )
        return artifacts

    def _merge_artifacts(
        self,
        *artifact_lists: list[ArtifactSpec],
    ) -> list[ArtifactSpec]:
        merged: list[ArtifactSpec] = []
        seen: set[tuple[str, ArtifactKind]] = set()
        for items in artifact_lists:
            for spec in items:
                key = (spec.path, spec.kind)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(spec)
        return merged

    def _legacy_helper_path(self) -> Path:
        current = Path(__file__).resolve()
        for parent in current.parents:
            candidate = parent / "P4_legacy_runner" / "src" / "p4_legacy_runner" / "legacy_helpers.py"
            if candidate.is_file():
                return candidate
        return current.parents[4] / "P4_legacy_runner" / "src" / "p4_legacy_runner" / "legacy_helpers.py"

    def _runtime_project_path(self, command: list[str], default: Path) -> Path:
        try:
            index = command.index("--project-path")
        except ValueError:
            return default
        if index + 1 >= len(command):
            return default
        return Path(command[index + 1]).resolve()

    def _remap_runtime_result_path(
        self,
        path: Path,
        runtime_project_path: Path,
        host_project_path: Path,
    ) -> Path:
        if path.is_file():
            return path
        try:
            relative = path.resolve().relative_to(runtime_project_path.resolve())
        except ValueError:
            return path
        return (host_project_path / relative).resolve()

    def _resolve_optional_path(self, root: Path, value: object) -> Path | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        path = Path(text)
        if not path.is_absolute():
            path = root / path
        return path.resolve()

    def _resolve_many_paths(self, root: Path, value: object) -> list[Path]:
        if value is None:
            return []
        if isinstance(value, str):
            raw_values = [part.strip() for part in value.replace(",", "\n").splitlines()]
        elif isinstance(value, (list, tuple)):
            raw_values = [str(part).strip() for part in value]
        else:
            raw_values = [str(value).strip()]
        resolved: list[Path] = []
        for item in raw_values:
            path = self._resolve_optional_path(root, item)
            if path is not None:
                resolved.append(path)
        return resolved

    def _result_paths_from_output(
        self,
        kind: JobKind,
        output: str,
        legacy_p4_app_path: Path | None,
    ) -> list[Path]:
        paths: list[Path] = []
        for line in output.splitlines():
            if not line.startswith("RESULT "):
                continue
            payload = line[7:].strip()
            if " replacements=" in payload:
                payload = payload.rsplit(" replacements=", 1)[0].strip()
            if payload:
                paths.append(Path(payload).resolve())
        if kind == JobKind.CONVERT_OPMANUAL_TO_BIT_XML:
            inferred = self._infer_opmanual_output_path(legacy_p4_app_path)
            if inferred is not None:
                paths.append(inferred)
        return paths

    def _infer_opmanual_output_path(self, legacy_p4_app_path: Path | None) -> Path | None:
        if legacy_p4_app_path is None:
            return None
        publisher_ini = Path(legacy_p4_app_path) / "publisher.ini"
        if not publisher_ini.is_file():
            return None
        config = configparser.ConfigParser()
        config.read(publisher_ini, encoding="utf-8")
        section = "ClientLinux" if os.name != "nt" else "ClientWin32"
        if not config.has_option(section, "projects_dir"):
            return None
        projects_dir = Path(os.path.expanduser(config.get(section, "projects_dir")))
        return (projects_dir / "tmp_auto_opmanual_conversion" / "bitplant_modules.xml").resolve()

    def _artifact_path(self, path: Path, project_path: Path) -> str:
        try:
            return path.resolve().relative_to(project_path.resolve()).as_posix()
        except ValueError:
            return path.name

    def _artifact_kind_for_path(self, path: Path) -> ArtifactKind:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return ArtifactKind.PDF
        if suffix in {".html", ".htm"}:
            return ArtifactKind.HTML
        if suffix in {".xml", ".book"}:
            return ArtifactKind.XML
        if suffix in {".fo", ".tex", ".texml", ".txt", ".log"}:
            return ArtifactKind.REPORT
        if suffix in {".zip", ".tar", ".gz", ".tgz"}:
            return ArtifactKind.PACKAGE
        return ArtifactKind.OTHER

    def _content_type_for_path(self, path: Path) -> str | None:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return "application/pdf"
        if suffix in {".html", ".htm"}:
            return "text/html"
        if suffix == ".xml":
            return "application/xml"
        if suffix == ".fo":
            return "application/xml"
        if suffix == ".texml":
            return "application/xml"
        if suffix in {".tex", ".log"}:
            return "text/plain"
        if suffix == ".css":
            return "text/css"
        if suffix == ".js":
            return "text/javascript"
        if suffix == ".txt":
            return "text/plain"
        if suffix == ".zip":
            return "application/zip"
        return None

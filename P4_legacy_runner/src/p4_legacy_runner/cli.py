from __future__ import print_function

import argparse
import json
import os
import subprocess
import sys

try:
    from shlex import quote as shell_quote
except ImportError:  # pragma: no cover - Python 2.7 fallback
    from pipes import quote as shell_quote

try:
    from .operations import HELPER_OPERATIONS, INTERFACE_OPERATIONS, all_operations, operation_spec
except (ImportError, ValueError):  # pragma: no cover - direct script fallback
    from operations import HELPER_OPERATIONS, INTERFACE_OPERATIONS, all_operations, operation_spec


DEFAULT_LANGUAGE = "de"
WEB_KIND_TO_COMMAND = {}


class RunnerConfig(object):
    def __init__(self, p4_app_path=None, python_executable=None):
        self.p4_app_path = resolve_p4_app_path(p4_app_path)
        self.python_executable = python_executable or os.environ.get(
            "P4_LEGACY_PYTHON",
            "python2.7",
        )


def package_dir():
    return os.path.dirname(os.path.abspath(__file__))


def candidate_repo_roots():
    current = package_dir()
    roots = []
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            break
        roots.append(parent)
        current = parent
    return roots


def repo_root_candidate():
    for root in candidate_repo_roots():
        if os.path.isfile(os.path.join(root, "P4_app", "interface.py")):
            return root
    return os.path.abspath(os.path.join(package_dir(), os.pardir, os.pardir, os.pardir))


def resolve_p4_app_path(value=None):
    if value:
        return os.path.abspath(value)
    env_value = os.environ.get("P4_LEGACY_APP_PATH")
    if env_value:
        return os.path.abspath(env_value)
    container_default = "/opt/P4_app"
    if os.path.exists(container_default):
        return container_default
    return os.path.join(repo_root_candidate(), "P4_app")


def interface_path(p4_app_path):
    return os.path.join(p4_app_path, "interface.py")


def helper_path():
    return os.path.join(package_dir(), "legacy_helpers.py")


def shell_join(command):
    return " ".join(shell_quote(str(part)) for part in command)


def common_project_args(args):
    command = []
    if getattr(args, "project_path", None):
        command.extend(["--project-path", os.path.abspath(args.project_path)])
    if getattr(args, "project_name", None):
        command.extend(["--project-name", args.project_name])
    if getattr(args, "language", None):
        command.extend(["--language", args.language])
    if getattr(args, "read_only", False):
        command.append("--read-only")
    if getattr(args, "legacy_dry_run", False):
        command.append("--dry-run")
    if getattr(args, "debug", False):
        command.append("--debug")
    return command


def build_interface_command(args, config):
    spec = INTERFACE_OPERATIONS[args.command]
    if spec.get("requires_project") and not getattr(args, "project_path", None):
        raise SystemExit("--project-path is required for {0}".format(args.command))
    if spec.get("requires_language") and not getattr(args, "language", None):
        raise SystemExit("--language is required for {0}".format(args.command))

    command = [config.python_executable, interface_path(config.p4_app_path)]
    command.extend(common_project_args(args))

    flag = spec["flag"]
    if args.command in ("convert-image", "convert-images"):
        command.extend([flag, args.source])
    elif args.command == "set-var":
        command.extend([flag, build_setvar_assignment(args)])
    elif args.command == "server-config":
        command.extend([flag, args.connection])
    else:
        command.append(flag)

    if args.command == "generate-pdf":
        if args.start_servercfg:
            command.append("--start-servercfg")
        if args.stop_servercfg:
            command.append("--stop-servercfg")
        if args.include is not None:
            command.extend(["--include", yes_no(args.include)])
    elif args.command == "generate-html":
        if args.noimages:
            command.append("--noimages")
        if args.include is not None:
            command.extend(["--include", yes_no(args.include)])
    elif args.command in ("pack-modules", "unpack-modules"):
        if args.schema:
            command.extend(["--schema", args.schema])
    elif args.command in ("convert-image", "convert-images"):
        if args.images_force is not None:
            command.extend(["--images-force", yes_no(args.images_force)])
        if args.topng:
            command.append("--topng")
    elif args.command == "aladin":
        command.extend(["--aladin-codes", args.aladin_codes])
    elif args.command == "opmanual-to-bit-xml":
        files = list(args.opmanual_files or [])
        for path in files:
            command.extend(["--opmanual-file", os.path.abspath(path)])
    elif args.command == "create-project":
        command.extend(["--client", args.client])
        command.extend(["--project-name", args.project_name])

    return command


def build_helper_command(args, config):
    if args.command not in HELPER_OPERATIONS:
        raise SystemExit("Unsupported helper command: {0}".format(args.command))
    spec = HELPER_OPERATIONS[args.command]
    if spec.get("requires_project") and not getattr(args, "project_path", None):
        raise SystemExit("--project-path is required for {0}".format(args.command))

    command = [
        config.python_executable,
        helper_path(),
        args.command,
        "--p4-app-path",
        config.p4_app_path,
    ]
    if getattr(args, "project_path", None):
        command.extend(["--project-path", os.path.abspath(args.project_path)])
    if getattr(args, "project_name", None):
        command.extend(["--project-name", args.project_name])
    if getattr(args, "xml_file", None):
        command.extend(["--xml-file", os.path.abspath(args.xml_file)])
    if getattr(args, "output_dir", None):
        command.extend(["--output-dir", os.path.abspath(args.output_dir)])
    if getattr(args, "output_file", None):
        command.extend(["--output-file", os.path.abspath(args.output_file)])
    if getattr(args, "etk_file", None):
        command.extend(["--etk-file", os.path.abspath(args.etk_file)])
    if getattr(args, "language", None):
        command.extend(["--language", args.language])
    if getattr(args, "debug", False):
        command.append("--debug")
    return command


def build_command(args, config):
    if args.command in INTERFACE_OPERATIONS:
        return build_interface_command(args, config)
    if args.command in HELPER_OPERATIONS:
        return build_helper_command(args, config)
    raise SystemExit("Unsupported command: {0}".format(args.command))


def build_setvar_assignment(args):
    if args.assignment:
        if "=" not in args.assignment:
            raise SystemExit("set-var assignment must use name=value")
        return args.assignment
    if args.name is None or args.value is None:
        raise SystemExit("set-var requires either name=value or --name plus --value")
    return "{0}={1}".format(args.name, args.value)


def yes_no(value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    lowered = str(value).strip().lower()
    if lowered in ("1", "true", "yes", "y", "on"):
        return "yes"
    if lowered in ("0", "false", "no", "n", "off"):
        return "no"
    raise SystemExit("Expected yes/no value, got: {0}".format(value))


def ensure_command_preconditions(command, config):
    if not os.path.isfile(interface_path(config.p4_app_path)):
        raise SystemExit(
            "P4_app interface.py not found: {0}".format(interface_path(config.p4_app_path))
        )
    if command in HELPER_OPERATIONS and not os.path.isfile(helper_path()):
        raise SystemExit("Legacy helper not found: {0}".format(helper_path()))


def resolve_web_command_name(operation):
    if not WEB_KIND_TO_COMMAND:
        for name in all_operations():
            spec = operation_spec(name)
            web_kind = spec.get("web_kind")
            if web_kind:
                WEB_KIND_TO_COMMAND[web_kind] = name
    if operation in WEB_KIND_TO_COMMAND:
        return WEB_KIND_TO_COMMAND[operation]
    if operation in INTERFACE_OPERATIONS or operation in HELPER_OPERATIONS:
        return operation
    raise SystemExit("Unsupported web operation: {0}".format(operation))


def load_web_job_parameters(args):
    if getattr(args, "parameters_json", None):
        try:
            return json.loads(args.parameters_json)
        except ValueError:
            raise SystemExit("Invalid --parameters-json payload")
    payload = os.environ.get("P4_WEB_JOB_PARAMETERS")
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except ValueError:
        raise SystemExit("Invalid P4_WEB_JOB_PARAMETERS payload")


def _append_arg(argv, name, value):
    if value is None:
        return
    text = str(value).strip()
    if not text:
        return
    argv.extend([name, text])


def _append_bool_flag(argv, name, value):
    if value:
        argv.append(name)


def _relative_to_root(path_text, root_text):
    if not path_text or not root_text:
        return None
    if os.path.isabs(path_text) != os.path.isabs(root_text):
        return None
    relative = os.path.relpath(os.path.normpath(path_text), os.path.normpath(root_text))
    if relative == ".":
        return ""
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        return None
    return relative


def _remap_web_job_path(value, parameters_project_path, runtime_project_path):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    runtime_root = str(runtime_project_path or "").strip()
    if not runtime_root:
        return text
    parameters_root = str(parameters_project_path or "").strip()
    relative = _relative_to_root(text, parameters_root)
    if relative is not None:
        return runtime_root if not relative else os.path.join(runtime_root, relative)
    if os.path.isabs(text):
        return text
    return os.path.join(runtime_root, text)


def build_web_job_argv(args):
    parameters = load_web_job_parameters(args)
    command_name = resolve_web_command_name(args.operation)
    parameters_project_path = parameters.get("project_path")

    argv = []
    if args.p4_app_path:
        argv.extend(["--p4-app-path", args.p4_app_path])
    if args.python:
        argv.extend(["--python", args.python])
    if args.print_command:
        argv.append("--print-command")
    if args.no_exec:
        argv.append("--no-exec")
    if args.json:
        argv.append("--json")
    if args.debug:
        argv.append("--debug")

    argv.append(command_name)
    _append_arg(argv, "--project-path", args.project_path)
    _append_arg(argv, "--project-name", args.project_name)
    _append_arg(argv, "--language", args.language or parameters.get("language"))
    _append_bool_flag(argv, "--read-only", args.read_only)
    _append_bool_flag(argv, "--legacy-dry-run", args.legacy_dry_run)

    if command_name in ("generate-pdf", "generate-html"):
        _append_arg(argv, "--include", parameters.get("include"))
    if command_name == "generate-pdf":
        _append_bool_flag(argv, "--start-servercfg", parameters.get("start_servercfg"))
        _append_bool_flag(argv, "--stop-servercfg", parameters.get("stop_servercfg"))
    if command_name == "generate-html":
        _append_bool_flag(argv, "--noimages", parameters.get("noimages"))
    if command_name in ("pack-modules", "unpack-modules"):
        _append_arg(argv, "--schema", parameters.get("schema"))
    if command_name in ("generate-lists", "check-index", "xsl-fo", "texml-pdf"):
        _append_arg(
            argv,
            "--xml-file",
            _remap_web_job_path(parameters.get("xml_file"), parameters_project_path, args.project_path),
        )
        _append_arg(
            argv,
            "--output-dir",
            _remap_web_job_path(
                parameters.get("output_dir"),
                parameters_project_path,
                args.project_path,
            ),
        )
    if command_name == "convert-sap-to-bit-xml":
        _append_arg(
            argv,
            "--etk-file",
            _remap_web_job_path(parameters.get("etk_file"), parameters_project_path, args.project_path),
        )
        _append_arg(
            argv,
            "--output-file",
            _remap_web_job_path(
                parameters.get("output_file"),
                parameters_project_path,
                args.project_path,
            ),
        )
    if command_name == "opmanual-to-bit-xml":
        files = parameters.get("opmanual_files") or []
        if isinstance(files, (str, bytes)):
            files = [files]
        for path in files:
            text = _remap_web_job_path(path, parameters_project_path, args.project_path)
            if text is None:
                continue
            text = str(text).strip()
            if text:
                argv.append(text)
    if command_name == "aladin":
        _append_arg(argv, "--aladin-codes", parameters.get("aladin_codes"))

    return argv


def run_web_job(args):
    delegate_argv = build_web_job_argv(args)
    delegate_args = parse_args(delegate_argv)
    return run(delegate_args)


def run(args):
    config = RunnerConfig(args.p4_app_path, args.python)
    if args.command == "list-commands":
        return list_commands(args)
    if args.command == "probe":
        return probe(config, args)
    if args.command == "run-web-job":
        return run_web_job(args)

    ensure_command_preconditions(args.command, config)
    command = build_command(args, config)
    if args.json:
        print(json.dumps({"command": command, "shell": shell_join(command)}, indent=2))
    elif args.print_command or args.no_exec:
        print(shell_join(command))

    if args.no_exec:
        return 0

    cwd = config.p4_app_path
    return subprocess.call(command, cwd=cwd)


def list_commands(args):
    if args.json:
        payload = []
        for name in all_operations():
            spec = operation_spec(name)
            payload.append(
                {
                    "name": name,
                    "web_kind": spec.get("web_kind"),
                    "runner": spec.get("runner"),
                    "mutates_project": bool(spec.get("mutates_project")),
                    "artifact_globs": spec.get("artifact_globs", []),
                    "description": spec.get("description", ""),
                }
            )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    for name in all_operations():
        spec = operation_spec(name)
        mutates = "mutates" if spec.get("mutates_project") else "artifact-only"
        print("{0:24} {1:10} {2:13} {3}".format(
            name,
            spec.get("runner"),
            mutates,
            spec.get("description", ""),
        ))
    return 0


def probe(config, args):
    payload = {
        "p4_app_path": config.p4_app_path,
        "interface_py": interface_path(config.p4_app_path),
        "interface_exists": os.path.isfile(interface_path(config.p4_app_path)),
        "helper_py": helper_path(),
        "helper_exists": os.path.isfile(helper_path()),
        "python": config.python_executable,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for key in sorted(payload):
            print("{0}: {1}".format(key, payload[key]))
    return 0 if payload["interface_exists"] and payload["helper_exists"] else 2


def add_global_arguments(parser):
    parser.add_argument("--p4-app-path", default=None, help="Path to the legacy P4_app tree.")
    parser.add_argument("--python", default=None, help="Python executable for legacy code.")
    parser.add_argument(
        "--print-command",
        action="store_true",
        help="Print the command before running.",
    )
    parser.add_argument(
        "--no-exec",
        action="store_true",
        help="Build/print the command without running it.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable command/details.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Pass legacy debug mode where supported.",
    )


def add_project_arguments(parser, language_default=DEFAULT_LANGUAGE):
    parser.add_argument(
        "--project-path",
        required=False,
        help="Materialized project workspace path.",
    )
    parser.add_argument("--project-name", default=None, help="Legacy sub-project name if needed.")
    parser.add_argument("--language", default=language_default, help="Language code or comma list.")
    parser.add_argument("--read-only", action="store_true", help="Pass legacy read-only mode.")
    parser.add_argument("--legacy-dry-run", action="store_true", help="Pass P4_app --dry-run.")


def build_parser():
    parser = argparse.ArgumentParser(prog="p4-legacy-runner")
    add_global_arguments(parser)
    sub = parser.add_subparsers(dest="command")

    list_parser = sub.add_parser("list-commands", help="List supported runner commands.")
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Print operation registry as JSON.",
    )

    probe_parser = sub.add_parser("probe", help="Check runner paths and helper availability.")
    probe_parser.add_argument("--json", action="store_true", help="Print probe result as JSON.")

    web_job = sub.add_parser("run-web-job", help="Run one P4_web job by web operation kind.")
    add_project_arguments(web_job)
    web_job.add_argument("--operation", required=True, help="P4_web job kind, for example pack_modules.")
    web_job.add_argument(
        "--parameters-json",
        default=None,
        help="Optional JSON object with extra job parameters. Falls back to P4_WEB_JOB_PARAMETERS.",
    )

    pdf = sub.add_parser("generate-pdf", help="Generate PDF.")
    add_project_arguments(pdf)
    pdf.add_argument("--include", default=None, help="Pass --include yes/no to P4_app.")
    pdf.add_argument("--start-servercfg", action="store_true")
    pdf.add_argument("--stop-servercfg", action="store_true")

    html = sub.add_parser("generate-html", help="Generate HTML.")
    add_project_arguments(html)
    html.add_argument("--include", default=None, help="Pass --include yes/no to P4_app.")
    html.add_argument("--noimages", action="store_true")

    for name in ("cut-source", "trunk-to-branch", "downgrade-to-p2"):
        command_parser = sub.add_parser(name, help=INTERFACE_OPERATIONS[name]["description"])
        add_project_arguments(command_parser)

    for name in ("export-translation", "import-translation"):
        command_parser = sub.add_parser(name, help=INTERFACE_OPERATIONS[name]["description"])
        add_project_arguments(command_parser, language_default=None)

    for name in ("pack-modules", "unpack-modules"):
        command_parser = sub.add_parser(name, help=INTERFACE_OPERATIONS[name]["description"])
        add_project_arguments(command_parser)
        command_parser.add_argument("--schema", default=None)

    aladin = sub.add_parser("aladin", help=INTERFACE_OPERATIONS["aladin"]["description"])
    add_project_arguments(aladin)
    aladin.add_argument("--aladin-codes", required=True)

    opmanual = sub.add_parser(
        "opmanual-to-bit-xml",
        help=INTERFACE_OPERATIONS["opmanual-to-bit-xml"]["description"],
    )
    add_project_arguments(opmanual)
    opmanual.add_argument("opmanual_files", nargs="*")

    for name in ("convert-image", "convert-images"):
        command_parser = sub.add_parser(name, help=INTERFACE_OPERATIONS[name]["description"])
        command_parser.add_argument("source")
        command_parser.add_argument("--images-force", default=None)
        command_parser.add_argument("--topng", action="store_true")

    create = sub.add_parser(
        "create-project",
        help=INTERFACE_OPERATIONS["create-project"]["description"],
    )
    create.add_argument("--client", required=True)
    create.add_argument("--project-name", required=True)

    setvar = sub.add_parser("set-var", help=INTERFACE_OPERATIONS["set-var"]["description"])
    add_project_arguments(setvar)
    setvar.add_argument("assignment", nargs="?")
    setvar.add_argument("--name", default=None)
    setvar.add_argument("--value", default=None)

    server = sub.add_parser(
        "server-config",
        help=INTERFACE_OPERATIONS["server-config"]["description"],
    )
    server.add_argument("connection")

    for name in ("generate-lists", "check-index", "xsl-fo", "texml-pdf"):
        command_parser = sub.add_parser(name, help=HELPER_OPERATIONS[name]["description"])
        add_project_arguments(command_parser)
        command_parser.add_argument("--xml-file", default=None)
        command_parser.add_argument("--output-dir", default=None)

    sap = sub.add_parser(
        "convert-sap-to-bit-xml",
        help=HELPER_OPERATIONS["convert-sap-to-bit-xml"]["description"],
    )
    add_project_arguments(sap)
    sap.add_argument("--etk-file", required=True)
    sap.add_argument("--output-file", default=None)

    return parser


def parse_args(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        raise SystemExit(2)
    return args


def main(argv=None):
    try:
        args = parse_args(argv)
        return run(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())

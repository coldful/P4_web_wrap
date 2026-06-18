# P4 Legacy Runner

Thin CLI/container adapter for running legacy `P4_app` operations from `P4_web`.

The runner does not copy or rewrite `P4_app`. It provides a stable command
contract around the old Python 2 application:

```text
P4_web job -> materialized project snapshot -> p4-legacy-runner -> P4_app -> artifacts
```

## Migration Plan

1. Keep `P4_app` untouched and executable as the source of truth.
2. Route all operations through explicit runner commands.
3. Prefer existing `P4_app/interface.py` flags when they exist.
4. Add helper entrypoints only for GUI-only features that have no `interface.py`
   flag.
5. Treat every `project-path` as a temporary snapshot prepared by `P4_web`.
6. Let the runner write outputs back into that snapshot.
7. Let `P4_web` collect artifacts by glob after the process exits.

## Operation Order

1. `generate-pdf`
2. `generate-html`
3. `xsl-fo`
4. `cut-source`
5. `generate-lists`
6. `check-index`
7. `export-translation`
8. `import-translation`
9. `pack-modules`
10. `unpack-modules`
11. `convert-sap-to-bit-xml`
12. `opmanual-to-bit-xml`
13. image conversion/admin commands

## Commands

Commands backed directly by `P4_app/interface.py`:

```bash
bin/p4-legacy-runner generate-pdf --project-path /work/project --language de
bin/p4-legacy-runner generate-html --project-path /work/project --language de
bin/p4-legacy-runner cut-source --project-path /work/project --language de
bin/p4-legacy-runner export-translation --project-path /work/project --language en
bin/p4-legacy-runner import-translation --project-path /work/project --language en
bin/p4-legacy-runner pack-modules --project-path /work/project --schema proced.xsd
bin/p4-legacy-runner unpack-modules --project-path /work/project --schema proced.xsd
bin/p4-legacy-runner trunk-to-branch --project-path /work/project --language de
bin/p4-legacy-runner downgrade-to-p2 --project-path /work/project --language de
bin/p4-legacy-runner opmanual-to-bit-xml /work/input/opmanual.xml
```

Commands backed by `legacy_helpers.py`:

```bash
bin/p4-legacy-runner xsl-fo --project-path /work/project --language de
bin/p4-legacy-runner generate-lists --project-path /work/project
bin/p4-legacy-runner check-index --project-path /work/project
bin/p4-legacy-runner convert-sap-to-bit-xml --etk-file /work/input/ETK.xml
```

Diagnostic commands:

```bash
bin/p4-legacy-runner list-commands
bin/p4-legacy-runner --p4-app-path ../../P4_app probe
bin/p4-legacy-runner --no-exec --p4-app-path ../../P4_app generate-pdf --project-path /tmp/project
bin/p4-legacy-runner run-web-job --operation pack_modules --project-path /tmp/project --parameters-json '{"schema":"proced.xsd"}'
```

## Local Usage

The runner needs a Python 2.7-compatible P4 runtime:

```bash
P4_LEGACY_APP_PATH=../../P4_app \
P4_LEGACY_PYTHON=python2.7 \
bin/p4-legacy-runner generate-pdf --project-path /abs/project --language de
```

On the current host this may fail if `python2.7` and legacy dependencies are not
installed. Use `--no-exec` to verify command construction without running legacy:

```bash
bin/p4-legacy-runner --no-exec --p4-app-path ../../P4_app generate-pdf --project-path /abs/project
```

## Docker Usage

Build the runner image from this directory:

```bash
docker build -t p4-legacy-runner P4_web_wrap/P4_legacy_runner
```

Run with `P4_app` and the materialized project mounted:

```bash
docker run --rm \
  -v "$PWD/P4_app:/opt/P4_app:ro" \
  -v "/abs/project:/work/project" \
  p4-legacy-runner \
  generate-pdf --project-path /work/project --language de
```

## P4_web Integration

For a local generic wrapper:

```env
P4_WEB_ENABLE_LEGACY_RUNNER=true
P4_WEB_LEGACY_RUNNER_COMMAND=../P4_legacy_runner/bin/p4-legacy-runner run-web-job --operation {operation} --project-path {project_path} --language {language}
```

For Docker:

```env
P4_WEB_ENABLE_LEGACY_RUNNER=true
P4_WEB_LEGACY_RUNNER_COMMAND=docker run --rm -e P4_WEB_JOB_PARAMETERS -e P4_WEB_JOB_KIND -v /home/kirill/Projects/p4/P4_app:/opt/P4_app:ro -v {project_path}:/work/project p4-legacy-runner run-web-job --operation {operation} --project-path /work/project --language {language}
```

The process must return exit code `0` on success and write produced files under
the mounted project path. `P4_web` then stores matching files as artifacts.

## Notes

- `project-path` must point to a `P4_web` version snapshot, not the user's live
  local folder.
- `generate-lists`, `check-index`, and `xsl-fo` use helper imports because the
  old GUI exposes them without stable `interface.py` flags.
- `convert-sap-to-bit-xml` follows `wizard.OnToXml`: ETK XML plus the configured
  `generate_xml/etk_table_template.xml` resource.

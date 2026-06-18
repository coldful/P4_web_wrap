# Local Sync

The first sync implementation is manual. This keeps offline work possible without
putting a background agent into the critical path too early.

## Scan

```bash
p4web sync scan ../000_Marine_A
```

This computes a manifest with path, size, mtime, SHA-256, and inferred file role.

## Import

```bash
p4web sync import-local ../000_Marine_A --project-name "000 Marine A" --label "initial import"
```

The same import is available through the shorter alias:

```bash
p4web import-local ../000_Marine_A --project-name "000 Marine A" --label "initial import"
```

The command:

1. creates a project when `--project-id` is omitted;
2. creates a new draft version;
3. stores every file under the version snapshot prefix;
4. writes file metadata to the database.

Future background sync should reuse the same manifest format.

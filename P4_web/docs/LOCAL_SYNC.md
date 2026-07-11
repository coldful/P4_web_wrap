# Local Sync

The first sync implementation is limited to local scanning. This keeps offline work
possible without exposing server-side imports by filesystem path.

## Scan

```bash
p4web sync scan ../000_Marine_A
```

This computes a manifest with path, size, mtime, SHA-256, and inferred file role.

## Import

Project import is available only through the web client folder upload flow. The
backend does not accept a filesystem path for project import.

Future background sync should reuse the same manifest format.

# P4 Web Client

Dependency-free browser client for the `P4_web` API.

```bash
cd P4_web_wrap/P4_web_client
python3 -m http.server 5173
```

Open http://localhost:5173.

The compact legacy-focused client is also available at:

```text
http://localhost:5173/reduced/
```

The API base defaults to `http://localhost:8000/api` and can be changed in the
top connection field.

When the UI is opened from a production host (not localhost), the client
auto-detects `https://your-host/api` or `http://your-host/api` unless a different
value is stored in the browser.

The File ribbon can create an empty project or import a local project folder.
Local import paths must be visible to the `P4_web` backend process. Imported
folders become a project version, so later imports can target an existing project.
Generation jobs run from the imported version snapshot.

Use `localhost` rather than `127.0.0.1` unless the backend CORS list also includes
`http://127.0.0.1:5173`.

from pathlib import Path

from fastapi.testclient import TestClient

from p4_web.api.dependencies import db_session, storage_dep
from p4_web.main import create_app
from p4_web.persistence.models import Artifact, FileObject
from p4_web.storage import LocalStorage


async def _fake_db_session():
    yield object()


def test_version_file_content_route_returns_inline_file(tmp_path: Path, monkeypatch) -> None:
    storage = LocalStorage(tmp_path / "storage")
    storage.put_bytes("versions/1/files/demo.xml", b"<root>demo</root>", "application/xml")
    app = create_app()
    app.dependency_overrides[db_session] = _fake_db_session
    app.dependency_overrides[storage_dep] = lambda: storage

    async def fake_get_version_file(session, version_id: str, file_id: str) -> FileObject:
        return FileObject(
            id=file_id,
            version_id=version_id,
            path="demo.xml",
            storage_key="versions/1/files/demo.xml",
            sha256="sha",
            size_bytes=17,
            content_type="application/xml",
            role="source_xml",
        )

    monkeypatch.setattr("p4_web.services.files.get_version_file", fake_get_version_file)

    with TestClient(app) as client:
        response = client.get("/api/versions/version-1/files/file-1/content")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.text == "<root>demo</root>"


def test_artifact_download_route_returns_attachment(tmp_path: Path, monkeypatch) -> None:
    storage = LocalStorage(tmp_path / "storage")
    storage.put_bytes("versions/1/artifacts/demo.pdf", b"%PDF-1.4\n", "application/pdf")
    app = create_app()
    app.dependency_overrides[db_session] = _fake_db_session
    app.dependency_overrides[storage_dep] = lambda: storage

    async def fake_get_artifact(session, artifact_id: str) -> Artifact:
        return Artifact(
            id=artifact_id,
            project_id="project-1",
            version_id="version-1",
            job_id="job-1",
            kind="pdf",
            path="demo.pdf",
            storage_key="versions/1/artifacts/demo.pdf",
            sha256="sha",
            size_bytes=9,
            content_type="application/pdf",
        )

    monkeypatch.setattr("p4_web.services.artifacts.get_artifact", fake_get_artifact)

    with TestClient(app) as client:
        response = client.get("/api/artifacts/artifact-1/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.content == b"%PDF-1.4\n"

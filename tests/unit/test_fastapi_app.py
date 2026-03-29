from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from rag_mcp.errors import ErrorCode, ServiceError, ServiceException
from rag_mcp.transport.fastapi_app import create_app


def _make_client(tmp_path: Path, mock_resources: MagicMock) -> TestClient:
    app = create_app(resource_service=mock_resources, data_dir=tmp_path)
    return TestClient(app, raise_server_exceptions=False)


def test_health_returns_ok(tmp_path: Path) -> None:
    client = _make_client(tmp_path, MagicMock())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_text_resource_returns_json(tmp_path: Path) -> None:
    mock_svc = MagicMock()
    mock_svc.read.return_value = {
        "uri": "rag://corpus/c1/d1#text-0",
        "type": "text",
        "text": "hello world",
        "metadata": {},
    }
    client = _make_client(tmp_path, mock_svc)
    resp = client.get("/resource", params={"uri": "rag://corpus/c1/d1#text-0"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "text"
    assert data["text"] == "hello world"


def test_get_resource_not_found_returns_404(tmp_path: Path) -> None:
    mock_svc = MagicMock()
    mock_svc.read.side_effect = ServiceException(
        ServiceError(code=ErrorCode.RESOURCE_NOT_FOUND, message="not found", hint="")
    )
    client = _make_client(tmp_path, mock_svc)
    resp = client.get("/resource", params={"uri": "rag://corpus/c1/d1#text-0"})
    assert resp.status_code == 404


def test_get_assets_returns_file(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets" / "doc1"
    assets_dir.mkdir(parents=True)
    img = assets_dir / "image-0.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

    client = _make_client(tmp_path, MagicMock())
    resp = client.get("/assets/doc1/image-0.png")
    assert resp.status_code == 200


def test_get_assets_missing_returns_404(tmp_path: Path) -> None:
    client = _make_client(tmp_path, MagicMock())
    resp = client.get("/assets/doc1/missing.png")
    assert resp.status_code == 404

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from rag_mcp.ingestion.vlm_client import VlmClient


def test_describe_image_returns_string(tmp_path):
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    client = VlmClient(api_key="fake", base_url="http://fake", model="fake")
    with patch("rag_mcp.ingestion.vlm_client.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "这是一张液压图"}}]}
        mock_httpx.post.return_value = mock_resp
        result = client.describe_image(img_path)
    assert isinstance(result, str)
    assert len(result) > 0


def test_describe_image_sends_base64(tmp_path):
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    client = VlmClient(api_key="fake", base_url="http://fake", model="fake")
    with patch("rag_mcp.ingestion.vlm_client.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_httpx.post.return_value = mock_resp
        client.describe_image(img_path)
    call_json = mock_httpx.post.call_args.kwargs.get("json") or mock_httpx.post.call_args[1].get("json")
    content = call_json["messages"][0]["content"]
    assert any(item.get("type") == "image_url" for item in content)


def test_describe_image_api_error_raises(tmp_path):
    from rag_mcp.errors import ServiceException
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    client = VlmClient(api_key="fake", base_url="http://fake", model="fake")
    with patch("rag_mcp.ingestion.vlm_client.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_httpx.post.return_value = mock_resp
        with pytest.raises(ServiceException):
            client.describe_image(img_path)

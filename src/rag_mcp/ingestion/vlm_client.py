from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import httpx

from rag_mcp.errors import ErrorCode, ServiceError, ServiceException


@dataclass
class VlmClient:
    api_key: str
    base_url: str
    model: str
    timeout: int = 60

    def describe_image(self, image_path: Path) -> str:
        image_data = base64.b64encode(Path(image_path).read_bytes()).decode()
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                    {"type": "text", "text": "请描述这张图片的内容，重点说明图中展示的技术信息。"}
                ]
            }]
        }
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise ServiceException(ServiceError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"VLM API error: {resp.status_code}",
                hint=resp.text[:200],
            ))
        return resp.json()["choices"][0]["message"]["content"]

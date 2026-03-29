from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from rag_mcp.errors import ErrorCode, ServiceException


def create_app(resource_service: Any, data_dir: Path) -> FastAPI:
    app = FastAPI()
    data_dir = Path(data_dir)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/resource")
    def get_resource(uri: str) -> JSONResponse:
        try:
            result = resource_service.read(uri)
            return JSONResponse(content=result)
        except ServiceException as exc:
            if exc.error.code == ErrorCode.RESOURCE_NOT_FOUND:
                raise HTTPException(status_code=404, detail=exc.error.message)
            raise HTTPException(status_code=500, detail=exc.error.message)

    @app.get("/assets/{doc_id}/{filename}")
    def get_asset(doc_id: str, filename: str) -> FileResponse:
        file_path = data_dir / "assets" / doc_id / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="asset not found")
        return FileResponse(str(file_path))

    return app

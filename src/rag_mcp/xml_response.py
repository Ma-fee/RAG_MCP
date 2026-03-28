from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from rag_mcp.errors import ErrorCode


def build_ok_response(node_name: str, payload: dict[str, Any]) -> str:
    root = ET.Element("response")
    ET.SubElement(root, "status").text = "ok"
    data_elem = ET.SubElement(root, "data")
    node_elem = ET.SubElement(data_elem, node_name)
    _populate_xml(node_elem, payload)
    return ET.tostring(root, encoding="unicode")


def build_error_response(
    code: ErrorCode, message: str, hint: str, details: dict[str, Any] | None = None
) -> str:
    root = ET.Element("response")
    ET.SubElement(root, "status").text = "error"
    err_elem = ET.SubElement(root, "error")
    ET.SubElement(err_elem, "code").text = code.value
    ET.SubElement(err_elem, "message").text = message
    ET.SubElement(err_elem, "hint").text = hint
    if details:
        details_elem = ET.SubElement(err_elem, "details")
        _populate_xml(details_elem, details)
    return ET.tostring(root, encoding="unicode")


def _populate_xml(parent: ET.Element, payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            child = ET.SubElement(parent, key)
            _populate_xml(child, value)
        return
    if isinstance(payload, list):
        for item in payload:
            child = ET.SubElement(parent, "item")
            _populate_xml(child, item)
        return
    parent.text = "" if payload is None else str(payload)


from __future__ import annotations

import copy
import re
from typing import Any

# Matches Chinese/English figure and table references like 图3-5, 表3-2, Figure 3, Table 2
_REF_RE = re.compile(
    r"(?P<label>(?:图|表|Figure|Table)\s*[\d\-–]+(?:\.\d+)?)"
)


def build_cross_references(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mutates a copy of entries to add related / related_weak links and rewrite text refs."""
    result: list[dict[str, Any]] = [copy.deepcopy(e) for e in entries]

    # Build caption → uri map for images and tables
    caption_to_uri: dict[str, str] = {}
    for entry in result:
        caption = (entry.get("caption") or "").strip()
        if caption and entry["type"] in ("image", "table"):
            caption_to_uri[caption] = entry["uri"]

    uri_to_entry: dict[str, dict] = {e["uri"]: e for e in result}

    for entry in result:
        if entry["type"] != "text":
            continue

        text = entry.get("text", "")
        matched_uris: list[str] = []

        def _replace(m: re.Match) -> str:
            label = m.group("label")
            target_uri = caption_to_uri.get(label)
            if target_uri:
                matched_uris.append(target_uri)
                return f"[{label}]({target_uri})"
            return label

        new_text = _REF_RE.sub(_replace, text)
        entry["text"] = new_text

        for target_uri in matched_uris:
            if target_uri not in entry["related"]:
                entry["related"].append(target_uri)
            target = uri_to_entry.get(target_uri)
            if target is not None and entry["uri"] not in target["related"]:
                target["related"].append(entry["uri"])

    # Fallback: same heading_path weak links for unlinked images/tables
    for entry in result:
        if entry["type"] not in ("image", "table"):
            continue
        if entry["related"]:
            continue  # already has strong links
        heading = entry.get("heading_path", "")
        if not heading:
            continue
        if "related_weak" not in entry:
            entry["related_weak"] = []
        for other in result:
            if other["uri"] == entry["uri"]:
                continue
            if other["type"] == "text" and other.get("heading_path") == heading:
                if other["uri"] not in entry["related_weak"]:
                    entry["related_weak"].append(other["uri"])

    return result

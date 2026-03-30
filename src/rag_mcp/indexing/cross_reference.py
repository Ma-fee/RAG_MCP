from __future__ import annotations

import copy
import re
from typing import Any

# Matches Chinese/English figure and table references like 图3-5, 表3-2, Figure 3, Fig 1-1, Table 2
_REF_RE = re.compile(
    r"(?P<label>(?:图|表|Figure|Fig|Table)\s*[\d\-–]+(?:\.\d+)?)"
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

    # Proximity fallback: for unlinked images/tables, find the nearest preceding text
    # entry by element_id order within the same doc and write a strong (related) link.
    # Falls back to same heading_path weak links when no element_id is available.
    def _el_order(entry: dict) -> int:
        eid = entry.get("element_id", "")
        try:
            return int(eid.split("-")[1])
        except (IndexError, ValueError):
            return -1

    # Group entries by doc_id for proximity search
    doc_entries: dict[str, list[dict]] = {}
    for entry in result:
        doc_id = entry.get("doc_id", "")
        doc_entries.setdefault(doc_id, []).append(entry)

    for entry in result:
        if entry["type"] not in ("image", "table"):
            continue
        if entry["related"]:
            continue  # already has strong links from caption match

        el_order = _el_order(entry)
        doc_id = entry.get("doc_id", "")

        if el_order >= 0:
            # Find nearest preceding text entry in the same doc (up to 3 steps back)
            candidates = [
                e for e in doc_entries.get(doc_id, [])
                if e["type"] == "text" and _el_order(e) < el_order
            ]
            candidates.sort(key=_el_order, reverse=True)
            if candidates:
                predecessor = candidates[0]
                if predecessor["uri"] not in entry["related"]:
                    entry["related"].append(predecessor["uri"])
                if entry["uri"] not in predecessor["related"]:
                    predecessor["related"].append(entry["uri"])
                continue

        # Fallback: same heading_path weak links
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

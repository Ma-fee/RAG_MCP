from __future__ import annotations

import argparse
from pathlib import Path

from rag_mcp.indexing.sections_mapping import build_sections_mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="Build section mapping JSON for list_sections")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(".rag_mcp_data"),
        help="RAG data directory that contains active_index.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: <active index dir>/sections_mapping.json)",
    )
    args = parser.parse_args()

    output_path = build_sections_mapping(data_dir=args.data_dir, output_path=args.output)
    print(f"sections mapping written to: {output_path}")


if __name__ == "__main__":
    main()

    #   uv run python scripts/build_sections_mapping.py --data-dir .rag_mcp_data --output /dataset/sections/sections_mapping.json                                                                             

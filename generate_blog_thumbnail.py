#!/usr/bin/env python3
"""
Standalone thumbnail generator for an existing blog markdown file.

Reuses the Codex-based thumbnail pipeline from ``blog_agent.py`` to generate a
thumbnail for a markdown/QMD file that has already been written. Unlike the
automatic path in ``blog_agent.py``, the artist style can be specified
explicitly and is not restricted to ``THUMBNAIL_ARTIST_STYLES``.

Example:
    python generate_blog_thumbnail.py --markdown output/202606231033.qmd --style "Claude Monet"
"""

import argparse
import sys
from pathlib import Path

from blog_agent import generate_thumbnail_with_codex


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the standalone thumbnail generator."""
    parser = argparse.ArgumentParser(
        description="Generate a blog thumbnail for an existing markdown/QMD file using Codex"
    )
    parser.add_argument(
        "--markdown",
        type=str,
        required=True,
        help="Path to the markdown/QMD file to generate a thumbnail for",
    )
    parser.add_argument(
        "--style",
        type=str,
        default=None,
        help=(
            "Artist style for the thumbnail (e.g. \"Claude Monet\"). "
            "Any artist may be given; if omitted, a style is chosen from the "
            "built-in roster."
        ),
    )
    return parser


def main() -> None:
    """Main entry point for the standalone thumbnail generator."""
    parser = build_parser()
    args = parser.parse_args()

    markdown_path = Path(args.markdown)
    if not markdown_path.is_file():
        print(f"Error: markdown file not found: {markdown_path}")
        sys.exit(1)

    generated = generate_thumbnail_with_codex(
        markdown_path,
        artist_style=args.style,
    )

    if not generated:
        print("Thumbnail generation failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()

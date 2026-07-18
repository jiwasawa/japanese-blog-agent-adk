#!/usr/bin/env python3
"""
Blog Writing Agent System using Google ADK

This script creates a multi-agent system that:
1. Fetches content from a URL or local PDF file using contextkit
2. Generates search queries related to the content
3. Performs parallel Google searches
4. Summarizes search results
5. Writes a final blog post
"""

import argparse
import base64
import binascii
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Tuple

from runner import run_blog_agent
from tools import YouTubeRateLimitError


DEFAULT_QMD_IMAGE = "https://picsum.photos/id/92/200"
THUMBNAIL_WIDTH = 600
THUMBNAIL_HEIGHT = 600
THUMBNAIL_EXTENSION = "jpg"
THUMBNAIL_FORMAT = "jpeg"


# Artist styles are rotated uniformly to maximize thumbnail diversity.
# Keep visually distinctive painters whose aesthetics still adapt well to a
# restrained, refined scientific palette.
THUMBNAIL_ARTIST_STYLES: Tuple[str, ...] = (
    "Pablo Picasso",
    "Paul Cézanne",
    "Wassily Kandinsky",
    "Henri Matisse",
    "Paul Klee",
    "Gustav Klimt",
    "Joan Miró",
    "Itō Jakuchū"
)


def select_thumbnail_style(style_rng: Callable[[], float] = random.random) -> str:
    """Select one thumbnail artist style using a uniform rotation over the roster."""
    styles = THUMBNAIL_ARTIST_STYLES
    index = min(int(style_rng() * len(styles)), len(styles) - 1)
    return styles[index]


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the blog agent."""
    parser = argparse.ArgumentParser(
        description="Blog Writing Agent System - Fetches URL or PDF content and writes an enriched blog post"
    )
    parser.add_argument(
        "url",
        type=str,
        help="The URL or local PDF file path to fetch content from and write a blog post about"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="Google API key (or set GOOGLE_API_KEY environment variable)",
        default=None
    )
    parser.add_argument(
        "--save-md",
        action="store_true",
        help="Save the blog post as a Quarto .md file"
    )
    parser.add_argument(
        "--custom",
        type=str,
        help="Custom instruction to add to the BlogWriterAgent instructions",
        default=None
    )
    parser.add_argument(
        "--english",
        action="store_true",
        help="Translate the blog post to English"
    )
    parser.add_argument(
        "--style",
        type=str,
        help="Style reference file name in the script directory (default: style_reference.md)",
        default=None
    )
    parser.add_argument(
        "--no-thumbnail",
        action="store_true",
        help="Skip automatic Codex thumbnail generation for Quarto QMD output"
    )
    return parser


def _replace_frontmatter_image(qmd_content: str, image_ref: str) -> str:
    """Return QMD content with the YAML frontmatter image field set."""
    lines = qmd_content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return qmd_content

    frontmatter_end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter_end = index
            break

    if frontmatter_end is None:
        return qmd_content

    image_line = f"image: {image_ref}\n"
    for index in range(1, frontmatter_end):
        if lines[index].lstrip().startswith("image:"):
            lines[index] = image_line
            return "".join(lines)

    lines.insert(frontmatter_end, image_line)
    return "".join(lines)


def _relative_posix_path(path: Path, start: Path) -> str:
    """Return a path relative to start when possible, using POSIX separators."""
    try:
        return path.resolve().relative_to(start.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_thumbnail_prompt(
    qmd_path: Path,
    thumbnail_path: Path,
    workspace_dir: Path,
    style_rng: Callable[[], float] = random.random,
    artist_style: Optional[str] = None,
) -> str:
    """Build instructions for Codex thumbnail generation from a QMD file."""
    qmd_display_path = _relative_posix_path(qmd_path, workspace_dir)
    thumbnail_display_path = _relative_posix_path(thumbnail_path, workspace_dir)
    artist_style = artist_style or select_thumbnail_style(style_rng)

    return f"""Read `{qmd_display_path}` and generate one thumbnail image for this Quarto blog post.
Full QMD path: `{qmd_path}`.

Use the ImageGen skill if it is available. The image must be based on the QMD title,
description, and article body.

Requirements:
- Save the final JPEG exactly at `{thumbnail_display_path}`.
- Create the parent directory if it does not exist.
- The final JPEG must originate from a fresh new ImageGen artifact created during this Codex run.
- After ImageGen returns, move or copy the selected fresh generated image into
  `{thumbnail_display_path}`; do not leave it only as an inline preview or only
  under `$CODEX_HOME`.
- If built-in ImageGen cannot expose a local file you can copy and `OPENAI_API_KEY`
  is already set, this prompt explicitly authorizes the ImageGen CLI fallback to
  generate a fresh image file at `{thumbnail_display_path}`. Do not ask for an
  API key during this automated run.
- Before using ImageGen output, ignore any image files that existed before this run started.
- Do not reuse, copy, resize, or convert images from previous runs.
- Do not convert or copy any pre-existing image from `$CODEX_HOME/generated_images`,
  `~/.codex/generated_images`, `output/`, or any other directory.
- Use a square 1:1 composition suitable for a technical blog thumbnail.
- Generate the image in the style of {artist_style}. Apply only the selected artist style, but do not make it too explicit.
- Use a refined scientific palette with restrained contrast, clear focal structure, and credible textures rather than stock-photo, marketing, or sci-fi game aesthetics.
- Do not include text, logos, watermarks, UI chrome, or fake article headlines.
- Do not modify the QMD file or any other project file.

If the ImageGen skill or fresh image generation is unavailable, do not create a placeholder
or reuse an old image.
Report the failure clearly.
"""


def resize_thumbnail(
    thumbnail_path: Path,
    width: int = THUMBNAIL_WIDTH,
    height: int = THUMBNAIL_HEIGHT,
    runner: Callable = subprocess.run,
    printer: Callable[[str], None] = print,
) -> bool:
    """Resize the thumbnail to the configured web-friendly dimensions."""
    dimensions = read_image_dimensions(thumbnail_path, runner=runner, printer=printer)
    if dimensions:
        source_width, source_height = dimensions
        square_size = min(source_width, source_height)
        crop_cmd = [
            "sips",
            "--cropToHeightWidth",
            str(square_size),
            str(square_size),
            str(thumbnail_path),
        ]
        if not run_image_command(crop_cmd, "Thumbnail square crop", runner, printer):
            return False

    cmd = ["sips", "-z", str(height), str(width), str(thumbnail_path)]
    if not run_image_command(cmd, "Thumbnail resize", runner, printer):
        return False

    convert_cmd = [
        "sips",
        "-s",
        "format",
        THUMBNAIL_FORMAT,
        str(thumbnail_path),
        "--out",
        str(thumbnail_path),
    ]
    return run_image_command(
        convert_cmd,
        "Thumbnail JPEG conversion",
        runner,
        printer,
    )


def read_image_dimensions(
    thumbnail_path: Path,
    runner: Callable = subprocess.run,
    printer: Callable[[str], None] = print,
) -> Optional[Tuple[int, int]]:
    """Return image dimensions from sips, or None if they cannot be read."""
    cmd = ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(thumbnail_path)]
    try:
        result = runner(
            cmd,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        printer("Warning: sips not found. Keeping generated thumbnail at original size.")
        return None
    except Exception as exc:
        printer(f"Warning: Thumbnail dimension check failed to start: {exc}")
        return None

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no details"
        printer(f"Warning: Thumbnail dimension check failed: {detail}")
        return None

    width = None
    height = None
    for line in result.stdout.splitlines():
        if "pixelWidth:" in line:
            width = int(line.rsplit(":", 1)[1].strip())
        elif "pixelHeight:" in line:
            height = int(line.rsplit(":", 1)[1].strip())

    if width is None or height is None:
        printer("Warning: Thumbnail dimensions were not found in sips output.")
        return None

    return width, height


def run_image_command(
    cmd: list,
    label: str,
    runner: Callable,
    printer: Callable[[str], None],
) -> bool:
    """Run an image-processing command and report non-fatal failures."""
    try:
        result = runner(
            cmd,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        printer("Warning: sips not found. Keeping generated thumbnail at original size.")
        return False
    except Exception as exc:
        printer(f"Warning: {label} failed to start: {exc}")
        return False

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no details"
        printer(f"Warning: {label} failed: {detail}")
        return False

    return True


def _decode_imagegen_result(result: str) -> Optional[bytes]:
    """Decode an ImageGen base64 payload from a Codex JSON event."""
    if not result:
        return None

    payload = result.strip()
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]

    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None


def _imagegen_result_from_codex_jsonl_text(jsonl_text: str) -> Optional[Tuple[bytes, str]]:
    """Return the latest ImageGen payload found in Codex JSONL output."""
    latest_result = None

    for line in jsonl_text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != "image_generation_end":
            continue

        image_bytes = _decode_imagegen_result(payload.get("result", ""))
        if image_bytes:
            call_id = payload.get("call_id") or "unknown call"
            latest_result = (image_bytes, f"Codex JSON event stream ({call_id})")

    return latest_result


def _imagegen_result_from_codex_session_file(
    session_file: Path,
    target_markers: Tuple[str, ...],
) -> Optional[Tuple[bytes, str, bool]]:
    """Return the latest ImageGen payload from one Codex session file."""
    latest_result = None
    mentions_target = False

    try:
        with session_file.open(encoding="utf-8") as handle:
            for line in handle:
                if any(marker and marker in line for marker in target_markers):
                    mentions_target = True

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                payload = event.get("payload")
                if not isinstance(payload, dict):
                    continue
                if payload.get("type") != "image_generation_end":
                    continue

                image_bytes = _decode_imagegen_result(payload.get("result", ""))
                if image_bytes:
                    latest_result = image_bytes
    except OSError:
        return None

    if not latest_result:
        return None

    return latest_result, str(session_file), mentions_target


def _imagegen_result_from_fresh_codex_sessions(
    thumbnail_path: Path,
    workspace_dir: Path,
    started_at: float,
) -> Optional[Tuple[bytes, str]]:
    """Find a fresh ImageGen payload in persisted Codex session logs."""
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    sessions_dir = codex_home / "sessions"
    if not sessions_dir.exists():
        return None

    target_markers = (
        str(thumbnail_path),
        thumbnail_path.as_posix(),
        _relative_posix_path(thumbnail_path, workspace_dir),
    )
    session_files = []
    cutoff = started_at - 5
    for session_file in sessions_dir.rglob("*.jsonl"):
        try:
            modified_at = session_file.stat().st_mtime
        except OSError:
            continue
        if modified_at >= cutoff:
            session_files.append((modified_at, session_file))

    fallback = None
    for _, session_file in sorted(
        session_files,
        key=lambda session: session[0],
        reverse=True,
    ):
        result = _imagegen_result_from_codex_session_file(session_file, target_markers)
        if not result:
            continue

        image_bytes, source, mentions_target = result
        if mentions_target:
            return image_bytes, f"Codex session log {source}"
        if fallback is None:
            fallback = (image_bytes, f"Codex session log {source}")

    return fallback


def _recover_thumbnail_from_codex_output(
    result: subprocess.CompletedProcess,
    thumbnail_path: Path,
    workspace_dir: Path,
    started_at: float,
    printer: Callable[[str], None],
) -> bool:
    """Recover a fresh ImageGen image when Codex did not write the target file."""
    recovered = _imagegen_result_from_codex_jsonl_text(result.stdout or "")
    if not recovered:
        recovered = _imagegen_result_from_fresh_codex_sessions(
            thumbnail_path,
            workspace_dir,
            started_at,
        )

    if not recovered:
        return False

    image_bytes, source = recovered
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_path.write_bytes(image_bytes)
    printer(f"Recovered fresh ImageGen artifact from {source}: {thumbnail_path}")
    return True


def generate_thumbnail_with_codex(
    qmd_path: Path,
    workspace_dir: Optional[Path] = None,
    codex_bin: str = "codex",
    runner: Callable = subprocess.run,
    printer: Callable[[str], None] = print,
    style_rng: Callable[[], float] = random.random,
    artist_style: Optional[str] = None,
) -> bool:
    """Generate a blog thumbnail with Codex and update QMD frontmatter on success.

    When ``artist_style`` is provided it is used verbatim; otherwise a style is
    selected from ``THUMBNAIL_ARTIST_STYLES`` using ``style_rng``.
    """
    qmd_path = Path(qmd_path)
    workspace_dir = Path(workspace_dir) if workspace_dir else Path(__file__).resolve().parent
    image_ref = f"{qmd_path.stem}.{THUMBNAIL_EXTENSION}"
    thumbnail_path = qmd_path.parent / image_ref
    artist_style = artist_style or select_thumbnail_style(style_rng)
    printer(f"{artist_style = }")

    prompt = build_thumbnail_prompt(
        qmd_path,
        thumbnail_path,
        workspace_dir,
        artist_style=artist_style,
    )
    cmd = [
        codex_bin,
        "exec",
        "--json",
        "-C",
        str(workspace_dir),
        "--sandbox",
        "danger-full-access",
        "-",
    ]

    codex_started_at = time.time()
    try:
        result = runner(
            cmd,
            input=prompt,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        printer("Warning: codex CLI not found. Skipping thumbnail generation.")
        return False
    except Exception as exc:
        printer(f"Warning: Codex thumbnail generation failed to start: {exc}")
        return False

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no details"
        printer(f"Warning: Codex thumbnail generation failed: {detail}")
        return False

    if not thumbnail_path.exists():
        _recover_thumbnail_from_codex_output(
            result,
            thumbnail_path,
            workspace_dir,
            codex_started_at,
            printer,
        )

    if not thumbnail_path.exists():
        printer(
            "Warning: Codex completed but did not create the expected thumbnail: "
            f"{thumbnail_path}"
        )
        return False

    resize_thumbnail(thumbnail_path, runner=runner, printer=printer)

    qmd_content = qmd_path.read_text(encoding="utf-8")
    qmd_path.write_text(
        _replace_frontmatter_image(qmd_content, image_ref),
        encoding="utf-8",
    )
    printer(f"Thumbnail image saved to: {thumbnail_path}")
    return True


def main():
    """Main entry point for the script."""
    parser = build_parser()
    args = parser.parse_args()

    # Set up API key
    if args.api_key:
        os.environ["GOOGLE_API_KEY"] = args.api_key
    elif "GOOGLE_API_KEY" not in os.environ:
        print("Error: GOOGLE_API_KEY not found. Please set it as an environment variable or use --api-key")
        sys.exit(1)
    
    # Run the agent system
    import asyncio
    try:
        blog_post, blog_description = asyncio.run(run_blog_agent(args.url, custom_instruction=args.custom, translate_to_english=args.english, style_file=args.style))
    except YouTubeRateLimitError as e:
        print(f"\nError: {e}")
        print("\nYouTube has rate-limited this IP address. Please wait a few hours and try again.")
        sys.exit(1)
    
    # Save the blog post to a file
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Generate filename with current datetime in YYYYMMDDHHMM format
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    output_filename = output_dir / f"{timestamp}.md"
    
    # Save QMD by default; --save-md keeps the legacy Markdown-only output.
    if not args.save_md:
        # Extract title from first "#" heading and remove it from blog post
        title = "Untitled"
        blog_post_lines = blog_post.split('\n')
        blog_post_without_title = blog_post_lines.copy()
        
        for i, line in enumerate(blog_post_lines):
            line_stripped = line.strip()
            if line_stripped.startswith('# '):
                title = line_stripped[2:].strip()  # Remove "# " prefix
                # Remove the title line from the blog post
                blog_post_without_title.pop(i)
                break
            elif line_stripped.startswith('#') and len(line_stripped) > 1:
                # Handle case where there might be multiple # without space
                title = line_stripped.lstrip('#').strip()
                # Remove the title line from the blog post
                blog_post_without_title.pop(i)
                break
        
        # Rejoin the blog post without the title
        blog_post_cleaned = '\n'.join(blog_post_without_title).lstrip('\n')
        
        # Escape quotes in title and description for YAML
        title_escaped = title.replace('"', '\\"')
        description_escaped = blog_description.replace('"', '\\"')
        
        # Get current date in YYYY-MM-DD format
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Create QMD content with metadata
        qmd_content = f"""---
title: "{title_escaped}"
description: "{description_escaped}"
author: "Junichiro Iwasawa"
date: "{current_date}"
categories: [LLM, AI, Podcast]
image: {DEFAULT_QMD_IMAGE}
---

{blog_post_cleaned}
"""
        
        # Save QMD file
        qmd_filename = output_dir / f"{timestamp}.qmd"
        with open(qmd_filename, 'w', encoding='utf-8') as f:
            f.write(qmd_content)
        
        print(f"Quarto QMD file saved to: {qmd_filename}")

        if args.no_thumbnail:
            print("Thumbnail generation skipped (--no-thumbnail).")
        else:
            generate_thumbnail_with_codex(qmd_filename)
    else:
        # Save the blog post
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(blog_post)
        
        print(f"\nBlog post saved to: {output_filename}")
    
    # Output the result
    print("\n" + "="*80)
    print("FINAL BLOG POST")
    print("="*80)
    print(blog_post)
    print("="*80)


if __name__ == "__main__":
    main()

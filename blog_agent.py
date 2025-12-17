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

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from runner import run_blog_agent
from tools import YouTubeRateLimitError


def main():
    """Main entry point for the script."""
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
    
    # If --save-qmd is specified, also save as .qmd file
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
image: https://picsum.photos/id/92/200
---

{blog_post_cleaned}
"""
        
        # Save QMD file
        qmd_filename = output_dir / f"{timestamp}.qmd"
        with open(qmd_filename, 'w', encoding='utf-8') as f:
            f.write(qmd_content)
        
        print(f"Quarto QMD file saved to: {qmd_filename}")
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

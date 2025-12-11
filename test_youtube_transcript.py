#!/usr/bin/env python3
"""Test script to debug YouTube transcript fetching (minimal requests version)."""

import sys

def test_youtube_transcript(video_id: str):
    """Test fetching a YouTube transcript using only yt-dlp."""
    print(f"Testing transcript fetch for video ID: {video_id}")
    print("-" * 50)
    
    # Check imports
    try:
        import yt_dlp
        print("✓ yt-dlp imported successfully")
    except ImportError:
        print("✗ yt-dlp not found")
        print("  Install with: pip install yt-dlp")
        return
    
    # Test: yt-dlp with English only (minimal requests)
    print("\nTest: Fetch with yt-dlp (English only)...")
    try:
        import tempfile
        import os
        import glob
        
        print("  Using temp dir...")
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],  # English only
                'outtmpl': os.path.join(temp_dir, '%(id)s'),
                'quiet': True,
                'no_warnings': True,
                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            }
            
            print("  Running yt-dlp download...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                
                files = glob.glob(os.path.join(temp_dir, f"{video_id}.*"))
                if not files:
                    print("  ✗ No subtitle files downloaded")
                else:
                    print(f"  ✓ Downloaded {len(files)} files: {[os.path.basename(f) for f in files]}")
                    
                    # Read the first file
                    file_path = files[0]
                    print(f"  Reading {os.path.basename(file_path)}...")
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    if file_path.endswith('.vtt'):
                        print("  Parsing VTT...")
                        lines = content.split('\n')
                        text_lines = []
                        for line in lines:
                            line = line.strip()
                            if (not line or line == 'WEBVTT' or '-->' in line or 
                                line.startswith('Kind:') or line.startswith('Language:')):
                                continue
                            if text_lines and text_lines[-1] == line:
                                continue
                            text_lines.append(line)
                        full_text = ' '.join(text_lines)
                    else:
                        full_text = content
                        
                    print(f"  ✓ Success! Got {len(full_text)} chars")
                    print(f"    Preview: {full_text[:150]}...")
                    
    except Exception as e:
        print(f"  ✗ yt-dlp failed: {type(e).__name__}: {e}")


def extract_video_id(url: str) -> str:
    """Extract video ID from a YouTube URL."""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    if parsed.netloc in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        return parse_qs(parsed.query).get('v', [None])[0]
    elif parsed.netloc == 'youtu.be':
        path = parsed.path.lstrip('/')
        if '?' in path:
            path = path.split('?')[0]
        return path
    return url


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_youtube_transcript.py <video_id_or_url>")
        sys.exit(1)
    
    input_arg = sys.argv[1]
    video_id = extract_video_id(input_arg)
    
    if not video_id:
        print(f"Could not extract video ID from: {input_arg}")
        sys.exit(1)
    
    test_youtube_transcript(video_id)

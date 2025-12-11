"""Tool definitions for the blog agent system.

This module provides tools for fetching content from URLs, with special handling
for YouTube URLs to extract video transcripts.
"""

import time
from typing import Optional
from urllib.parse import urlparse, parse_qs

from google.adk.tools import FunctionTool
from contextkit.read import read_link

# Optional imports for YouTube transcript fetching
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_TRANSCRIPT_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPT_AVAILABLE = False

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False


# =============================================================================
# Exceptions
# =============================================================================

class YouTubeRateLimitError(Exception):
    """Raised when YouTube returns 429 Too Many Requests."""
    pass


# =============================================================================
# General Helper Functions
# =============================================================================

def _sanitize_for_adk(text: str) -> str:
    """Replace curly braces so ADK won't treat them as template variables."""
    if not text:
        return text
    return text.replace("{", "｛").replace("}", "｝")


def _check_and_raise_rate_limit(error_str: str) -> None:
    """Check if error indicates rate limiting and raise YouTubeRateLimitError if so."""
    if '429' in error_str or 'Too Many Requests' in error_str:
        raise YouTubeRateLimitError(
            "YouTube rate limit hit (429). Please wait and try again later."
        )


# =============================================================================
# YouTube URL Helpers
# =============================================================================

def _is_youtube_url(url: str) -> bool:
    """Check if the URL is a YouTube URL."""
    parsed = urlparse(url)
    return parsed.netloc in ('youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com')


def _extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from a YouTube URL.
    
    Supports formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID
    """
    parsed = urlparse(url)
    if parsed.netloc in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        return parse_qs(parsed.query).get('v', [None])[0]
    elif parsed.netloc == 'youtu.be':
        return parsed.path.lstrip('/')
    return None


# =============================================================================
# Subtitle Parsing Helpers
# =============================================================================

def _parse_vtt(content: str) -> str:
    """Parse VTT subtitle content and extract plain text."""
    lines = content.split('\n')
    text_lines = []
    
    for line in lines:
        line = line.strip()
        # Skip header, timestamps, and empty lines
        if (not line or 
            line == 'WEBVTT' or 
            '-->' in line or 
            line.startswith('Kind:') or 
            line.startswith('Language:')):
            continue
        # Avoid consecutive duplicates (common in VTT)
        if text_lines and text_lines[-1] == line:
            continue
        text_lines.append(line)
    
    return ' '.join(text_lines)


def _parse_json3(content: str) -> str:
    """Parse JSON3 subtitle content and extract plain text."""
    import json
    data = json.loads(content)
    events = data.get('events', [])
    text_parts = []
    
    for event in events:
        for seg in event.get('segs', []):
            if 'utf8' in seg:
                text_parts.append(seg['utf8'])
    
    return ' '.join(text_parts).replace('\n', ' ')


# =============================================================================
# YouTube Transcript Fetching (yt-dlp)
# =============================================================================

def _fetch_with_ytdlp(video_id: str) -> str:
    """Fetch transcript using yt-dlp.
    
    Downloads subtitle files to a temp directory and parses them.
    Uses Android client to avoid some rate limiting.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Transcript text as a string
        
    Raises:
        ImportError: If yt-dlp is not installed
        YouTubeRateLimitError: If rate limited (429)
        Exception: For other download failures
    """
    if not YTDLP_AVAILABLE:
        raise ImportError("yt-dlp is not installed. Run: pip install yt-dlp")
    
    import tempfile
    import os
    import glob
    
    with tempfile.TemporaryDirectory() as temp_dir:
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'outtmpl': os.path.join(temp_dir, '%(id)s'),
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                
                # Find downloaded subtitle files
                files = glob.glob(os.path.join(temp_dir, f"{video_id}.*"))
                if not files:
                    raise Exception("No subtitle file downloaded")
                
                # Select English subtitle file if available
                selected_file = None
                for lang_pattern in ['.en.', '.en-US.', '.en-GB.']:
                    for f in files:
                        if lang_pattern in f:
                            selected_file = f
                            break
                    if selected_file:
                        break
                
                if not selected_file:
                    selected_file = files[0]
                
                # Read and parse the subtitle file
                with open(selected_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if selected_file.endswith('.vtt'):
                    return _parse_vtt(content)
                elif selected_file.endswith('.json3'):
                    return _parse_json3(content)
                else:
                    return content  # Return raw content as fallback
                    
        except Exception as e:
            error_str = str(e)
            _check_and_raise_rate_limit(error_str)
            raise Exception(f"yt-dlp download failed: {error_str}")


# =============================================================================
# YouTube Transcript Fetching (youtube-transcript-api)
# =============================================================================

def _try_fetch_transcript(transcript, max_retries: int, errors: list) -> Optional[str]:
    """Try to fetch a single transcript with retries.
    
    Returns transcript text on success, None on failure.
    Raises YouTubeRateLimitError if rate limited.
    """
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(1.0 * (2 ** (attempt - 1)))  # Exponential backoff
            
            chunks = transcript.fetch()
            text = ' '.join([chunk['text'] for chunk in chunks])
            
            if text.strip():
                return text
                
        except Exception as e:
            error_str = str(e)
            errors.append(f"{transcript.language_code} attempt {attempt + 1}: {type(e).__name__}: {error_str}")
            _check_and_raise_rate_limit(error_str)
            
            # Wait longer for ParseErrors (often transient)
            if "ParseError" in type(e).__name__ or "no element found" in error_str:
                time.sleep(2.0)
    
    return None


def _try_translate_transcript(transcript, max_retries: int, errors: list) -> Optional[str]:
    """Try to translate a transcript to English with retries.
    
    Returns translated text on success, None on failure.
    Raises YouTubeRateLimitError if rate limited.
    """
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(1.0 * (2 ** (attempt - 1)))
            
            translated = transcript.translate('en')
            chunks = translated.fetch()
            text = ' '.join([chunk['text'] for chunk in chunks])
            
            if text.strip():
                return text
                
        except Exception as e:
            error_str = str(e)
            errors.append(f"translate to en attempt {attempt + 1}: {type(e).__name__}: {error_str}")
            _check_and_raise_rate_limit(error_str)
    
    return None


def _fetch_youtube_transcript(video_id: str, max_retries: int = 3) -> str:
    """Fetch transcript from YouTube video.
    
    Tries multiple approaches in order:
    1. youtube-transcript-api with list_transcripts()
    2. youtube-transcript-api with get_transcript()
    3. yt-dlp fallback
    
    Args:
        video_id: YouTube video ID
        max_retries: Max retry attempts per method
        
    Returns:
        Transcript text as a string
        
    Raises:
        ImportError: If required libraries not installed
        YouTubeRateLimitError: If rate limited (429)
        Exception: If all methods fail
    """
    if not YOUTUBE_TRANSCRIPT_AVAILABLE:
        raise ImportError("youtube-transcript-api is not installed. Run: pip install youtube-transcript-api")
    
    errors = []
    
    # Approach 1: Use list_transcripts() to find and fetch available transcripts
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        available = list(transcript_list)
        
        if available:
            # Sort: prefer manual over auto-generated, prefer English
            available.sort(key=lambda t: (
                0 if not t.is_generated else 1,
                0 if t.language_code.startswith('en') else 1
            ))
            
            # Try fetching each transcript
            for transcript in available:
                result = _try_fetch_transcript(transcript, max_retries, errors)
                if result:
                    return result
            
            # Try translating auto-generated transcripts
            for transcript in available:
                if transcript.is_generated and transcript.is_translatable:
                    result = _try_translate_transcript(transcript, max_retries, errors)
                    if result:
                        return result
                        
    except YouTubeRateLimitError:
        raise
    except Exception as e:
        errors.append(f"list_transcripts: {type(e).__name__}: {str(e)}")
    
    # Approach 2: Try direct get_transcript()
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(2.0 * (2 ** (attempt - 1)))
            
            chunks = YouTubeTranscriptApi.get_transcript(video_id)
            text = ' '.join([chunk['text'] for chunk in chunks])
            
            if text.strip():
                return text
                
        except Exception as e:
            error_str = str(e)
            errors.append(f"get_transcript attempt {attempt + 1}: {type(e).__name__}: {error_str}")
            _check_and_raise_rate_limit(error_str)
    
    # Approach 3: yt-dlp fallback
    if YTDLP_AVAILABLE:
        try:
            return _fetch_with_ytdlp(video_id)
        except YouTubeRateLimitError:
            raise
        except Exception as e:
            error_summary = "; ".join(errors[-3:])
            raise Exception(f"All methods failed. API errors: {error_summary}. yt-dlp: {str(e)}")
    
    # All approaches failed
    error_summary = "; ".join(errors[-5:])
    raise Exception(f"Failed to fetch transcript for video {video_id}. Errors: {error_summary}")


# =============================================================================
# Main Tool Function
# =============================================================================

def fetch_url_content(url: str, heavy: bool = False, sel: Optional[str] = None, 
                      useJina: bool = False, ignore_links: bool = False) -> dict:
    """Fetch content from a URL. For YouTube URLs, fetches the video transcript.
    
    Args:
        url: The URL to fetch content from
        heavy: Use headless browser (for dynamic pages)
        sel: CSS selector to extract specific content
        useJina: Use Jina for markdown conversion
        ignore_links: Strip links from the content
    
    Returns:
        Dictionary with status and content:
        - Success: {"status": "success", "content": "...", "url": "..."}
        - Error: {"status": "error", "error_message": "..."}
        
    Raises:
        YouTubeRateLimitError: If YouTube rate limits the request (propagates up)
    """
    try:
        if _is_youtube_url(url):
            video_id = _extract_video_id(url)
            if not video_id:
                return {
                    "status": "error",
                    "error_message": f"Could not extract video ID from YouTube URL: {url}"
                }
            
            transcript = _fetch_youtube_transcript(video_id)
            content = _sanitize_for_adk(transcript)
        else:
            content = read_link(
                url=url,
                heavy=heavy,
                sel=sel,
                useJina=useJina,
                ignore_links=ignore_links
            )
            content = _sanitize_for_adk(content)
        
        return {
            "status": "success",
            "content": content,
            "url": url
        }
        
    except YouTubeRateLimitError:
        raise  # Propagate to stop the script
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Failed to fetch URL content: {str(e)}"
        }


# =============================================================================
# Tool Export
# =============================================================================

read_link_tool = FunctionTool(func=fetch_url_content)

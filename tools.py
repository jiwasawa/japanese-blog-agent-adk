"""Tool definitions for the blog agent system."""

from typing import Optional
from google.adk.tools import FunctionTool
from contextkit.read import read_link


def fetch_url_content(url: str, heavy: bool = False, sel: Optional[str] = None, 
                     useJina: bool = False, ignore_links: bool = False) -> dict:
    """Fetches content from a URL and converts it to markdown using contextkit.
    
    Args:
        url: The URL to read
        heavy: Use headless browser (requires extra setup steps before use)
        sel: CSS selector to pull content from
        useJina: Use Jina for the markdown conversion
        ignore_links: Whether to keep links or not
    
    Returns:
        Dictionary with status and content information.
        Success: {"status": "success", "content": "...", "url": "..."}
        Error: {"status": "error", "error_message": "..."}
    """
    try:
        content = read_link(
            url=url,
            heavy=heavy,
            sel=sel,
            useJina=useJina,
            ignore_links=ignore_links
        )
        return {
            "status": "success",
            "content": content,
            "url": url
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Failed to fetch URL content: {str(e)}"
        }


# Create the read_link tool
read_link_tool = FunctionTool(func=fetch_url_content)


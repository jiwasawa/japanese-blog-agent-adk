"""Execution logic for running the blog agent system."""

from typing import Tuple
from google.adk.runners import InMemoryRunner
from orchestration import create_blog_agent_system


async def run_blog_agent(url: str, custom_instruction: str = None, translate_to_english: bool = False) -> Tuple[str, str]:
    """Runs the blog writing agent system for a given URL.
    
    Args:
        url: The URL to fetch content from
        custom_instruction: Optional custom instruction for the BlogWriterAgent
        translate_to_english: If True, translates the blog post to English
    
    Returns:
        Tuple of (final_blog_post, blog_description) as strings
    """
    # Create the agent system
    root_agent = create_blog_agent_system(custom_instruction=custom_instruction, translate_to_english=translate_to_english)
    
    # Create runner
    runner = InMemoryRunner(agent=root_agent)
    
    # Run the agent with the URL
    print(f"Starting blog generation for URL: {url}")
    print("This may take a few minutes as the agents fetch content, search, and write...\n")
    
    response = await runner.run_debug(f"Fetch content from this URL and write a blog post: {url}")
    
    # Extract the final blog post and description from the response
    # run_debug returns events that we can iterate through
    final_blog = None
    blog_description = None
    all_text_parts = []
    link_enhanced_blog = None
    blog_writer_blog = None
    
    # Collect all text from events
    try:
        all_events = []
        if hasattr(response, '__aiter__'):
            # It's an async generator
            async for event in response:
                all_events.append(event)
        else:
            # Regular iterable
            all_events = list(response)
            
        for event in all_events:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        all_text_parts.append(part.text)
                        # Check for specific agents
                        if hasattr(event, 'author'):
                            if 'Translator' in str(event.author):
                                # Translator output takes highest priority when translation is enabled
                                final_blog = part.text
                            elif 'LinkEnhancer' in str(event.author):
                                link_enhanced_blog = part.text
                            elif 'BlogWriter' in str(event.author):
                                blog_writer_blog = part.text
                            elif 'Description' in str(event.author):
                                blog_description = part.text
                                
        # Prioritize Translator output if translation is enabled, otherwise LinkEnhancer, then BlogWriter
        if not final_blog:
            final_blog = link_enhanced_blog or blog_writer_blog
        
    except Exception as e:
        print(f"Warning: Error processing response: {e}")
    
    # Return the blog post - prefer identified agent output, otherwise use last text
    if not final_blog:
        if all_text_parts:
            # Return the last substantial text response (likely the blog post)
            final_blog = all_text_parts[-1]
        else:
            final_blog = "Blog post generation completed. Please check the console output for details."
    
    # Clean up description if it has any prefix
    if blog_description:
        # Remove any "ORIGINAL_URL:" prefix or similar if present
        blog_description = blog_description.strip()
    
    return final_blog, blog_description or ""


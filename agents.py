"""Agent creation functions for the blog agent system."""

import os
from typing import Optional
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import google_search
from config import retry_config
from tools import read_link_tool


def create_url_storage_agent() -> Agent:
    """Creates an agent that stores the original URL in session state."""
    return Agent(
        name="URLStorageAgent",
        model=Gemini(
            model="gemini-2.5-flash-lite",
            retry_options=retry_config
        ),
        instruction="""You are a URL storage agent. Your job is simple:
1. Extract the URL from the user's request (the user will ask to fetch content from a URL)
2. Output ONLY the URL in this exact format: "ORIGINAL_URL: [the URL here]"
3. Do not add any other text or explanation""",
        output_key="original_url"
    )


def create_url_fetcher_agent() -> Agent:
    """Creates the URL Fetcher Agent that fetches content from a URL."""
    return Agent(
        name="URLFetcherAgent",
        model=Gemini(
            model="gemini-2.5-flash-lite",
            retry_options=retry_config
        ),
        instruction="""You are a URL content fetcher. Your job is to:
1. Use the fetch_url_content tool to retrieve content from the URL provided by the user
2. Check the "status" field in the tool response
3. If status is "error", inform the user about the error
4. If status is "success", present the fetched content clearly
5. Make sure to preserve the full content as it will be used by subsequent agents""",
        tools=[read_link_tool],
        output_key="url_content"
    )


def create_query_generator_agent() -> Agent:
    """Creates the Query Generator Agent that generates search queries from content."""
    return Agent(
        name="QueryGeneratorAgent",
        model=Gemini(
            model="gemini-2.5-flash-lite",
            retry_options=retry_config
        ),
        instruction="""You are a search query generator. Your job is to:
1. Analyze the content provided: {url_content}
2. Generate up to 3 search queries that would help enrich and provide additional context for a blog post about this content
3. The queries should be designed to find complementary information, recent developments, related topics, or expert opinions
4. Output the queries as a numbered list (1-3)
5. Each query should be clear, specific, and likely to return useful results
6. Focus on queries that would add value to the original content""",
        output_key="search_queries"
    )


def create_search_summarize_agent(query_index: int) -> Agent:
    """Creates a Search+Summarize Agent for a specific query.
    
    Args:
        query_index: The index of the query (1-3) to identify this agent
    """
    return Agent(
        name=f"SearchSummarizeAgent{query_index}",
        model=Gemini(
            model="gemini-2.5-flash-lite",
            retry_options=retry_config
        ),
        instruction=f"""You are a search and summarization specialist. Your job is to:
1. Extract query {query_index} from the search queries list: {{search_queries}}
2. If query {query_index} does not exist in the list (e.g., fewer than {query_index} queries were generated), output: "No query {query_index} available. Skipping this search."
3. If the query exists, use the google_search tool to search for information using that specific query
4. Review the search results carefully
5. Summarize the search results, keeping ONLY the parts that are relevant to the original URL content: {{url_content}}
6. Focus on information that would enrich, complement, or provide additional context for the original content
7. Ignore information that is not relevant to the original content
8. Keep your summary concise but informative (approximately 100-200 words)
9. IMPORTANT: Include the URLs from the search results in your summary. List them at the end of your summary in a format like: "Sources: [URL1], [URL2], [URL3]"
10. If the search results are not relevant or no results are found, output: "No relevant information found for query {query_index}."
11. IMPORTANT: You MUST always produce an output, even if it's just a message indicating the query doesn't exist or no relevant information was found.""",
        tools=[google_search],
        output_key=f"summary_{query_index}"
    )


def create_blog_writer_agent(num_summaries: int = 3, custom_instruction: Optional[str] = None) -> Agent:
    """Creates the Blog Writer Agent that combines all content into a final blog post in Japanese.
    
    Args:
        num_summaries: Number of summary outputs to expect (default 3)
        custom_instruction: Optional custom instruction to insert into the final instruction
    """
    # Read the style reference file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    style_reference_path = os.path.join(script_dir, "style_reference.md")
    
    style_reference_content = ""
    try:
        with open(style_reference_path, 'r', encoding='utf-8') as f:
            style_reference_content = f.read().strip()
    except FileNotFoundError:
        pass  # Will handle empty content below

    # Build the instruction with placeholders for all summaries
    # Since we've modified the search agents to always output something,
    # all summary variables should now exist in the session state
    summary_placeholders = "\n".join([f"- Summary {i}: {{{f'summary_{i}'}}}" for i in range(1, num_summaries + 1)])
    
    base_instruction = f"""You are an expert Japanese blog writer. Your job is to write an engaging, deep, and well-structured blog post in Japanese.

Use the following information:
- Original URL content: {{url_content}}
- Search query enrichment summaries:
{summary_placeholders}

Note: Some summaries may indicate that no query was available or no relevant information was found. In such cases, simply ignore those summaries and focus on the summaries that contain actual enrichment information.
"""

    if style_reference_content:
        style_instruction = f"""
CRITICAL: You must follow the Japanese writing style demonstrated in the example blog post below. Study this example carefully and emulate its style, tone, and structure.

=== EXAMPLE BLOG POST (STYLE REFERENCE) ===

{style_reference_content}

=== END OF EXAMPLE ===

Instructions for writing the blog post:
1. **Target Audience**: Write for a sophisticated, educated audience who appreciates technical depth and nuanced analysis. Avoid oversimplification.
2. **Terminology**: When writing, spell names and advanced technical terms in the alphabet (e.g., "Large Language Model (LLM)" instead of "大規模言語モデル", "podcast" instead of "ポッドキャスト").
3. **Style**: Follow the reference style, but with a longer post.
"""
    else:
        # Fallback instruction mimicking the style of the reference file
        style_instruction = """
CRITICAL: You must follow a specific Japanese writing style characterized by technical depth, critical analysis, and a mix of casual and polite language.

Style Guidelines to Emulate:
1. **Language Mix**: Use a sophisticated blend of polite (丁寧語 - desu/masu) and casual (タメ口 - da/de aru) forms. Use polite forms for general explanations but switch to casual forms for emphatic points, critical analysis, or "inner voice" commentary.
2. **Tone**: Maintain a conversational yet highly intellectual and analytical tone. It should feel like a knowledgeable expert discussing a topic with a peer.
3. **Structure**: Organize arguments logically with clear section headings (##). Start with a strong hook that contextualizes the topic.
4. **Critical Perspective**: Do not just summarize. Provide critical analysis, point out limitations, and offer unique insights. Be balanced but opinionated.
5. **Parenthetical Commentary**: Use parenthetical asides (like this) to add nuance, humor, or meta-commentary to your main points.
6. **Technical Depth**: Do not oversimplify. Explain the "why" and "how" deeply. Assume the reader is intelligent and tech-savvy.
7. **Terminology**: When writing, spell names and advanced technical terms in the alphabet (e.g., "Large Language Model (LLM)" instead of "大規模言語モデル", "podcast" instead of "ポッドキャスト", "SaaS" instead of "サース").
8. **Engagement**: Write with high energy and engagement. Avoid dry, wikipedia-style descriptions.

Instructions for writing the blog post:
1. Write a Japanese blog post based on the content of the original URL content.
2. **Target Audience**: Write for a sophisticated, educated audience who appreciates technical depth and nuanced analysis.
3. **Depth**: Provide detailed analysis and context. Connect the dots between different pieces of information.
4. **Length**: The post should be substantial and detailed. Aim for a length that allows for deep exploration of the topic (e.g., 2000-3000 characters or more in Japanese).
"""

    # Build final instruction
    final_instruction = base_instruction + style_instruction
    
    # Add custom instruction if provided
    if custom_instruction:
        final_instruction += f"\n\nADDITIONAL COMMENTS:\n{custom_instruction}\n"
    
    # Add the title requirement at the end
    final_instruction += """
IMPORTANT: You MUST start your blog post with a title using a single "#" heading (e.g., "# Your Title Here")."""
    
    return Agent(
        name="BlogWriterAgent",
        model=Gemini(
            model="gemini-3-pro-preview",  #"gemini-2.5-pro", "gemini-3-pro-preview",
            retry_options=retry_config
        ),
        instruction=final_instruction,
        output_key="final_blog_post"
    )


def create_link_enhancer_agent() -> Agent:
    """Creates the Link Enhancer Agent that adds links to the blog post."""
    return Agent(
        name="LinkEnhancerAgent",
        model=Gemini(
            model="gemini-3-pro-preview",
            retry_options=retry_config
        ),
        instruction="""You are a link enhancement specialist. Your job is to naturally add links to a blog post.

You will receive:
- The blog post: {final_blog_post}
- The original URL: {original_url} (this will be in format "ORIGINAL_URL: [url]" - extract just the URL part)
- Search summaries that may contain URLs: {summary_1}, {summary_2}, {summary_3}

Your task:
1. Extract the original URL from {original_url}. It will be in the format "ORIGINAL_URL: [url]" - extract just the URL part.
2. Extract URLs from the search summaries. Look for URLs mentioned in the summaries, especially in "Sources:" sections or similar formats. URLs may be in formats like:
   - "Sources: [URL1], [URL2], [URL3]"
   - Plain URLs in the text
   - Markdown links [text](url)
3. Naturally integrate these links into the blog post markdown:
   - Add the original URL naturally within the content where it makes contextual sense (e.g., when first mentioning the source article, in the introduction, or in a "参考" or "出典" section)
   - Add relevant URLs from search results as markdown links [text](url) where they add value to the content
   - Ensure links are properly formatted as markdown: [link text](url)
   - Maintain the natural flow and readability of the Japanese text
   - Don't over-link - only add links where they genuinely add value and context
   - Links should feel natural and not forced
   - When adding the original URL, use appropriate Japanese text like "元記事" or "参考記事" or similar
4. Preserve all the original content and structure of the blog post
5. Output the enhanced blog post with links integrated naturally

Note: Some summaries may indicate no query was available or no information was found - ignore those when extracting URLs.""",
        output_key="final_blog_post"
    )


def create_description_agent() -> Agent:
    """Creates the Description Agent that generates a one-sentence description for the blog post."""
    return Agent(
        name="DescriptionAgent",
        model=Gemini(
            model="gemini-2.5-flash-lite",
            retry_options=retry_config
        ),
        instruction="""You are a blog description specialist. Your job is to write a compelling one-sentence description in Japanese for a blog post.

You will receive:
- The blog post content: {final_blog_post}

Your task:
1. Read and understand the blog post content
2. Write a single, compelling sentence in Japanese that captures the essence and main theme of the blog post
3. The description should:
   - Be exactly one sentence (no periods in the middle, just one sentence ending with a period or appropriate Japanese punctuation)
   - Be engaging and informative
   - Capture the main topic, analysis, or insight presented in the blog post
   - Use natural Japanese that flows well
   - Spell names and advanced technical terms in the alphabet (e.g., "Large Language Model" instead of "大規模言語モデル" or "LLM", "SaaS" instead of "サース").
   - Be concise but descriptive enough to give readers a clear sense of what the blog post is about
   - Follow the style of the example: "Google DeepMindの研究者へのインタビューを基に、Gemini 2.5 Proにおけるlong context能力と思考能力の技術的進化、現状の課題、そして今後の展望を分析する。"
4. Output ONLY the description sentence, nothing else. No prefix, no explanation, just the sentence itself.""",
        output_key="blog_description"
    )


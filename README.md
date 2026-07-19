# DeepDraft: The Automated Blog Writer Agent

A multi-agent system built with Google ADK that automatically fetches content from a URL, enriches it with related information from web searches, and generates a comprehensive blog post in Japanese (or English with the `--english` option).

## Features

- **URL Content Fetching**: Uses contextkit to fetch and convert URL content to markdown
- **Intelligent Query Generation**: Automatically generates up to 3 search queries related to the content
- **Parallel Web Search**: Performs multiple Google searches concurrently for efficiency
- **Smart Summarization**: Summarizes search results, keeping only relevant information with source URLs
- **Blog Post Generation**: Combines original content and summaries into a well-structured blog post in Japanese
- **Automatic Link Enhancement**: Naturally integrates original and source URLs into the text
- **Style Emulation**: Follows a specific Japanese technical blog writing style (configurable via `style_reference.md` or custom style file with `--style` option)
- **Blog Description Generation**: Automatically generates a one-sentence description for the blog post
- **English Translation**: Optional translation to English with `--english` flag (translates both blog post and description)
- **Quarto Support**: Saves blog posts as Quarto `.qmd` files with YAML frontmatter metadata by default
- **Automatic Thumbnail Generation**: Calls Codex CLI to generate a scientific journal-style local Quarto JPEG thumbnail from the completed QMD content, then crops and resizes it to 600x600
- **Custom Instructions**: Add custom instructions to the BlogWriterAgent via `--custom` argument

## Project Structure

The codebase is organized into modular components:

```
blog_agent_adk/
├── blog_agent.py      # Main entry point (CLI, file saving)
├── config.py          # Configuration settings (retry config)
├── tools.py           # Tool definitions (fetch_url_content)
├── agents.py          # Agent creation functions (8 agents)
├── orchestration.py   # System orchestration (agent assembly)
├── runner.py          # Execution logic (run_blog_agent)
├── style_reference.md # Style reference for blog writing
├── requirements.txt   # Python dependencies
└── output/            # Generated blog posts (created automatically)
```

## Architecture

The system uses a combination of `SequentialAgent` and `ParallelAgent` from Google ADK:

```
SequentialAgent (Root)
├── URL Storage Agent (extracts original URL)
├── URL Fetcher Agent (uses read_link tool)
├── Query Generator Agent (generates up to 3 search queries)
├── ParallelAgent (ParallelSearchTeam)
│   ├── Search+Summarize Agent 1 (for query 1)
│   ├── Search+Summarize Agent 2 (for query 2)
│   └── Search+Summarize Agent 3 (for query 3)
├── Blog Writer Agent (writes final post in Japanese)
├── ParallelAgent (ParallelFinalTeam)
│   ├── Link Enhancer Agent (adds links to the post)
│   └── Description Agent (generates one-sentence description)
└── Translator Agent (optional, translates to English when --english is used)
```

### Agent Details

- **URL Storage Agent**: Extracts and stores the original URL in session state
- **URL Fetcher Agent**: Fetches content from URL using contextkit's `read_link` function
- **Query Generator Agent**: Analyzes content and generates up to 3 enrichment queries
- **Search+Summarize Agents** (3 parallel agents): Each performs a Google search and summarizes relevant results with source URLs
- **Blog Writer Agent**: Combines all content into a comprehensive Japanese blog post following style guidelines
- **Link Enhancer Agent**: Naturally integrates original URL and search result URLs into the blog post
- **Description Agent**: Generates a one-sentence description for the blog post (Japanese by default, English when `--english` is used)
- **Translator Agent**: Translates the Japanese blog post to English while preserving markdown formatting (only added when `--english` is specified)

## Installation

1. Install the locked dependencies with [uv](https://docs.astral.sh/uv/):
```bash
uv sync --locked
```

`requirements.txt` remains available as a fully pinned compatibility export for environments that require pip.
Regenerate it after dependency changes with `uv export --locked --no-dev --no-hashes --output-file requirements.txt`.

2. Set up your Google API key:
```bash
export GOOGLE_API_KEY="your-api-key-here"
```

Or get one from [Google AI Studio](https://aistudio.google.com/app/api-keys).

3. Optional: set up Codex CLI for automatic thumbnail generation:
```bash
codex login
```

If Codex CLI is unavailable or thumbnail generation fails, the QMD file is still saved with the default placeholder image. When built-in ImageGen returns an inline/session payload instead of writing the target file directly, the script recovers that fresh payload from Codex JSON/session logs and saves it as the local thumbnail.

## Usage

### Basic Usage

```bash
uv run --locked python blog_agent.py <URL>
```

This saves a Quarto `.qmd` file by default and attempts to generate a local 600x600 thumbnail directly under `output/`.

### With API Key as Argument

```bash
uv run --locked python blog_agent.py <URL> --api-key <your-api-key>
```

### Save as Markdown File

```bash
uv run --locked python blog_agent.py <URL> --save-md
```

### Skip Thumbnail Generation

```bash
uv run --locked python blog_agent.py <URL> --no-thumbnail
```

### Add Custom Instructions

```bash
uv run --locked python blog_agent.py <URL> --custom "Focus on technical details and include code examples where relevant."
```

Custom instructions are inserted into the BlogWriterAgent's instruction set and can be used to modify writing style, focus areas, or add specific requirements.

### Use Custom Style Reference File

```bash
uv run --locked python blog_agent.py <URL> --style style_XX.md
```

The `--style` option allows you to specify a custom style reference file located in the script directory. The file should contain an example blog post that demonstrates the writing style you want the BlogWriterAgent to emulate. If not specified, the system defaults to `style_reference.md`. The style file is used as a reference for tone, structure, and writing patterns.

### Translate to English

```bash
uv run --locked python blog_agent.py <URL> --english
```

When `--english` is specified:
- The blog post is written in Japanese first (as usual)
- Links are enhanced (as usual)
- The blog post is translated to English
- The description is generated in English (instead of Japanese)
- The final output is in English

### Combined Options

```bash
uv run --locked python blog_agent.py <URL> --english --custom "Focus on technical details" --style style_XX.md
```

## Output

The system generates files in the `output/` directory:

- **Markdown files**: `output/YYYYMMDDHHMM.md` - Standard markdown blog posts
- **Quarto files**: `output/YYYYMMDDHHMM.qmd` - Quarto format with YAML metadata (default)
- **Thumbnail files**: `output/YYYYMMDDHHMM.jpg` - Local 600x600 JPEG thumbnail images generated by Codex for QMD output

Files are named with a timestamp in `YYYYMMDDHHMM` format (e.g., `202511271430.qmd`).

## How It Works

1. **URL Storage Agent**: Extracts the original URL from the user's request and stores it in session state.

2. **URL Fetcher Agent**: Fetches the content from the provided URL using contextkit's `read_link` function, converting it to markdown format.

3. **Query Generator Agent**: Analyzes the fetched content and generates up to 3 search queries designed to enrich and provide additional context for the blog post.

4. **Search+Summarize Agents** (Parallel): Each agent takes one query, performs a Google search, and summarizes the results, keeping only information relevant to the original content. Each summary includes source URLs.

5. **Blog Writer Agent**: Combines the original URL content and search summaries to write a comprehensive blog post in Japanese. The agent follows style guidelines from `style_reference.md` (or uses fallback instructions if the file is missing). Custom instructions can be added via the `--custom` argument.

6. **Link Enhancer Agent** & **Description Agent** (Parallel): 
   - Link Enhancer naturally integrates the original URL and relevant source links into the blog post
   - Description Agent generates a one-sentence description (Japanese by default, English when `--english` is used)

7. **Translator Agent** (Optional, when `--english` is specified): Translates the Japanese blog post to English while preserving all markdown formatting, links, and structure. The translation maintains the original tone and style.

8. **Codex Thumbnail Generation** (Default for QMD output): After the QMD file is saved, the script calls `codex exec --json` with instructions to use the ImageGen skill when available. If Codex writes the thumbnail directly, or if the script can recover a fresh ImageGen payload from the Codex event stream/session log, the image is cropped/resized to JPEG and the QMD `image:` frontmatter is updated to reference it.

## Configuration

### Style Reference

The blog writing style can be customized in two ways:

1. **Default style file**: Edit `style_reference.md` in the script directory. This file contains an example blog post that the BlogWriterAgent will emulate.

2. **Custom style file**: Use the `--style` command-line argument to specify a different style reference file:
   ```bash
   uv run --locked python blog_agent.py <URL> --style style_XX.md
   ```
   The file must be located in the script directory. The BlogWriterAgent will study this example and emulate its style, tone, and structure.

If the style file is missing or empty, the system uses built-in fallback style instructions. Note: Style files containing LaTeX math expressions (with curly braces) are automatically sanitized to prevent template variable conflicts.

### Models Used

- **Lightweight Agents**: `gemini-2.5-flash-lite` (URL Storage, URL Fetcher, Query Generator, Search+Summarize, Description)
- **Writer Agents**: `gemini-3-pro-preview` (Blog Writer, Link Enhancer, Translator)

### Retry Configuration

Located in `config.py`:
- Attempts: 5
- Exponential backoff base: 7
- Initial delay: 1 second
- HTTP status codes retried: 429, 500, 503, 504

### Search Queries

The system generates up to 3 search queries by default. This can be modified in `orchestration.py` by changing the range in the `search_summarize_agents` list.

## Requirements

- Python 3.10+
- uv
- Google ADK (`google-adk`)
- ContextKit (`contextkit`)
- Google API Key for Gemini models

## File Descriptions

- **`blog_agent.py`**: Main entry point with CLI argument parsing and file saving logic
- **`config.py`**: Shared configuration (retry settings)
- **`tools.py`**: Tool definitions (`fetch_url_content` function wrapped as `FunctionTool`)
- **`agents.py`**: All agent creation functions (8 agents: URL Storage, URL Fetcher, Query Generator, Search+Summarize x3, Blog Writer, Link Enhancer, Description, Translator)
- **`orchestration.py`**: Assembles agents into SequentialAgent and ParallelAgent structures
- **`runner.py`**: Executes the agent system and processes responses
- **`style_reference.md`**: Example blog post used as style reference (optional)
- **`requirements.txt`**: Python package dependencies

## License

This project is for educational purposes. Please ensure you comply with the terms of service for:
- Google ADK
- ContextKit
- Google Search API
- Any websites you fetch content from

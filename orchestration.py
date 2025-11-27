"""System orchestration for the blog agent system."""

from google.adk.agents import SequentialAgent, ParallelAgent
from agents import (
    create_url_storage_agent,
    create_url_fetcher_agent,
    create_query_generator_agent,
    create_search_summarize_agent,
    create_blog_writer_agent,
    create_link_enhancer_agent,
    create_description_agent
)


def create_blog_agent_system(custom_instruction: str = None) -> SequentialAgent:
    """Creates the complete blog writing agent system with all agents orchestrated.
    
    Args:
        custom_instruction: Optional custom instruction for the BlogWriterAgent
    """
    
    # Create individual agents
    url_storage = create_url_storage_agent()
    url_fetcher = create_url_fetcher_agent()
    query_generator = create_query_generator_agent()
    
    # Create search+summarize agents (max 3)
    search_summarize_agents = [
        create_search_summarize_agent(i) for i in range(1, 4)
    ]
    
    # Create parallel agent for search operations
    parallel_search_team = ParallelAgent(
        name="ParallelSearchTeam",
        sub_agents=search_summarize_agents
    )
    
    # Create blog writer agent
    blog_writer = create_blog_writer_agent(num_summaries=3, custom_instruction=custom_instruction)
    
    # Create link enhancer agent
    link_enhancer = create_link_enhancer_agent()
    
    # Create description agent
    description_agent = create_description_agent()
    
    # Create parallel agent for link enhancement and description generation
    parallel_final_team = ParallelAgent(
        name="ParallelFinalTeam",
        sub_agents=[link_enhancer, description_agent]
    )
    
    # Create root sequential agent that orchestrates everything
    root_agent = SequentialAgent(
        name="BlogWritingSystem",
        sub_agents=[
            url_storage,
            url_fetcher,
            query_generator,
            parallel_search_team,
            blog_writer,
            parallel_final_team
        ]
    )
    
    return root_agent


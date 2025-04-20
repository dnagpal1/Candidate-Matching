import logging
from typing import List, Optional

from langgraph.graph import StateGraph, START, END

from app.graphs.candidate_discovery.schema import (
    DiscoveryState,
    SearchParameters,
    CandidateProfile,
)
from app.graphs.candidate_discovery.nodes import (
    search_linkedin_candidates,
)

logger = logging.getLogger(__name__)


def create_discovery_graph():
    """
    Create a LangGraph for candidate discovery.
    
    Returns:
        StateGraph: A LangGraph instance for candidate discovery
    """
    # Create the graph
    graph = StateGraph(DiscoveryState)
    
    # Add nodes to the graph
    graph.add_node("linkedin_search", search_linkedin_candidates)
    
    # Add edges to the graph
    graph.add_edge(START, "linkedin_search")
    graph.add_edge("linkedin_search", END)

    graph.set_entry_point("linkedin_search")
    
    # Compile the graph
    compiled_graph = graph.compile()
    
    return compiled_graph


async def run_discovery_graph(
    job_title: str,
    location: str,
    company: Optional[str] = None,
    skills: Optional[List[str]] = None,
    max_results: int = 20,
) -> List[CandidateProfile]:
    """
    Run the candidate discovery graph.
    
    Parameters:
        job_title: Job title to search for
        location: Location to search in
        company: Optional company name filter
        skills: Optional list of skills to filter by
        max_results: Maximum number of results to return
        
    Returns:
        List of discovered candidate profiles
    """
    logger.info(f"Starting candidate discovery for {job_title} in {location}")
    
    # Create search parameters
    search_params = SearchParameters(
        job_title=job_title,
        location=location,
        company=company,
        skills=skills,
        max_results=max_results,
    )
    
    # Create initial state
    initial_state = DiscoveryState(search_params=search_params)
    
    # Create the graph
    graph = create_discovery_graph()
    
    # Run the graph
    try:
        result = await graph.ainvoke(initial_state)
        
        logger.info(f"Candidate discovery complete. Found {len(result.valid_candidates)} profiles")
        return result.valid_candidates
    except Exception as e:
        logger.error(f"Error during candidate discovery: {str(e)}", exc_info=True)
        raise
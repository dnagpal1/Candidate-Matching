import logging
from typing import List, Optional

from langgraph.graph import StateGraph, START, END

from app.graphs.candidate_discovery.schema import (
    DiscoveryState,
    SearchParameters,
    CandidateProfile,
    UserQuery,
)
from app.graphs.candidate_discovery.nodes import (
    parse_intent_node,
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
    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("linkedin_search", search_linkedin_candidates)
    
    # Add edges to the graph
    graph.add_edge(START, "parse_intent")
    graph.add_edge("parse_intent", "linkedin_search")
    graph.add_edge("linkedin_search", END)

    graph.set_entry_point("parse_intent")
    
    # Compile the graph
    compiled_graph = graph.compile()
    
    return compiled_graph


async def run_discovery_graph(
    query: str,
) -> List[CandidateProfile]:
    """
    Run the candidate discovery graph.
    
    Parameters:
        query: The query to search for
        
    Returns:
        List of discovered candidate profiles
    """
    logger.info(f"Starting candidate discovery for {query}")
    # Create the user query
    initial_state = DiscoveryState(query_string=query)
    
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
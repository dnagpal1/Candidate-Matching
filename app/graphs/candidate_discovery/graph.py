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
    plan_actions_node,
    search_candidates_parallel_node,
    validate_profiles_node,
)

logger = logging.getLogger(__name__)


def should_continue_searching(state: DiscoveryState) -> str:
    """
    Conditional routing function to determine if we should search more websites.
    Returns the name of the next node to route to.
    """
    if state.should_search_more:
        return "search_candidates"
    return "end"


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
    graph.add_node("plan_actions", plan_actions_node)
    graph.add_node("search_candidates", search_candidates_parallel_node)
    graph.add_node("validate_profiles", validate_profiles_node)
    
    # Add edges to the graph
    graph.add_edge(START, "parse_intent")
    graph.add_edge("parse_intent", "plan_actions")
    graph.add_edge("plan_actions", "search_candidates")
    graph.add_edge("search_candidates", "validate_profiles")
    
    # Add conditional edges for looping
    graph.add_conditional_edges(
        "validate_profiles",
        should_continue_searching,
        {
            "search_candidates": "search_candidates",
            "end": END
        }
    )

    graph.set_entry_point("parse_intent")
    
    # Compile the graph
    compiled_graph = graph.compile()
    
    return compiled_graph


async def run_discovery_graph(
    query: str,
    min_required_profiles: int = 5,
) -> List[CandidateProfile]:
    """
    Run the candidate discovery graph.
    
    Parameters:
        query: The query to search for
        min_required_profiles: Minimum number of profiles to find before stopping
        
    Returns:
        List of discovered candidate profiles
    """
    logger.info(f"Starting candidate discovery for {query}")
    # Create the initial state
    initial_state = DiscoveryState(
        query_string=query,
        min_required_profiles=min_required_profiles,
    )
    
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
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.models.candidate import Candidate
from app.services.discovery_service import DiscoveryService, LinkedInSearchParams
from app.agents.candidate_discovery.agent import (
    candidate_discovery_agent, 
    CandidateDiscoveryContext, 
    CandidateList,
    CandidateOutput
)
from agents import Runner
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/linkedin/search", response_model=List[Candidate])
async def search_linkedin(
    background_tasks: BackgroundTasks,
    title: str = Query(..., description="Job title to search for"),
    location: str = Query(..., description="Location to search in"),
    company: Optional[str] = Query(None, description="Company name filter"),
    skills: Optional[List[str]] = Query(None, description="Skills to filter by"),
    max_results: int = Query(20, ge=1, le=100, description="Maximum number of results to return"),
    run_in_background: bool = Query(False, description="Run search as a background task"),
    discovery_service: DiscoveryService = Depends(),
):
    """
    Search for candidates on LinkedIn with the specified criteria.
    Results are automatically saved to the database.
    
    Can be run as a background task for larger searches.
    """
    # Create the context for the agent
    context = CandidateDiscoveryContext(
        job_title=title,
        location=location,
        company=company,
        skills=skills,
        max_profiles=max_results
    )
    
    # Create a unique ID for this search task
    task_id = f"search_{uuid.uuid4().hex[:8]}"
    
    async def run_agent():
        logger.info(f"Running candidate discovery agent for task {task_id}")
        # Create the user input for the agent
        input_items = [{"role": "user", "content": f"Find {title} professionals in {location}"}]
        
        try:
            # Run the agent
            result = await Runner.run(candidate_discovery_agent, input_items, context=context)
            
            # Log the agent's responses
            for item in result.new_items:
                if hasattr(item, 'content'):
                    logger.info(f"Agent output: {item.content}")
            
            # Get the discovered candidates from the context
            logger.info(f"Agent discovered {len(context.discovered_candidates)} candidates")
            
            # Save candidates to the database if required
            if len(context.discovered_candidates) > 0:
                await discovery_service.save_candidates(context.discovered_candidates)
                
            return context.discovered_candidates
        except Exception as e:
            logger.error(f"Error running agent: {str(e)}", exc_info=True)
            raise
    
    if run_in_background:
        # Run the task in the background
        background_tasks.add_task(run_agent)
        # Return an empty list immediately
        return []
    
    try:
        # Run the agent synchronously
        return await run_agent()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during LinkedIn search: {str(e)}",
        )


@router.get("/status/{task_id}", response_model=dict)
async def get_search_status(
    task_id: str,
    discovery_service: DiscoveryService = Depends(),
):
    """
    Get the status of a background search task.
    """
    status_info = await discovery_service.get_task_status(task_id)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return status_info 
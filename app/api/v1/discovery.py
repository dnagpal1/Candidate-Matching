from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
import uuid
import logging

from app.models.candidate import Candidate, CandidateCreate
from app.services.discovery_service import DiscoveryService
from app.graphs.candidate_discovery import run_discovery_graph

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/search", response_model=List[Candidate])
async def search_candidates(
    background_tasks: BackgroundTasks,
    query: str = Query(..., description="The query to search for (e.g., 'Software Engineer in San Francisco with React skills')"),
    min_profiles: int = Query(5, description="Minimum number of profiles to find before stopping"),
    run_in_background: bool = Query(False, description="Run search as a background task"),
    discovery_service: DiscoveryService = Depends(),
):
    """
    Search for candidates across multiple platforms (LinkedIn, Wellfound, GitHub) with the specified criteria.
    Results are automatically saved to the database.
    
    This uses a ReAct-style agent that:
    1. Parses the intent of your query
    2. Plans which websites to search
    3. Searches each website in sequence 
    4. Validates profiles and decides if more searching is needed
    
    Can be run as a background task for larger searches.
    """
    # Create a unique ID for this search task
    task_id = f"search_{uuid.uuid4().hex[:8]}"
    
    # Define the search function
    async def run_search():
        logger.info(f"Running candidate discovery for task {task_id}")
        try:
            # Run the discovery graph
            candidates = await run_discovery_graph(
                query=query,
                min_required_profiles=min_profiles,
            )
            
            # Convert to CandidateCreate for database storage
            candidate_creates = []
            for candidate in candidates:
                candidate_creates.append(
                    CandidateCreate(
                        name=candidate.name,
                        title=candidate.title,
                        location=candidate.location,
                        current_company=candidate.current_company,
                        skills=candidate.skills,
                        open_to_work=candidate.open_to_work,
                        profile_url=candidate.profile_url,
                        source=candidate.source,
                    )
                )
            
            # Save candidates to the database
            if candidate_creates:
                await discovery_service.save_candidates(candidate_creates)
            
            logger.info(f"Task {task_id} complete: Found {len(candidate_creates)} candidates")
            return candidate_creates
        except Exception as e:
            logger.error(f"Error in task {task_id}: {str(e)}", exc_info=True)
            raise
    
    # Run in background if requested
    if run_in_background:
        background_tasks.add_task(run_search)
        return []
    
    # Run synchronously
    try:
        return await run_search()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during candidate search: {str(e)}",
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
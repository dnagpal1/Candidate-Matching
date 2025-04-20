from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
import uuid
import logging

from app.models.candidate import Candidate, CandidateCreate
from app.services.discovery_service import DiscoveryService
from app.graphs.candidate_discovery.graph import run_discovery_graph
from app.graphs.candidate_discovery.schema import SearchParameters

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
    # Create a unique ID for this search task
    task_id = f"search_{uuid.uuid4().hex[:8]}"
    
    # Define the search function
    async def run_search():
        logger.info(f"Running candidate discovery for task {task_id}")
        try:
            # Run the discovery graph
            candidates = await run_discovery_graph(
                job_title=title,
                location=location,
                company=company,
                skills=skills,
                max_results=max_results,
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
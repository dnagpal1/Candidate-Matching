from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.models.candidate import Candidate
from app.services.discovery_service import DiscoveryService, LinkedInSearchParams

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
    search_params = LinkedInSearchParams(
        title=title,
        location=location,
        company=company,
        skills=skills,
        max_results=max_results,
    )
    
    if run_in_background:
        background_tasks.add_task(
            discovery_service.search_linkedin_background,
            search_params,
        )
        return []
    
    try:
        return await discovery_service.search_linkedin(search_params)
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
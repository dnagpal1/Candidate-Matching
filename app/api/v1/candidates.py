from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.candidate import (Candidate, CandidateCreate, CandidateSearchParams,
                                 CandidateUpdate)
from app.services.candidate_service import CandidateService

router = APIRouter()


@router.post("/", response_model=Candidate, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    candidate: CandidateCreate,
    candidate_service: CandidateService = Depends(),
):
    """
    Create a new candidate record.
    """
    return await candidate_service.create_candidate(candidate)


@router.get("/", response_model=List[Candidate])
async def list_candidates(
    title: Optional[str] = Query(None, description="Filter by job title"),
    location: Optional[str] = Query(None, description="Filter by location"),
    company: Optional[str] = Query(None, description="Filter by current company"),
    skills: Optional[List[str]] = Query(None, description="Filter by skills"),
    is_open_to_work: Optional[bool] = Query(None, description="Filter by open to work status"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    candidate_service: CandidateService = Depends(),
):
    """
    List candidates with optional filtering.
    """
    search_params = CandidateSearchParams(
        title=title,
        location=location,
        company=company,
        skills=skills,
        is_open_to_work=is_open_to_work,
        limit=limit,
        offset=offset,
    )
    return await candidate_service.list_candidates(search_params)


@router.get("/{candidate_id}", response_model=Candidate)
async def get_candidate(
    candidate_id: UUID,
    candidate_service: CandidateService = Depends(),
):
    """
    Get a candidate by ID.
    """
    candidate = await candidate_service.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    return candidate


@router.patch("/{candidate_id}", response_model=Candidate)
async def update_candidate(
    candidate_id: UUID,
    candidate_update: CandidateUpdate,
    candidate_service: CandidateService = Depends(),
):
    """
    Update a candidate by ID.
    """
    candidate = await candidate_service.update_candidate(candidate_id, candidate_update)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    return candidate


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: UUID,
    candidate_service: CandidateService = Depends(),
):
    """
    Delete a candidate by ID.
    """
    success = await candidate_service.delete_candidate(candidate_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    return None 
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class CandidateBase(BaseModel):
    """Base model for candidate data."""
    name: str
    title: Optional[str] = None
    location: Optional[str] = None
    current_company: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    open_to_work: bool = False
    profile_url: Optional[HttpUrl] = None
    source: str = "linkedin"  # Source platform where the profile was found (linkedin, wellfound, github)


class CandidateCreate(CandidateBase):
    """Model for creating a new candidate."""
    pass


class CandidateUpdate(BaseModel):
    """Model for updating an existing candidate."""
    name: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    current_company: Optional[str] = None
    skills: Optional[List[str]] = None
    open_to_work: Optional[bool] = None
    profile_url: Optional[HttpUrl] = None
    source: Optional[str] = None


class CandidateInDB(CandidateBase):
    """Model for candidate data stored in the database."""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class Candidate(CandidateInDB):
    """Complete candidate model for API responses."""
    pass


class CandidateSearchParams(BaseModel):
    """Parameters for searching candidates."""
    title: Optional[str] = None
    location: Optional[str] = None
    company: Optional[str] = None
    skills: Optional[List[str]] = None
    is_open_to_work: Optional[bool] = None
    source: Optional[str] = None  # Filter by source platform
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0) 
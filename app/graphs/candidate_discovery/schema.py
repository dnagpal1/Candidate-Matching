from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from datetime import datetime


class SearchParameters(BaseModel):
    """Parameters for searching candidates on LinkedIn."""
    job_title: str
    location: str
    company: Optional[str] = None
    skills: Optional[List[str]] = None
    max_results: int = Field(default=20, ge=1, le=100)


class ProfileData(BaseModel):
    """Raw profile data extracted from LinkedIn."""
    name: str
    job_title: Optional[str] = None
    location: Optional[str] = None
    headline: Optional[str] = None
    current_company: Optional[str] = None
    about: Optional[str] = None
    experience: Optional[str] = None
    education: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    profile_url: Optional[str] = None

class Profiles(BaseModel):
    """Profiles extracted from LinkedIn."""
    profiles: List[ProfileData] = Field(default_factory=list)

class CandidateProfile(BaseModel):
    """Validated candidate profile."""
    name: str
    title: Optional[str] = None
    location: Optional[str] = None
    current_company: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    open_to_work: Optional[bool] = None
    profile_url: Optional[str] = None
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.now)
    matched_skills: List[str] = Field(default_factory=list)
    match_score: float = 1.0
    match_reasons: List[str] = Field(default_factory=list)


class DiscoveryState(BaseModel):
    """State maintained for LinkedIn candidate discovery."""
    # Input parameters
    search_params: SearchParameters
    
    # Output data
    raw_profiles: Profiles = Field(default_factory=Profiles)
    valid_candidates: List[CandidateProfile] = Field(default_factory=list)
    
    # Status tracking
    status: Literal["initialized", "searching", "completed", "error"] = "initialized"
    error_message: Optional[str] = None
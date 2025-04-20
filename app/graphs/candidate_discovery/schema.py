from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl
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
    title: Optional[str] = None
    location: Optional[str] = None
    current_company: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    open_to_work: Optional[bool] = None
    profile_url: Optional[str] = None
    html_content: Optional[str] = None


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


class DiscoveryState(BaseModel):
    """State maintained across the discovery graph execution."""
    # Input parameters
    search_params: SearchParameters
    
    # Processing state
    current_page: int = 1
    has_more_pages: bool = True
    current_profile_index: int = 0
    search_url: Optional[str] = None
    browser_initialized: bool = False
    
    # Output data
    raw_profiles: List[ProfileData] = Field(default_factory=list)
    valid_candidates: List[CandidateProfile] = Field(default_factory=list)
    invalid_candidates: List[ProfileData] = Field(default_factory=list)
    
    # Status tracking
    status: Literal["initialized", "searching", "extracting", "validating", "complete", "error"] = "initialized"
    error_message: Optional[str] = None


class NextAction(BaseModel):
    """Next action to take in the graph."""
    action: Literal["initialize", "search", "extract", "validate", "complete", "error"]
    message: Optional[str] = None
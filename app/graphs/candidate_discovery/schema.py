from typing import Dict, List, Optional, Literal, Set
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from datetime import datetime


class SearchParameters(BaseModel):
    """Parameters for searching candidates on LinkedIn."""
    job_title: str = Field(..., description="The job title to search for")
    location: str = Field(..., description="The location to search in")
    company: Optional[str] = Field(None, description="The company to search in")
    skills: Optional[List[str]] = Field(None, description="The skills to search for")
    max_results: int = Field(default=20, ge=1, le=100, description="The maximum number of results to return")

class UserQuery(BaseModel):
    """The user's query."""
    query: str = Field(..., description="The query to search for")


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
    source: str = "linkedin"  # Source platform where the profile was found

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
    source: str = "linkedin"  # Source platform where the profile was found

class ActionPlan(BaseModel):
    """Plan for which websites to search and in what order."""
    websites: List[str] = Field(default_factory=list)
    priority: Dict[str, int] = Field(default_factory=dict)
    reasoning: str = ""


class DiscoveryState(BaseModel):
    """State maintained for candidate discovery."""

    # User query
    query_string: Optional[str] = None
    
    # Search parameters
    search_params: Optional[SearchParameters] = None
    
    # Action plan
    action_plan: Optional[ActionPlan] = None
    
    # Output data
    raw_profiles: Profiles = Field(default_factory=Profiles)
    valid_candidates: List[CandidateProfile] = Field(default_factory=list)
    
    # Tracking information
    websites_searched: Set[str] = Field(default_factory=set)
    websites_to_search: List[str] = Field(default_factory=list)
    current_website: Optional[str] = None
    min_required_profiles: int = 5
    
    # Status tracking
    status: Literal["initialized", "planning", "searching", "validating", "completed", "error"] = "initialized"
    error_message: Optional[str] = None
    
    # For conditional routing
    should_search_more: bool = True
    has_enough_profiles: bool = False
import asyncio
import logging
from typing import List, Optional

from agents import Agent, function_tool, RunContextWrapper, Runner
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.models.candidate import CandidateCreate
from app.tools.linkedin import search_linkedin_candidates
from app.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# -------------------------------
# CONTEXT
# -------------------------------

class CandidateDiscoveryContext(BaseModel):
    job_title: str
    location: str
    company: Optional[str] = None
    skills: Optional[List[str]] = None
    max_profiles: int = Field(default=20, ge=1, le=100)
    profiles_extracted: int = 0
    discovered_candidates: List[CandidateCreate] = []

# -------------------------------
# RESPONSE SCHEMA
# -------------------------------

# Define a simplified schema that's compatible with OpenAI's response format requirements
class CandidateOutput(BaseModel):
    name: str
    title: Optional[str] = None
    location: Optional[str] = None
    current_company: Optional[str] = None
    skills: Optional[List[str]] = None
    open_to_work: Optional[bool] = None
    profile_url: Optional[str] = None

class CandidateList(BaseModel):
    candidates: List[CandidateOutput]

# -------------------------------
# TOOLS
# -------------------------------

@function_tool
async def search_candidates_tool(context: RunContextWrapper[CandidateDiscoveryContext]) -> str:
    """
    Search for candidates on LinkedIn based on the context parameters.
    
    Returns:
        A message indicating the number of candidates found.
    """
    # Use the existing search_linkedin_candidates function
    candidates = await search_linkedin_candidates(
        job_title=context.context.job_title,
        location=context.context.location,
        company=context.context.company,
        skills=context.context.skills,
        max_profiles=context.context.max_profiles
    )
    
    # Update context with the discovered candidates
    context.context.discovered_candidates.extend(candidates)
    context.context.profiles_extracted = len(candidates)
    
    return f"Found {len(candidates)} candidates matching your criteria."

# -------------------------------
# AGENT
# -------------------------------

candidate_discovery_agent = Agent[CandidateDiscoveryContext](
    name="Candidate Discovery Agent",
    handoff_description="An agent that discovers candidate profiles on LinkedIn.",
    instructions="""
    You are a candidate discovery agent. Use the search_candidates_tool to find candidates on LinkedIn
    based on the job title, location, company, and skills provided in the context.
    
    After searching, return the number of candidates found and their basic information.
    """,
    tools=[search_candidates_tool],
    output_type=CandidateList,
)

# -------------------------------
# RUN
# -------------------------------

async def main():
    """Example runner for the candidate discovery agent."""
    context = CandidateDiscoveryContext(
        job_title="Software Engineer",
        location="San Francisco",
        max_profiles=20
    )
    input_items = [{"role": "user", "content": "Find software engineers in San Francisco"}]
    result = await Runner.run(candidate_discovery_agent, input_items, context=context)
    
    for item in result.new_items:
        if hasattr(item, 'content'):
            print(f"Agent: {item.content}")
    
    print(f"Discovered {len(context.discovered_candidates)} candidates.")
    
    # Convert CandidateCreate to CandidateOutput for the return value
    output_candidates = []
    for candidate in context.discovered_candidates:
        output_candidates.append(
            CandidateOutput(
                name=candidate.name,
                title=candidate.title,
                location=candidate.location,
                current_company=candidate.current_company,
                skills=candidate.skills,
                open_to_work=candidate.open_to_work,
                profile_url=str(candidate.profile_url) if candidate.profile_url else None
            )
        )
    
    # Return the output as CandidateList
    return CandidateList(candidates=output_candidates)

if __name__ == "__main__":
    asyncio.run(main())

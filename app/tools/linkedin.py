import logging
import re
from typing import List, Optional
import json

from browser_use import Agent, Browser
from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.models.candidate import CandidateCreate

logger = logging.getLogger(__name__)

# Constants
LINKEDIN_URL = "https://www.linkedin.com"
LINKEDIN_SEARCH_URL = f"{LINKEDIN_URL}/search/results/people/"
LOGIN_URL = f"{LINKEDIN_URL}/login"
SEARCH_PAGE_SIZE = 10  # LinkedIn typically shows 10 results per page

 
async def search_linkedin_candidates(
    job_title: str,
    location: str,
    company: Optional[str] = None,
    skills: Optional[List[str]] = None,
    max_profiles: int = 20,
) -> List[CandidateCreate]:
    """
    Search for candidates on LinkedIn with the given parameters.
    This is a synchronous operation that will block until complete.
    
    Args:
        job_title: The job title to search for
        location: The location to search in
        company: Optional company name filter
        skills: Optional list of skills to filter by
        max_profiles: Maximum number of profiles to extract
            
    Returns:
        List of CandidateCreate objects representing discovered candidates
    """
    logger.info(f"Searching LinkedIn for {job_title} in {location}")
    
    try:
        # Configure browser options
        browser_options = {}
        if settings.browser_headless:
            browser_options["headless"] = settings.browser_headless
        if settings.browser_proxy_url:
            browser_options["proxy"] = settings.browser_proxy_url
        
        # Build the agent's task
        task = f"""
        Navigate to LinkedIn and search for candidates based on the following parameters:
        Job Title: {job_title}
        Location: {location}
        Company: {company if company else "Any company"}
        Skills: {skills if skills else "Any skills"}
        Maximum results: {max_profiles}
        
        Search using the "People" tab on LinkedIn and extract information from the first {max_profiles} results.
        For each candidate you find, extract the following information:
        - Name
        - Title/Role
        - Location
        - Current company (if available)
        - Whether they're "Open to Work" (if indicated)
        - Profile URL
        - Skills (from their profile or inferred from their title)
        
        For skills, try to match any of these if present: {skills if skills else ""}
        
        Return the results as a valid JSON array with each candidate having these fields:
        - name (string)
        - title (string)
        - location (string)
        - current_company (string or null)
        - open_to_work (boolean)
        - profile_url (string)
        - skills (array of strings)
        
        Example output format:
        [
            {{
                "name": "Jane Smith",
                "title": "Software Engineer",
                "location": "San Francisco, CA",
                "current_company": "Google",
                "open_to_work": false,
                "profile_url": "https://www.linkedin.com/in/janesmith/",
                "skills": ["Python", "JavaScript", "React"]
            }},
            // more candidates...
        ]
        """
        
        # Create and run the agent
        browser = Browser(**browser_options)
        agent = Agent(
            task=task,
            llm=ChatOpenAI(model=settings.openai_model),
            browser=browser,
        )
        # Await the run method since it's a coroutine
        result = await agent.run()
        
        # Parse the results to CandidateCreate objects
        candidates = []
        if result:
            # Extract JSON array from the results - handle potential text before/after JSON
            json_text = result
            # Try to extract JSON if there's additional text
            matches = re.search(r'\[\s*\{.*\}\s*\]', json_text, re.DOTALL)
            if matches:
                json_text = matches.group(0)
            
            try:
                candidate_data = json.loads(json_text)
                for data in candidate_data:
                    # Convert to CandidateCreate model
                    candidate = CandidateCreate(
                        name=data.get("name", "Unknown"),
                        title=data.get("title"),
                        location=data.get("location"),
                        current_company=data.get("current_company"),
                        open_to_work=data.get("open_to_work", False),
                        profile_url=data.get("profile_url"),
                        skills=data.get("skills", [])
                    )
                    candidates.append(candidate)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse candidate data: {e}")
                logger.error(f"Raw result: {result}")
        
        logger.info(f"Found {len(candidates)} candidates on LinkedIn")
        return candidates
    except Exception as e:
        logger.error(f"Error searching LinkedIn: {e}")
        raise e
    

    
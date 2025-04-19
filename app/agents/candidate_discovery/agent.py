import asyncio
import logging
from typing import List, Optional

from browser_use import Browser
from playwright.async_api import Page

from app.config.settings import settings
from app.models.candidate import CandidateCreate
from app.tools.linkedin import (extract_candidate_profiles, paginate_and_scroll,
                              search_linkedin_candidates)
from app.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class CandidateDiscoveryAgent:
    """
    Agent responsible for discovering candidate profiles on LinkedIn.
    Follows the Single-Agent Loop Pattern as specified in the PRD.
    """
    
    def __init__(self):
        """Initialize the agent with configured tools."""
        self.browser_use = None
        self.rate_limiter = RateLimiter(
            max_operations=settings.max_profiles_per_day,
            operation_type="profile_extraction",
        )
    
    async def discover_candidates(
        self,
        job_title: str,
        location: str,
        company: Optional[str] = None,
        skills: Optional[List[str]] = None,
        max_profiles: int = 20,
    ) -> List[CandidateCreate]:
        """
        Main agent loop for discovering candidates on LinkedIn.
        
        Args:
            job_title: The job title to search for
            location: The location to search in
            company: Optional company name filter
            skills: Optional list of skills to filter by
            max_profiles: Maximum number of profiles to extract
            
        Returns:
            List of CandidateCreate objects representing discovered candidates
        """
        logger.info(f"Starting candidate discovery for {job_title} in {location}")
        
        # Initialize browser session
        try:
            await self._initialize_browser()
            page = self.browser_use.page
            
            # Apply search filters and navigate to results page
            await search_linkedin_candidates(
                page=page,
                job_title=job_title,
                location=location,
                company=company,
            )
            
            # Extract candidate profiles
            discovered_candidates = []
            page_number = 1
            profiles_extracted = 0
            
            # Loop through result pages until we reach max_profiles or run out of results
            while profiles_extracted < max_profiles:
                # Check rate limits before proceeding
                await self.rate_limiter.check_rate_limit()
                
                logger.info(f"Processing page {page_number} of LinkedIn search results")
                
                # Extract profiles from current page
                profiles_on_page = await extract_candidate_profiles(
                    page=page,
                    skills_to_match=skills,
                )
                
                # Add new profiles to our results
                for profile in profiles_on_page:
                    if profiles_extracted >= max_profiles:
                        break
                    
                    discovered_candidates.append(profile)
                    profiles_extracted += 1
                    
                    # Log progress
                    logger.debug(
                        f"Extracted profile {profiles_extracted}/{max_profiles}: {profile.name}"
                    )
                    
                    # Apply rate limiting delay between extractions
                    await asyncio.sleep(settings.rate_limit_delay_seconds)
                
                # Break if we've reached max profiles
                if profiles_extracted >= max_profiles:
                    break
                
                # Try to paginate to next page
                has_next_page = await paginate_and_scroll(page=page)
                if not has_next_page:
                    logger.info("No more results pages available")
                    break
                
                page_number += 1
            
            logger.info(f"Candidate discovery complete. Found {len(discovered_candidates)} profiles")
            return discovered_candidates
            
        except Exception as e:
            logger.error(f"Error during candidate discovery: {str(e)}", exc_info=True)
            raise
        finally:
            # Always ensure browser is closed
            await self._cleanup_browser()
    
    async def _initialize_browser(self) -> None:
        """Initialize Browser and set up the browser session."""
        if self.browser_use:
            # Already initialized
            return
        
        logger.info("Initializing browser session")
        self.browser_use = Browser()
        
        # Configure browser options
        await self.browser_use.create_browser(
            headless=settings.browser_headless,
            proxy=settings.browser_proxy_url,
            user_agent=settings.user_agent,
        )
        
        # Create a new page
        await self.browser_use.create_page()
        
        # Handle LinkedIn login if required (login detection handled by the tools)
        if settings.linkedin_email and settings.linkedin_password:
            logger.info("LinkedIn credentials found, will attempt login if needed")
    
    async def _cleanup_browser(self) -> None:
        """Clean up browser resources."""
        if self.browser_use:
            logger.info("Closing browser session")
            await self.browser_use.close_browser()
            self.browser_use = None 
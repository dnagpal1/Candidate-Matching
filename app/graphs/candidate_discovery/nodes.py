import json
import logging
import re
from typing import Dict, List, Optional, Tuple
import asyncio
from browser_use import Agent, Browser
from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.graphs.candidate_discovery.schema import (
    DiscoveryState,
    NextAction,
    ProfileData,
    CandidateProfile,
)
from app.models.candidate import CandidateCreate

logger = logging.getLogger(__name__)

# Constants
LINKEDIN_URL = "https://www.linkedin.com"
LINKEDIN_SEARCH_URL = f"{LINKEDIN_URL}/search/results/people/"
LOGIN_URL = f"{LINKEDIN_URL}/login"

 
async def search_linkedin_candidates(
    state: DiscoveryState
):
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
    logger.info(f"Searching LinkedIn for {state.search_params.job_title} in {state.search_params.location}")

    search_params = state.search_params
    
    try:
        # Configure browser options
        browser_options = {}
        if settings.browser_headless:
            browser_options["headless"] = settings.browser_headless
        if settings.browser_proxy_url:
            browser_options["proxy"] = settings.browser_proxy_url
        
        # Build the agent's task
        task = f"""
        Navigate to LinkedIn and login with the following credentials:
        Email: {settings.linkedin_email}
        Password: {settings.linkedin_password}
        
        search for candidates based on the following parameters:
        Job Title: {search_params.job_title}
        Location: {search_params.location}
        Company: {search_params.company if search_params.company else "Any company"}
        Skills: {search_params.skills if search_params.skills else "Any skills"}
        Maximum results: {search_params.max_results}
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
                    candidate = ProfileData(
                        name=data.get("name", "Unknown"),
                        title=data.get("title"),
                        location=data.get("location"),
                        current_company=data.get("current_company"),
                        open_to_work=data.get("open_to_work", False),
                        profile_url=data.get("profile_url"),
                        skills=data.get("skills", []),
                        html_content=data.get("html_content")
                    )
                    candidates.append(candidate)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse candidate data: {e}")
                logger.error(f"Raw result: {result}")
        
        logger.info(f"Found {len(candidates)} candidates on LinkedIn")
        state.raw_profiles = candidates
    except Exception as e:
        logger.error(f"Error searching LinkedIn: {e}")
        raise e
    
async def start_search_node(state: DiscoveryState) -> DiscoveryState:
    """
    Initialize browser session and construct search URL.
    
    Parameters:
        state: Current state of discovery process
        
    Returns:
        Updated state with browser initialized and search URL constructed
    """
    try:
        logger.info(f"Starting search for {state.search_params.job_title} in {state.search_params.location}")
        
        # Construct search URL with filters
        search_url = LINKEDIN_SEARCH_URL
        
        # Add keyword (job title)
        keywords = state.search_params.job_title.replace(" ", "%20")
        search_url += f"?keywords={keywords}"
        
        # Add location filter
        location_param = state.search_params.location.replace(" ", "%20")
        search_url += f"&location={location_param}"
        
        # Add company filter if provided
        if state.search_params.company:
            company_param = state.search_params.company.replace(" ", "%20")
            search_url += f"&currentCompany={company_param}"
        
        # Update state
        state.search_url = search_url
        state.status = "searching"
        state.browser_initialized = True
        
        return state
    except Exception as e:
        logger.error(f"Error in start_search_node: {str(e)}", exc_info=True)
        state.status = "error"
        state.error_message = f"Failed to initialize search: {str(e)}"
        return state


async def browser_scraper_node(state: DiscoveryState) -> DiscoveryState:
    """
    Navigate to LinkedIn search page and extract profile links.
    
    Parameters:
        state: Current state of discovery process
        
    Returns:
        Updated state with raw profile data
    """
    try:
        # Don't proceed if we've reached max results or no more pages
        if (
            len(state.raw_profiles) >= state.search_params.max_results
            or not state.has_more_pages
        ):
            state.status = "extracting"
            return state
        
        logger.info(f"Scraping LinkedIn search page {state.current_page}")
        
        # Configure browser options
        browser_options = {}
        if settings.browser_headless:
            browser_options["headless"] = settings.browser_headless
        if settings.browser_proxy_url:
            browser_options["proxy"] = settings.browser_proxy_url
        
        # Create browser instance and navigate to search URL
        browser = Browser(**browser_options)
        browser_page = await browser.new_page()
        
        # First navigate to LinkedIn homepage to check if login is required
        await browser_page.goto(LINKEDIN_URL)
        
        # Check if login is required
        login_button = await browser_page.query_selector("a[href*='/login']")
        login_form = await browser_page.query_selector("form#login-form")
        
        if login_button or login_form:
            logger.info("Login required, attempting LinkedIn login")
            await browser_page.goto(LOGIN_URL)
            await browser_page.fill("input#username", settings.linkedin_email)
            await browser_page.fill("input#password", settings.linkedin_password)
            await browser_page.click("button[type='submit']")
            await browser_page.wait_for_load_state("networkidle")
        
        # Navigate to search URL with appropriate page number
        page_url = state.search_url
        if state.current_page > 1:
            page_url += f"&page={state.current_page}"
        
        logger.info(f"Navigating to: {page_url}")
        await browser_page.goto(page_url)
        await browser_page.wait_for_selector(".search-results-container", timeout=30000)
        
        # Get profile cards
        profile_cards = await browser_page.query_selector_all(".reusable-search__result-container")
        
        # Process each profile card
        for card in profile_cards:
            if len(state.raw_profiles) >= state.search_params.max_results:
                break
                
            try:
                # Extract basic information from the card
                name_element = await card.query_selector(".entity-result__title-text a")
                if not name_element:
                    continue
                    
                # Extract name
                name_text = await name_element.inner_text()
                name = name_text.strip().split("\n")[0].strip()
                
                # Extract profile URL
                profile_url = await name_element.get_attribute("href")
                if profile_url:
                    # Clean up URL by removing query parameters
                    profile_url = profile_url.split("?")[0]
                
                # Extract title/headline
                title_element = await card.query_selector(".entity-result__primary-subtitle")
                title = await title_element.inner_text() if title_element else None
                
                # Extract location
                location_element = await card.query_selector(".entity-result__secondary-subtitle")
                location = await location_element.inner_text() if location_element else None
                
                # Extract current company (part of the title in most cases)
                company = None
                if title:
                    # Company is often in format "Title at Company"
                    title_parts = title.split(" at ", 1)
                    if len(title_parts) > 1:
                        actual_title = title_parts[0].strip()
                        company = title_parts[1].strip()
                        title = actual_title
                
                # Check for "Open to work" badge
                open_to_work = False
                open_badge = await card.query_selector(".image-badge-recruiter-entity-lockup__badge")
                if open_badge:
                    open_to_work = True
                
                # Create profile data object
                profile_data = ProfileData(
                    name=name,
                    title=title,
                    location=location,
                    current_company=company,
                    skills=[],  # Will be extracted in the profile extractor node
                    open_to_work=open_to_work,
                    profile_url=profile_url,
                )
                
                state.raw_profiles.append(profile_data)
                
            except Exception as e:
                logger.error(f"Error extracting profile card: {str(e)}", exc_info=True)
        
        # Check if there's a next page
        next_button = await browser_page.query_selector("button.artdeco-pagination__button--next")
        if not next_button:
            state.has_more_pages = False
            logger.info("No next button found, reached the last page")
        else:
            # Check if the button is disabled
            is_disabled = await next_button.get_attribute("disabled")
            if is_disabled:
                state.has_more_pages = False
                logger.info("Next button is disabled, reached the last page")
            else:
                state.current_page += 1
        
        # Close browser
        await browser.close()
        
        # Update state
        logger.info(f"Found {len(state.raw_profiles)} raw profiles so far")
        
        # Move to next phase if we have enough profiles or no more pages
        if len(state.raw_profiles) >= state.search_params.max_results or not state.has_more_pages:
            state.status = "extracting"
        
        return state
    except Exception as e:
        logger.error(f"Error in browser_scraper_node: {str(e)}", exc_info=True)
        state.status = "error"
        state.error_message = f"Failed to scrape profiles: {str(e)}"
        return state


async def profile_extractor_node(state: DiscoveryState) -> DiscoveryState:
    """
    Extract detailed information from each profile.
    
    Parameters:
        state: Current state of discovery process
        
    Returns:
        Updated state with extracted profile data
    """
    try:
        # Don't proceed if we're already done or there are no profiles
        if not state.raw_profiles or state.current_profile_index >= len(state.raw_profiles):
            state.status = "validating"
            return state
            
        logger.info(f"Extracting detailed information for profiles")
        
        # Configure browser options
        browser_options = {}
        if settings.browser_headless:
            browser_options["headless"] = settings.browser_headless
        if settings.browser_proxy_url:
            browser_options["proxy"] = settings.browser_proxy_url
            
        # Create browser instance
        browser = Browser(**browser_options)
        browser_page = await browser.new_page()
        
        # Process batch of profiles (up to 5 at a time to avoid rate limiting)
        batch_size = 5
        batch_start = state.current_profile_index
        batch_end = min(batch_start + batch_size, len(state.raw_profiles))
        
        for i in range(batch_start, batch_end):
            profile = state.raw_profiles[i]
            
            # Skip if no profile URL
            if not profile.profile_url:
                continue
                
            try:
                # Visit profile page
                await browser_page.goto(profile.profile_url, wait_until="networkidle")
                
                # Extract skills section if available
                skills_section = await browser_page.query_selector("section.skills-section")
                skills = []
                
                if skills_section:
                    skill_elements = await skills_section.query_selector_all("span.skill-name")
                    for skill_el in skill_elements:
                        skill_text = await skill_el.inner_text()
                        if skill_text:
                            skills.append(skill_text.strip())
                
                # If skills section not found or empty, try to extract from about section or experience
                if not skills and state.search_params.skills:
                    page_text = await browser_page.inner_text("body")
                    
                    # Check for each skill in the page text
                    for skill in state.search_params.skills:
                        if skill.lower() in page_text.lower():
                            skills.append(skill)
                
                # Update profile with skills
                state.raw_profiles[i].skills = skills
                
                # Delay to avoid rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error extracting profile details: {str(e)}", exc_info=True)
        
        # Update current profile index
        state.current_profile_index = batch_end
        
        # Close browser
        await browser.close()
        
        # Move to next phase if we've processed all profiles
        if state.current_profile_index >= len(state.raw_profiles):
            state.status = "validating"
        
        return state
    except Exception as e:
        logger.error(f"Error in profile_extractor_node: {str(e)}", exc_info=True)
        state.status = "error"
        state.error_message = f"Failed to extract profile details: {str(e)}"
        return state


async def guardrail_validator_node(state: DiscoveryState) -> DiscoveryState:
    """
    Validate profiles against schema requirements.
    
    Parameters:
        state: Current state of discovery process
        
    Returns:
        Updated state with validated candidate profiles
    """
    try:
        logger.info(f"Validating {len(state.raw_profiles)} profiles")
        
        for profile in state.raw_profiles:
            # Validate required fields
            if not profile.name:
                state.invalid_candidates.append(profile)
                continue
                
            # Create validated candidate profile
            candidate = CandidateProfile(
                name=profile.name,
                title=profile.title,
                location=profile.location,
                current_company=profile.current_company,
                skills=profile.skills,
                open_to_work=profile.open_to_work,
                profile_url=profile.profile_url,
            )
            
            # Apply additional filters based on search parameters
            if state.search_params.skills and not any(
                skill in profile.skills for skill in state.search_params.skills
            ):
                # No matching skills found, mark as invalid
                state.invalid_candidates.append(profile)
            else:
                state.valid_candidates.append(candidate)
        
        # Update state
        logger.info(f"Validated {len(state.valid_candidates)} profiles, {len(state.invalid_candidates)} failed validation")
        state.status = "complete"
        
        return state
    except Exception as e:
        logger.error(f"Error in guardrail_validator_node: {str(e)}", exc_info=True)
        state.status = "error"
        state.error_message = f"Failed to validate profiles: {str(e)}"
        return state


async def decide_next_action(state: DiscoveryState) -> NextAction:
    """
    Decide the next action based on the current state.
    
    Parameters:
        state: Current state of discovery process
        
    Returns:
        Next action to take
    """
    # Handle error states
    if state.status == "error":
        return NextAction(action="error", message=state.error_message)
    
    # Handle initial state
    if state.status == "initialized":
        return NextAction(action="initialize")
    
    # Handle searching state
    if state.status == "searching":
        # Check if we've found enough profiles
        if len(state.raw_profiles) >= state.search_params.max_results:
            return NextAction(action="extract")
        # Check if there are more pages to process
        if state.has_more_pages:
            return NextAction(action="search")
        # No more pages, move to extraction
        return NextAction(action="extract")
    
    # Handle extracting state
    if state.status == "extracting":
        # Check if we've processed all profiles
        if state.current_profile_index >= len(state.raw_profiles):
            return NextAction(action="validate")
        # Continue extracting
        return NextAction(action="extract")
    
    # Handle validating state
    if state.status == "validating":
        return NextAction(action="validate")
    
    # Handle complete state
    if state.status == "complete":
        return NextAction(action="complete")
    
    # Default to error if we don't know what to do
    return NextAction(
        action="error",
        message=f"Unknown state: {state.status}",
    )
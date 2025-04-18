import logging
import re
from typing import List, Optional

from playwright.async_api import Page, TimeoutError

from app.config.settings import settings
from app.models.candidate import CandidateCreate

logger = logging.getLogger(__name__)

# Constants
LINKEDIN_URL = "https://www.linkedin.com"
LINKEDIN_SEARCH_URL = f"{LINKEDIN_URL}/search/results/people/"
LOGIN_URL = f"{LINKEDIN_URL}/login"
SEARCH_PAGE_SIZE = 10  # LinkedIn typically shows 10 results per page


async def search_linkedin_candidates(
    page: Page, 
    job_title: str, 
    location: str,
    company: Optional[str] = None,
) -> None:
    """
    Navigate to LinkedIn and search for candidates with the given criteria.
    
    Args:
        page: Playwright page object
        job_title: Job title to search for
        location: Location to search in
        company: Optional company name filter
    """
    logger.info(f"Searching LinkedIn for {job_title} in {location}")
    
    # Navigate to LinkedIn
    await page.goto(LINKEDIN_URL)
    
    # Check if login is required
    if await _is_login_required(page):
        await _perform_login(page)
    
    # Construct search URL with filters
    search_url = LINKEDIN_SEARCH_URL
    
    # Add keyword (job title)
    keywords = job_title.replace(" ", "%20")
    search_url += f"?keywords={keywords}"
    
    # Add location filter
    location_param = location.replace(" ", "%20")
    search_url += f"&location={location_param}"
    
    # Add company filter if provided
    if company:
        company_param = company.replace(" ", "%20")
        search_url += f"&currentCompany={company_param}"
    
    # Navigate to search results
    logger.info(f"Navigating to search URL: {search_url}")
    await page.goto(search_url)
    
    # Wait for search results to load
    await page.wait_for_selector(".search-results-container", timeout=30000)
    
    # Small delay to ensure results are fully loaded
    await page.wait_for_timeout(2000)
    
    logger.info("Search completed, results page loaded")


async def extract_candidate_profiles(
    page: Page, 
    skills_to_match: Optional[List[str]] = None,
) -> List[CandidateCreate]:
    """
    Extract candidate information from the current search results page.
    
    Args:
        page: Playwright page object
        skills_to_match: Optional list of skills to filter by
        
    Returns:
        List of CandidateCreate objects
    """
    logger.info("Extracting candidate profiles from search results")
    
    # Wait for search results to be present
    await page.wait_for_selector(".reusable-search__result-container", timeout=30000)
    
    # Get all profile cards on the page
    profile_cards = await page.query_selector_all(".reusable-search__result-container")
    
    candidates = []
    for card in profile_cards:
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
            
            # Extract or infer skills (from title and description)
            skills = []
            if skills_to_match:
                # Simple skill matching from title and other text
                card_text = await card.inner_text()
                card_text = card_text.lower()
                
                for skill in skills_to_match:
                    if skill.lower() in card_text:
                        skills.append(skill)
            
            # Create candidate object
            candidate = CandidateCreate(
                name=name,
                title=title,
                location=location,
                current_company=company,
                skills=skills,
                open_to_work=open_to_work,
                profile_url=profile_url,
            )
            
            candidates.append(candidate)
            logger.debug(f"Extracted profile: {name}")
            
        except Exception as e:
            logger.error(f"Error extracting profile: {e}", exc_info=True)
    
    logger.info(f"Extracted {len(candidates)} profiles from current page")
    return candidates


async def paginate_and_scroll(page: Page) -> bool:
    """
    Scroll through the current page and navigate to the next page of results if available.
    
    Args:
        page: Playwright page object
        
    Returns:
        Boolean indicating if there is a next page (True) or not (False)
    """
    # Scroll to the bottom of the page
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1000)
    
    # Check if next button exists and is not disabled
    next_button = await page.query_selector("button.artdeco-pagination__button--next")
    if not next_button:
        logger.info("No next button found, reached the last page")
        return False
    
    # Check if the button is disabled
    is_disabled = await next_button.get_attribute("disabled")
    if is_disabled:
        logger.info("Next button is disabled, reached the last page")
        return False
    
    # Click next button
    logger.info("Navigating to next page")
    await next_button.click()
    
    # Wait for next page to load
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
        await page.wait_for_timeout(2000)  # Additional wait to ensure content is loaded
        return True
    except TimeoutError:
        logger.warning("Timeout waiting for next page to load")
        return False


async def _is_login_required(page: Page) -> bool:
    """
    Check if the current page requires login.
    
    Args:
        page: Playwright page object
        
    Returns:
        Boolean indicating if login is required
    """
    # Check for login button or form
    login_button = await page.query_selector("a[href*='/login']")
    login_form = await page.query_selector("form#login-form")
    
    return bool(login_button or login_form)


async def _perform_login(page: Page) -> None:
    """
    Perform LinkedIn login with credentials from settings.
    
    Args:
        page: Playwright page object
    """
    logger.info("Login required, attempting to log in to LinkedIn")
    
    # Navigate to login page if not already there
    current_url = page.url
    if LOGIN_URL not in current_url:
        await page.goto(LOGIN_URL)
    
    # Fill in login form
    await page.fill("input#username", settings.linkedin_email)
    await page.fill("input#password", settings.linkedin_password)
    
    # Submit form
    await page.click("button[type='submit']")
    
    # Wait for navigation to complete
    await page.wait_for_load_state("networkidle")
    
    # Check if login was successful
    if "feed" in page.url or "voyager" in page.url:
        logger.info("LinkedIn login successful")
    else:
        logger.error("LinkedIn login failed, check credentials")
        # Check for specific error messages
        error_msg = await page.inner_text(".alert-content")
        if error_msg:
            logger.error(f"Login error: {error_msg}")
        raise Exception("LinkedIn login failed") 
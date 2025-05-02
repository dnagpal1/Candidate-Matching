import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
import asyncio
from browser_use import Agent, Browser, Controller
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config.settings import settings
from app.graphs.candidate_discovery.schema import (
    DiscoveryState,
    ProfileData,
    CandidateProfile,
    Profiles,
    SearchParameters,
    ActionPlan,
)


logger = logging.getLogger(__name__)

# Constants
LINKEDIN_URL = "https://www.linkedin.com"
LINKEDIN_SEARCH_URL = f"{LINKEDIN_URL}/search/results/people/"
LOGIN_URL = f"{LINKEDIN_URL}/login"
WELLFOUND_URL = "https://wellfound.com"
GITHUB_URL = "https://github.com"


async def parse_intent_node(state: DiscoveryState) -> DiscoveryState:
    """
    Parse the intent of the user's query into a SearchParameters object.
    """
    logger.info(f"Parsing intent of user's query: {state.query_string}")
    
    # Create a prompt for intent parsing
    prompt = f"""
    You are a helpful assistant that parses the intent of a user's query.
    Convert the user's query into structured search parameters for a candidate search.
    
    The user's query is: {state.query_string}
    
    Your task is to extract and return the following information as JSON, ensuring each field is grounded in real and valid LinkedIn-compatible data:

    - **job_title**: The main role being searched for (e.g., "Software Engineer", "Product Manager").
    - **location**: A real geographic location where the candidate is expected to be located. This should match actual LinkedIn city or region names (e.g., "Toronto", "San Francisco Bay Area").
    - **company**: (Optional) If the user specifies a company preference, include the company name (e.g., "Google").
    - **skills**: A list of relevant, real-world skills (e.g., ["Python", "Django", "AWS"]). These should be technical or professional skills, not soft traits.
    - **experience_level**: Use one of the following: "Internship", "Entry Level", "Associate", "Mid-Senior", "Director", or "Executive".
    - **max_results**: A number between 1 and 100 indicating how many profiles to extract (default to 20 if not specified).

    Make sure all values are realistic and coherent with each other. If any value is missing or unclear, set it to `null` or an empty list.
    """

    # Create and run the node
    llm = ChatGoogleGenerativeAI(model=settings.gemini_model, api_key=settings.gemini_api_key)
    structured_llm = llm.with_structured_output(SearchParameters)
    response = await structured_llm.ainvoke(prompt)

    logger.info(f"Parsed search parameters: {response}")

    return {"search_params": response, "status": "planning"}


async def plan_actions_node(state: DiscoveryState) -> DiscoveryState:
    """
    Plan which websites to search based on the search parameters.
    """
    logger.info(f"Planning actions for search parameters: {state.search_params}")
    
    # Create a prompt for planning
    search_params = state.search_params
    prompt = f"""
    You are a strategic agent for candidate discovery. Based on the search parameters, 
    decide which websites to search for candidate profiles and in what order.
    
    Search parameters:
    - Job title: {search_params.job_title}
    - Location: {search_params.location}
    - Company: {search_params.company if search_params.company else 'Not specified'}
    - Skills: {', '.join(search_params.skills) if search_params.skills else 'Not specified'}
    
    Available websites:
    - LinkedIn (professional networking site, strong for most professional roles)
    - Wellfound (startup-focused, good for tech roles in startups)
    
    Decide which websites to search based on the likelihood of finding quality 
    candidates matching the criteria. Prioritize sites based on:
    
    1. Relevance to the job domain
    2. Likelihood of finding qualified candidates
    3. Diversity of candidate pool
    
    Return your plan as a structured object with:
    - A list of websites to search
    - Priority ranking for each website (1=highest)
    - Brief reasoning for your choices
    """
    
    # Create and run the node
    llm = ChatGoogleGenerativeAI(model=settings.gemini_model, api_key=settings.gemini_api_key)
    structured_llm = llm.with_structured_output(ActionPlan)
    action_plan = await structured_llm.ainvoke(prompt)
    
    logger.info(f"Generated action plan: {action_plan}")
    
    # Update the state with the plan
    websites_to_search = action_plan.websites
    
    return {
        "action_plan": action_plan,
        "websites_to_search": websites_to_search,
        "status": "searching"
    }


async def search_candidates_parallel_node(state: DiscoveryState) -> DiscoveryState:
    """
    Search for candidates on multiple websites in parallel.
    """
    if not state.websites_to_search:
        logger.info("No more websites to search")
        return {"status": "validating", "should_search_more": False}
    
    # Take the next website to search
    current_website = state.websites_to_search.pop(0)
    logger.info(f"Searching for candidates on {current_website}")
    
    # Update state to track which website we're searching
    state.current_website = current_website
    state.websites_searched.add(current_website)
    
    # Call the appropriate search function based on the website
    search_params = state.search_params
    try:
        if current_website.lower() == "linkedin":
            profiles = await search_linkedin_candidates_task(search_params)
        elif current_website.lower() == "wellfound":
            profiles = await search_wellfound_candidates_task(search_params)
        elif current_website.lower() == "github":
            profiles = await search_github_candidates_task(search_params)
        else:
            logger.warning(f"Unknown website: {current_website}")
            profiles = Profiles()
        
        # Merge new profiles with existing ones
        for profile in profiles.profiles:
            profile.source = current_website.lower()
            state.raw_profiles.profiles.append(profile)
            
        logger.info(f"Found {len(profiles.profiles)} profiles on {current_website}")
        
        return {
            "raw_profiles": state.raw_profiles,
            "status": "validating"
        }
    except Exception as e:
        logger.error(f"Error searching {current_website}: {str(e)}")
        return {
            "error_message": f"Error searching {current_website}: {str(e)}",
            "status": "validating"  # Continue to validation even if there's an error
        }


async def validate_profiles_node(state: DiscoveryState) -> DiscoveryState:
    """
    Validate and analyze the extracted profiles.
    Determines if we have enough quality profiles or need to search more.
    """
    logger.info(f"Validating {len(state.raw_profiles.profiles)} profiles")
    
    # Extract valid candidates from raw profiles
    valid_candidates = []
    search_params = state.search_params
    
    # Convert raw profiles to candidate profiles
    for profile in state.raw_profiles.profiles:
        # Basic validation - skip profiles without names
        if not profile.name:
            continue
            
        # Create a candidate profile
        candidate = CandidateProfile(
            name=profile.name,
            title=profile.job_title,
            location=profile.location,
            current_company=profile.current_company,
            skills=profile.skills if profile.skills else [],
            profile_url=profile.profile_url,
            source=profile.source
        )
        
        # Calculate match score and reasons
        matched_skills = []
        match_reasons = []
        
        # Match skills if we have them
        if search_params.skills and profile.skills:
            for skill in search_params.skills:
                if any(skill.lower() in s.lower() for s in profile.skills):
                    matched_skills.append(skill)
        
        # Add match reasons
        if matched_skills:
            match_reasons.append(f"Has {len(matched_skills)} of the required skills")
            
        if search_params.location and profile.location and search_params.location.lower() in profile.location.lower():
            match_reasons.append(f"Located in {search_params.location}")
            
        if search_params.company and profile.current_company and search_params.company.lower() in profile.current_company.lower():
            match_reasons.append(f"Works at {search_params.company}")
            
        # Set the match score (simple heuristic - can be improved)
        if matched_skills and search_params.skills:
            match_score = len(matched_skills) / len(search_params.skills)
        else:
            match_score = 0.5  # Default score if we can't calculate
            
        # Update candidate with match information
        candidate.matched_skills = matched_skills
        candidate.match_reasons = match_reasons
        candidate.match_score = match_score
        
        valid_candidates.append(candidate)
    
    # Sort by match score
    valid_candidates.sort(key=lambda c: c.match_score, reverse=True)
    
    # Determine if we need to search more
    has_enough_profiles = len(valid_candidates) >= state.min_required_profiles
    should_search_more = not has_enough_profiles and len(state.websites_to_search) > 0
    
    logger.info(f"Found {len(valid_candidates)} valid candidates, need more: {should_search_more}")
    
    return {
        "valid_candidates": valid_candidates,
        "has_enough_profiles": has_enough_profiles,
        "should_search_more": should_search_more,
        "status": "searching" if should_search_more else "completed"
    }


async def search_linkedin_candidates_task(search_params: SearchParameters) -> Profiles:
    """
    Search for candidates on LinkedIn with the given parameters.
    """
    logger.info(f"Searching LinkedIn for {search_params.job_title} in {search_params.location}")
    
    try:
        controller = Controller(output_model=Profiles)

        task = (f"""
            Navigate to LinkedIn.com and login with the following credentials:
            Email: {settings.linkedin_email}
            Password: {settings.linkedin_password}

            Use LinkedIn to find candidate profiles that match the following criteria:

            1. Go to LinkedIn and use the People Search feature.
            2. Apply the following search filters:
            - Keywords: {search_params.job_title} + {search_params.skills if search_params.skills else ''}
            - Location: {search_params.location}
            - Experience level: All (unless specified otherwise)
            3. Navigate through at least 3 pages of search results.
            4. On each page:
            - Scroll down to ensure all results load.
            - Extract the **profile URLs only** for each candidate card (do not open profiles yet).
            - Store at least 10-15 unique profile links before proceeding.
            """

           f""" Once all profile URLs are collected:
            5. Visit each stored LinkedIn profile one by one (in a new tab or session).
            6. For each profile, extract the following fields:
            - Full name
            - Location
            - Current job title and company
            - Profile headline or summary
            - About section
            - Experience section (with roles and dates)
            - Education section
            - Skills section
            - Recommendations section (received and given)
            - Profile URL

            If any field is missing, return "N/A" instead of skipping the profile.
            After all profiles are scraped, return them as a list of JSON objects.
            """
        )
        
        # Create and run the agent
        browser = Browser()
        agent = Agent(
            task=task,
            llm=ChatGoogleGenerativeAI(model=settings.gemini_model, api_key=settings.gemini_api_key),
            browser=browser,
            controller=controller,
        )
        
        # Await the run method since it's a coroutine
        history = await agent.run()
        result = history.final_result()

        if result:
            parsed = Profiles.model_validate_json(result)
            return parsed
        else:
            logger.error("No profiles found on LinkedIn")
            return Profiles()
    except Exception as e:
        logger.error(f"Error searching LinkedIn: {e}")
        raise e


async def search_wellfound_candidates_task(search_params: SearchParameters) -> Profiles:
    """
    Search for candidates on Wellfound (AngelList Talent) with the given parameters.
    """
    logger.info(f"Searching Wellfound for {search_params.job_title} in {search_params.location}")
    
    try:
        controller = Controller(output_model=Profiles)

        task = (f"""
            Navigate to Wellfound.com (formerly AngelList Talent).
            
            Use Wellfound to find candidate profiles that match the following criteria:

            1. Go to Wellfound and use the People Search feature.
            2. Apply the following search filters:
            - Keywords: {search_params.job_title} + {search_params.skills if search_params.skills else ''}
            - Location: {search_params.location}
            3. Navigate through at least the first page of search results.
            4. On each page:
            - Scroll down to ensure all results load.
            - Extract the **profile URLs only** for each candidate card (do not open profiles yet).
            - Store at least 3 unique profile links before proceeding.
            """

           f""" Once all profile URLs are collected:
            5. Visit each stored profile one by one (in a new tab or session).
            6. For each profile, extract the following fields:
            - Full name
            - Location
            - Current job title and company
            - Profile headline or summary
            - About section
            - Experience section (with roles and dates)
            - Education section
            - Skills section
            - Profile URL

            If any field is missing, return "N/A" instead of skipping the profile.
            After all profiles are scraped, return them as a list of JSON objects.
            """
        )
        
        # Create and run the agent
        browser = Browser()
        agent = Agent(
            task=task,
            llm=ChatGoogleGenerativeAI(model=settings.gemini_model, api_key=settings.gemini_api_key),
            browser=browser,
            controller=controller,
        )
        
        # Await the run method since it's a coroutine
        history = await agent.run()
        result = history.final_result()

        if result:
            parsed = Profiles.model_validate_json(result)
            return parsed
        else:
            logger.error("No profiles found on Wellfound")
            return Profiles()
    except Exception as e:
        logger.error(f"Error searching Wellfound: {e}")
        raise e


async def search_github_candidates_task(search_params: SearchParameters) -> Profiles:
    """
    Search for candidates on GitHub with the given parameters.
    """
    logger.info(f"Searching GitHub for {search_params.job_title} with skills: {search_params.skills}")
    
    try:
        controller = Controller(output_model=Profiles)

        # Construct a GitHub-appropriate search
        skills_query = " ".join(search_params.skills) if search_params.skills else search_params.job_title
        
        task = (f"""
            Navigate to GitHub.com.
            
            Use GitHub to find candidate profiles that match the following criteria:

            1. Go to GitHub and use the People Search feature.
            2. Apply the following search filters:
            - Keywords: {skills_query}
            - Location: {search_params.location} (if available)
            3. Navigate through at least the first page of search results.
            4. On each page:
            - Scroll down to ensure all results load.
            - Extract the **profile URLs only** for each developer (do not open profiles yet).
            - Store at least 3 unique profile links before proceeding.
            """

           f""" Once all profile URLs are collected:
            5. Visit each stored GitHub profile one by one (in a new tab or session).
            6. For each profile, extract the following fields:
            - Full name
            - Location (if available)
            - Bio or summary
            - Repositories and their topics (to extract skills)
            - Contributions graph data
            - Profile URL

            If any field is missing, return "N/A" instead of skipping the profile.
            After all profiles are scraped, return them as a list of JSON objects.
            """
        )
        
        # Create and run the agent
        browser = Browser()
        agent = Agent(
            task=task,
            llm=ChatGoogleGenerativeAI(model=settings.gemini_model, api_key=settings.gemini_api_key),
            browser=browser,
            controller=controller,
        )
        
        # Await the run method since it's a coroutine
        history = await agent.run()
        result = history.final_result()

        if result:
            parsed = Profiles.model_validate_json(result)
            return parsed
        else:
            logger.error("No profiles found on GitHub")
            return Profiles()
    except Exception as e:
        logger.error(f"Error searching GitHub: {e}")
        raise e

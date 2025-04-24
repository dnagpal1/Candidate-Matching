import json
import logging
import re
from typing import Dict, List, Optional, Tuple
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
)


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

        controller = Controller(output_model=Profiles)

        task =( f"""
            Navigate to LinkedIn and login with the following credentials:
            Email: {settings.linkedin_email}
            Password: {settings.linkedin_password}

            Use LinkedIn to find candidate profiles that match the following criteria:

            1. Go to LinkedIn and use the People Search feature.
            2. Apply the following search filters:
            - Keywords: {search_params.job_title} + {search_params.skills}
            - Location: {search_params.location}
            - Experience level: All (unless specified otherwise)
            3. Navigate through at least the first 3 pages of search results.
            4. On each page:
            - Scroll down to ensure all results load.
            - Extract the **profile URLs only** for each candidate card (do not open profiles yet).
            - Store at least 10–15 unique profile links before proceeding.
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
        browser = Browser(
            # config=BrowserConfig(
            #     browser_binary_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            # )
        )
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
            parsed: Profiles = Profiles.model_validate_json(result)

            for profile in parsed.profiles:
                print('\n----------------------------')
                print(f"Name: {profile.name}")
                print(f"Location: {profile.location}")
                print(f"Current job title and company: {profile.current_company}")
                print(f"Profile headline/summary: {profile.headline}")
                print(f"About section: {profile.about}")
                print(f"Experience section: {profile.experience}")
                print(f"Education section: {profile.education}")
                print(f"Skills section: {profile.skills}")
                print(f"Recommendations section: {profile.recommendations}")
                print(f"Profile URL: {profile.profile_url}")

            else:
                logger.error("No profiles found")
                
                
                
        
        # # Parse the results to CandidateCreate objects
        # candidates = []
        # if result:
        #     # Extract JSON array from the results - handle potential text before/after JSON
        #     json_text = result
        #     # Try to extract JSON if there's additional text
        #     matches = re.search(r'\[\s*\{.*\}\s*\]', json_text, re.DOTALL)
        #     if matches:
        #         json_text = matches.group(0)
            
        #     try:
        #         candidate_data = json.loads(json_text)
        #         for data in candidate_data:
        #             # Convert to CandidateCreate model
        #             candidate = ProfileData(
        #                 name=data.get("name", "Unknown"),
        #                 title=data.get("title"),
        #                 location=data.get("location"),
        #                 current_company=data.get("current_company"),
        #                 open_to_work=data.get("open_to_work", False),
        #                 profile_url=data.get("profile_url"),
        #                 skills=data.get("skills", []),
        #                 html_content=data.get("html_content")
        #             )
        #             candidates.append(candidate)
        #     except json.JSONDecodeError as e:
        #         logger.error(f"Failed to parse candidate data: {e}")
        #         logger.error(f"Raw result: {result}")
        
        # logger.info(f"Found {len(candidates)} candidates on LinkedIn")
        # state.raw_profiles = candidates
    except Exception as e:
        logger.error(f"Error searching LinkedIn: {e}")
        raise e



async def parse_intent_node(state: DiscoveryState) -> DiscoveryState:
    """
    Parse the intent of the user's query into a SearchParameters object.
    """
    logger.info(f"Parsing intent of user's query: {state.query_string}")
    
    # Create a prompt for intent parsing
    prompt = f"""
    You are a helpful assistant that parses the intent of a user's query.
    Convert the user's query into structured search parameters for a LinkedIn candidate search.
    
    The user's query is: {state.query_string}
    
    Your task is to extract and return the following information as JSON, ensuring each field is grounded in real and valid LinkedIn-compatible data:

    - **job_title**: The main role being searched for (e.g., "Software Engineer", "Product Manager").
    - **location**: A real geographic location where the candidate is expected to be located or open to work. This should match actual LinkedIn city or region names (e.g., "Toronto", "San Francisco Bay Area").
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

    return {"search_params": response}

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.candidate_discovery.agent import CandidateDiscoveryAgent
from app.models.candidate import CandidateCreate


@pytest.mark.asyncio
async def test_discover_candidates():
    # Mock the browser use and tools
    with patch("app.agents.candidate_discovery.agent.Browser") as mock_browser_use, \
         patch("app.agents.candidate_discovery.agent.search_linkedin_candidates") as mock_search, \
         patch("app.agents.candidate_discovery.agent.extract_candidate_profiles") as mock_extract, \
         patch("app.agents.candidate_discovery.agent.paginate_and_scroll") as mock_paginate, \
         patch("app.agents.candidate_discovery.agent.RateLimiter") as mock_rate_limiter:
        
        # Set up mocks
        mock_browser_instance = AsyncMock()
        mock_browser_instance.page = MagicMock()
        mock_browser_use.return_value = mock_browser_instance
        
        mock_search.return_value = None
        
        # Mock profile extraction to return two candidates
        mock_extract.return_value = [
            CandidateCreate(
                name="John Doe",
                title="Software Engineer",
                location="New York, NY",
                current_company="Tech Corp",
                skills=["Python", "FastAPI"],
                open_to_work=True,
                profile_url="https://linkedin.com/in/johndoe",
            ),
            CandidateCreate(
                name="Jane Smith",
                title="Data Scientist",
                location="San Francisco, CA",
                current_company="Data Inc",
                skills=["Python", "Machine Learning"],
                open_to_work=False,
                profile_url="https://linkedin.com/in/janesmith",
            ),
        ]
        
        # Mock pagination to return False (no more pages)
        mock_paginate.return_value = False
        
        # Mock rate limiter
        mock_rate_limiter_instance = AsyncMock()
        mock_rate_limiter_instance.check_rate_limit.return_value = True
        mock_rate_limiter.return_value = mock_rate_limiter_instance
        
        # Create agent and call discover_candidates
        agent = CandidateDiscoveryAgent()
        results = await agent.discover_candidates(
            job_title="Software Engineer",
            location="New York",
            skills=["Python"],
            max_profiles=5,
        )
        
        # Assertions
        assert len(results) == 2
        assert results[0].name == "John Doe"
        assert results[1].name == "Jane Smith"
        
        # Verify method calls
        mock_search.assert_called_once_with(
            page=mock_browser_instance.page,
            job_title="Software Engineer",
            location="New York",
            company=None,
        )
        
        mock_extract.assert_called_once_with(
            page=mock_browser_instance.page,
            skills_to_match=["Python"],
        )
        
        mock_paginate.assert_not_called()  # Should not paginate since we got enough results
        mock_browser_instance.close_browser.assert_called_once()  # Browser should be closed 
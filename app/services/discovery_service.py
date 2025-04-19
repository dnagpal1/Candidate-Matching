import asyncio
import logging
import uuid
from typing import Dict, List, Optional

from fastapi import Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.agents.candidate_discovery.agent import CandidateDiscoveryAgent
from app.database.init_db import get_redis_client
from app.models.candidate import Candidate
from app.services.candidate_service import CandidateService

logger = logging.getLogger(__name__)


class LinkedInSearchParams(BaseModel):
    """Parameters for LinkedIn candidate search."""
    title: str
    location: str
    company: Optional[str] = None
    skills: Optional[List[str]] = None
    max_results: int = Field(default=20, ge=1, le=100)


class DiscoveryService:
    """Service for candidate discovery operations."""
    
    def __init__(
        self,
        candidate_service: CandidateService = Depends(),
        redis_client: Optional[Redis] = Depends(get_redis_client),
    ):
        self.candidate_service = candidate_service
        self.redis_client = redis_client
        self.discovery_agent = CandidateDiscoveryAgent()
    
    async def search_linkedin(self, params: LinkedInSearchParams) -> List[Candidate]:
        """
        Search for candidates on LinkedIn with the given parameters.
        This is a synchronous operation that will block until complete.
        """
        try:
            # Use the candidate discovery agent to perform the search
            candidate_profiles = await self.discovery_agent.discover_candidates(
                job_title=params.title,
                location=params.location,
                company=params.company,
                skills=params.skills,
                max_profiles=params.max_results,
            )
            
            # Save candidates to database
            saved_candidates = []
            for profile in candidate_profiles:
                # Convert profile to CandidateCreate model
                candidate = await self.candidate_service.create_candidate(profile)
                saved_candidates.append(candidate)
            
            return saved_candidates
        except Exception as e:
            logger.error(f"Error during LinkedIn search: {str(e)}", exc_info=True)
            raise
    
    async def search_linkedin_background(self, params: LinkedInSearchParams) -> str:
        """
        Start a background task to search for candidates on LinkedIn.
        Returns a task ID that can be used to check the status later.
        """
        task_id = str(uuid.uuid4())
        
        # Store task info in Redis if available
        if self.redis_client:
            try:
                await self.redis_client.hset(
                    f"task:{task_id}",
                    mapping={
                        "status": "pending",
                        "type": "linkedin_search",
                        "params": params.model_dump_json(),
                        "created_at": str(asyncio.get_event_loop().time()),
                        "total_found": "0",
                        "total_saved": "0",
                    },
                )
                
                # Set TTL for task info (24 hours)
                await self.redis_client.expire(f"task:{task_id}", 60 * 60 * 24)
            except Exception as e:
                logger.warning(f"Failed to store task in Redis: {e}. Continuing anyway.")
        else:
            logger.info(f"Redis not available. Task {task_id} info stored in memory only.")
        
        # Start background task
        asyncio.create_task(self._run_background_search(task_id, params))
        
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        Get the status of a background task.
        """
        if not self.redis_client:
            logger.info(f"Redis not available. Cannot retrieve status for task {task_id}")
            return {
                "status": "unknown",
                "note": "Redis not available, cannot retrieve task status"
            }
            
        try:
            task_info = await self.redis_client.hgetall(f"task:{task_id}")
            
            if not task_info:
                return None
            
            return task_info
        except Exception as e:
            logger.error(f"Error retrieving task status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _run_background_search(self, task_id: str, params: LinkedInSearchParams) -> None:
        """
        Run a LinkedIn search in the background and update the status in Redis.
        """
        try:
            # Update task status to running
            if self.redis_client:
                try:
                    await self.redis_client.hset(f"task:{task_id}", "status", "running")
                except Exception as e:
                    logger.warning(f"Failed to update task status in Redis: {e}")
            
            # Use the candidate discovery agent to perform the search
            candidate_profiles = await self.discovery_agent.discover_candidates(
                job_title=params.title,
                location=params.location,
                company=params.company,
                skills=params.skills,
                max_profiles=params.max_results,
            )
            
            # Update total found
            if self.redis_client:
                try:
                    await self.redis_client.hset(
                        f"task:{task_id}", 
                        "total_found", 
                        str(len(candidate_profiles))
                    )
                except Exception as e:
                    logger.warning(f"Failed to update total_found in Redis: {e}")
            
            # Save candidates to database
            saved_count = 0
            for profile in candidate_profiles:
                try:
                    # Save candidate to database
                    await self.candidate_service.create_candidate(profile)
                    saved_count += 1
                    
                    # Update progress in Redis
                    if self.redis_client:
                        try:
                            await self.redis_client.hset(
                                f"task:{task_id}", 
                                "total_saved", 
                                str(saved_count)
                            )
                        except Exception as e:
                            logger.warning(f"Failed to update total_saved in Redis: {e}")
                except Exception as e:
                    logger.error(f"Error saving candidate: {str(e)}", exc_info=True)
            
            # Update task status to completed
            if self.redis_client:
                try:
                    await self.redis_client.hset(
                        f"task:{task_id}",
                        mapping={
                            "status": "completed",
                            "completed_at": str(asyncio.get_event_loop().time()),
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to update task status to completed in Redis: {e}")
        except Exception as e:
            # Update task status to failed
            error_message = str(e)
            logger.error(f"Background task failed: {error_message}", exc_info=True)
            
            if self.redis_client:
                try:
                    await self.redis_client.hset(
                        f"task:{task_id}",
                        mapping={
                            "status": "failed",
                            "error": error_message,
                            "completed_at": str(asyncio.get_event_loop().time()),
                        },
                    )
                except Exception as redis_e:
                    logger.warning(f"Failed to update task status to failed in Redis: {redis_e}") 
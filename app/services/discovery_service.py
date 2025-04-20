import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any, Callable

from fastapi import Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.database.init_db import get_redis_client
from app.models.candidate import Candidate, CandidateCreate
from app.services.candidate_service import CandidateService
from app.graphs.candidate_discovery.graph import run_discovery_graph
from app.graphs.candidate_discovery.schema import SearchParameters

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
    
    async def save_candidates(self, candidates: List[CandidateCreate]) -> List[Candidate]:
        """
        Save a list of candidate profiles to the database.
        
        Args:
            candidates: List of candidate profiles to save
            
        Returns:
            List of saved candidate models
        """
        saved_candidates = []
        for profile in candidates:
            try:
                # Save candidate to database
                candidate = await self.candidate_service.create_candidate(profile)
                saved_candidates.append(candidate)
            except Exception as e:
                logger.error(f"Error saving candidate: {str(e)}", exc_info=True)
        
        return saved_candidates
    
    async def run_background_search(self, task_id: str, search_func: Callable) -> None:
        """
        Run a search function in the background and track its progress.
        
        Args:
            task_id: Unique identifier for the task
            search_func: Async function that performs the search
        """
        try:
            # Update task status to running
            if self.redis_client:
                try:
                    await self.redis_client.hset(f"task:{task_id}", "status", "running")
                    await self.redis_client.hset(f"task:{task_id}", "start_time", str(asyncio.get_event_loop().time()))
                except Exception as e:
                    logger.warning(f"Failed to update task status in Redis: {e}")
            
            # Run the search function
            candidates = await search_func()
            
            # Update total found
            if self.redis_client:
                try:
                    await self.redis_client.hset(
                        f"task:{task_id}", 
                        "total_found", 
                        str(len(candidates))
                    )
                except Exception as e:
                    logger.warning(f"Failed to update total_found in Redis: {e}")
            
            # Save candidates to database
            saved_candidates = await self.save_candidates(candidates)
            saved_count = len(saved_candidates)
            
            # Update total saved
            if self.redis_client:
                try:
                    await self.redis_client.hset(
                        f"task:{task_id}", 
                        "total_saved", 
                        str(saved_count)
                    )
                except Exception as e:
                    logger.warning(f"Failed to update total_saved in Redis: {e}")
            
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
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a background task.
        
        Args:
            task_id: The task ID to check
            
        Returns:
            Dictionary containing task status information or None if not found
        """
        if not self.redis_client:
            logger.info(f"Redis not available. Cannot retrieve status for task {task_id}")
            return {
                "status": "unknown",
                "note": "Redis not available, cannot retrieve task status"
            }
            
        try:
            # Get task info from Redis
            task_info = await self.redis_client.hgetall(f"task:{task_id}")
            
            if not task_info:
                return None
            
            # Convert byte values to strings
            decoded_info = {}
            for key, value in task_info.items():
                if isinstance(key, bytes):
                    key = key.decode("utf-8")
                if isinstance(value, bytes):
                    value = value.decode("utf-8")
                decoded_info[key] = value
            
            return decoded_info
        except Exception as e:
            logger.error(f"Error retrieving task status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
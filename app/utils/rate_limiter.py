import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from asyncpg import Connection, Pool
from fastapi import Depends, HTTPException, status

from app.database.init_db import get_db_pool
from app.config.settings import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter for controlling the frequency of operations.
    Can use either database or in-memory storage for rate limits.
    """
    
    def __init__(
        self,
        max_operations: int,
        operation_type: str,
        reset_interval_hours: int = 24,
        pool: Optional[Pool] = None,
    ):
        """
        Initialize the rate limiter.
        
        Args:
            max_operations: Maximum number of operations allowed per reset interval
            operation_type: Type of operation being rate limited
            reset_interval_hours: Interval in hours after which the counter resets
            pool: Optional database connection pool
        """
        self.max_operations = max_operations
        self.operation_type = operation_type
        self.reset_interval_hours = reset_interval_hours
        self.pool = pool
        
        # In-memory storage for rate limits when not using database
        self._in_memory_counter: Dict[str, Dict] = {}
    
    async def check_rate_limit(self) -> bool:
        """
        Check if the operation can proceed based on rate limits.
        Raises an exception if rate limit is exceeded.
        
        Returns:
            True if the operation can proceed
        """
        # If we have a database pool, use that for persistent rate limiting
        if self.pool:
            return await self._check_db_rate_limit()
        
        # Otherwise use in-memory rate limiting
        return await self._check_memory_rate_limit()
    
    async def _check_memory_rate_limit(self) -> bool:
        """
        Check rate limit using in-memory storage.
        """
        now = datetime.now()
        
        # Get or create counter entry
        if self.operation_type not in self._in_memory_counter:
            self._in_memory_counter[self.operation_type] = {
                "count": 0,
                "reset_at": now + timedelta(hours=self.reset_interval_hours)
            }
        
        counter = self._in_memory_counter[self.operation_type]
        
        # Check if we need to reset the counter
        if now >= counter["reset_at"]:
            counter["count"] = 0
            counter["reset_at"] = now + timedelta(hours=self.reset_interval_hours)
        
        # Check if we're at the limit
        if counter["count"] >= self.max_operations:
            reset_time = counter["reset_at"].strftime("%Y-%m-%d %H:%M:%S")
            logger.warning(
                f"Rate limit exceeded for {self.operation_type}. "
                f"Limit: {self.max_operations}, Reset at: {reset_time}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again after {reset_time}",
            )
        
        # Increment counter and allow operation
        counter["count"] += 1
        logger.debug(
            f"Rate limit check passed for {self.operation_type}. "
            f"Count: {counter['count']}/{self.max_operations}"
        )
        return True
    
    async def _check_db_rate_limit(self) -> bool:
        """
        Check rate limit using database storage.
        """
        now = datetime.now()
        
        async with self.pool.acquire() as conn:
            # Try to get existing rate limit record
            row = await conn.fetchrow(
                "SELECT id, count, reset_at FROM rate_limits WHERE operation = $1",
                self.operation_type,
            )
            
            if row:
                rate_limit_id = row["id"]
                count = row["count"]
                reset_at = row["reset_at"]
                
                # Check if we need to reset the counter
                if now >= reset_at:
                    # Reset counter
                    new_reset_at = now + timedelta(hours=self.reset_interval_hours)
                    await conn.execute(
                        "UPDATE rate_limits SET count = 1, reset_at = $2 WHERE id = $1",
                        rate_limit_id,
                        new_reset_at,
                    )
                    return True
                
                # Check if we're at the limit
                if count >= self.max_operations:
                    reset_time = reset_at.strftime("%Y-%m-%d %H:%M:%S")
                    logger.warning(
                        f"Rate limit exceeded for {self.operation_type}. "
                        f"Limit: {self.max_operations}, Reset at: {reset_time}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Try again after {reset_time}",
                    )
                
                # Increment counter and allow operation
                await conn.execute(
                    "UPDATE rate_limits SET count = count + 1 WHERE id = $1",
                    rate_limit_id,
                )
            else:
                # Create new rate limit record
                reset_at = now + timedelta(hours=self.reset_interval_hours)
                await conn.execute(
                    """
                    INSERT INTO rate_limits (operation, count, reset_at)
                    VALUES ($1, 1, $2)
                    """,
                    self.operation_type,
                    reset_at,
                )
        
        return True 
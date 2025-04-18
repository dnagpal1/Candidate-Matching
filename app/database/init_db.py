import logging
from typing import Dict, Optional

import asyncpg
import redis.asyncio as redis
from asyncpg import Pool

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Global connection pools
pg_pool: Optional[Pool] = None
redis_client: Optional[redis.Redis] = None


async def init_db() -> None:
    """Initialize database connections and create tables if needed."""
    global pg_pool, redis_client
    
    logger.info("Initializing database connections...")
    
    # Create PostgreSQL connection pool
    try:
        pg_pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=5,
            max_size=20,
        )
        logger.info("PostgreSQL connection pool created successfully")
        
        # Initialize schema and tables
        await _create_tables()
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL: {e}", exc_info=True)
        raise
    
    # Create Redis connection
    try:
        redis_client = redis.from_url(
            url=settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await redis_client.ping()
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}", exc_info=True)
        raise


async def get_db_pool() -> Pool:
    """Get the PostgreSQL connection pool."""
    if pg_pool is None:
        raise RuntimeError("Database connection pool not initialized")
    return pg_pool


async def get_redis_client() -> redis.Redis:
    """Get the Redis client."""
    if redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return redis_client


async def close_db_connections() -> None:
    """Close all database connections."""
    global pg_pool, redis_client
    
    if pg_pool:
        logger.info("Closing PostgreSQL connection pool...")
        await pg_pool.close()
        pg_pool = None
    
    if redis_client:
        logger.info("Closing Redis connection...")
        await redis_client.close()
        redis_client = None


async def _create_tables() -> None:
    """Create database tables if they don't exist."""
    if not pg_pool:
        return
    
    async with pg_pool.acquire() as conn:
        # Create candidates table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id UUID PRIMARY KEY,
                name TEXT NOT NULL,
                title TEXT,
                location TEXT,
                current_company TEXT,
                skills TEXT[],
                open_to_work BOOLEAN DEFAULT FALSE,
                profile_url TEXT UNIQUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        # Create rate limiting table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                id SERIAL PRIMARY KEY,
                operation TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                reset_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        logger.info("Database tables created successfully") 
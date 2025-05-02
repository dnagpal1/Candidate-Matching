import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from asyncpg import Record
from fastapi import Depends

from app.database.init_db import get_db_pool
from app.models.candidate import (Candidate, CandidateCreate, CandidateInDB,
                                 CandidateSearchParams, CandidateUpdate)

logger = logging.getLogger(__name__)


class CandidateService:
    """Service for candidate-related database operations."""
    
    def __init__(self, pool=Depends(get_db_pool)):
        self.pool = pool
    
    async def create_candidate(self, candidate: CandidateCreate) -> Candidate:
        """
        Create a new candidate record in the database.
        """
        candidate_id = uuid4()
        now = datetime.now()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO candidates (
                    id, name, title, location, current_company, 
                    skills, open_to_work, profile_url, source, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING *
            """, 
                candidate_id,
                candidate.name,
                candidate.title,
                candidate.location,
                candidate.current_company,
                candidate.skills,
                candidate.open_to_work,
                str(candidate.profile_url) if candidate.profile_url else None,
                candidate.source,
                now,
                now,
            )
            
            return self._record_to_candidate(row)
    
    async def get_candidate(self, candidate_id: UUID) -> Optional[Candidate]:
        """
        Get a candidate by ID.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM candidates WHERE id = $1",
                candidate_id,
            )
            
            if not row:
                return None
                
            return self._record_to_candidate(row)
    
    async def update_candidate(
        self, candidate_id: UUID, candidate_update: CandidateUpdate
    ) -> Optional[Candidate]:
        """
        Update a candidate record.
        """
        # Get existing candidate
        candidate = await self.get_candidate(candidate_id)
        if not candidate:
            return None
        
        # Prepare update values
        update_values = {}
        update_fields = []
        
        for field, value in candidate_update.model_dump(exclude_unset=True).items():
            if value is not None:
                update_values[field] = value
                update_fields.append(field)
        
        if not update_fields:
            return candidate
        
        # Build update query
        query_parts = []
        params = [candidate_id]
        
        for i, field in enumerate(update_fields, start=2):
            if field == "profile_url" and update_values[field]:
                query_parts.append(f"{field} = ${i}")
                params.append(str(update_values[field]))
            else:
                query_parts.append(f"{field} = ${i}")
                params.append(update_values[field])
        
        # Add updated_at field
        query_parts.append(f"updated_at = ${len(params) + 1}")
        params.append(datetime.now())
        
        # Build and execute query
        query = f"""
            UPDATE candidates
            SET {", ".join(query_parts)}
            WHERE id = $1
            RETURNING *
        """
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            
            if not row:
                return None
                
            return self._record_to_candidate(row)
    
    async def delete_candidate(self, candidate_id: UUID) -> bool:
        """
        Delete a candidate by ID.
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM candidates WHERE id = $1",
                candidate_id,
            )
            
            # Parse the DELETE count from result
            return "DELETE 1" in result
    
    async def list_candidates(self, params: CandidateSearchParams) -> List[Candidate]:
        """
        List candidates with optional filtering.
        """
        # Build query conditions
        conditions = []
        query_params = []
        param_idx = 1
        
        if params.title:
            conditions.append(f"title ILIKE ${param_idx}")
            query_params.append(f"%{params.title}%")
            param_idx += 1
            
        if params.location:
            conditions.append(f"location ILIKE ${param_idx}")
            query_params.append(f"%{params.location}%")
            param_idx += 1
            
        if params.company:
            conditions.append(f"current_company ILIKE ${param_idx}")
            query_params.append(f"%{params.company}%")
            param_idx += 1
            
        if params.skills:
            # PostgreSQL array overlap operator: &&
            skills_placeholders = []
            for skill in params.skills:
                skills_placeholders.append(f"${param_idx}")
                query_params.append(skill)
                param_idx += 1
            conditions.append(f"skills && ARRAY[{', '.join(skills_placeholders)}]")
            
        if params.is_open_to_work is not None:
            conditions.append(f"open_to_work = ${param_idx}")
            query_params.append(params.is_open_to_work)
            param_idx += 1
            
        if params.source:
            conditions.append(f"source = ${param_idx}")
            query_params.append(params.source)
            param_idx += 1
        
        # Build where clause
        where_clause = " AND ".join(conditions)
        if where_clause:
            where_clause = f"WHERE {where_clause}"
        
        # Add pagination
        query = f"""
            SELECT * FROM candidates
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        query_params.append(params.limit)
        query_params.append(params.offset)
        
        # Execute query
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *query_params)
            return [self._record_to_candidate(row) for row in rows]
    
    def _record_to_candidate(self, record: Record) -> Candidate:
        """
        Convert a database record to a Candidate model.
        """
        return Candidate(
            id=record["id"],
            name=record["name"],
            title=record["title"],
            location=record["location"],
            current_company=record["current_company"],
            skills=record["skills"] if record["skills"] else [],
            open_to_work=record["open_to_work"],
            profile_url=record["profile_url"],
            source=record.get("source", "linkedin"),  # Default to LinkedIn if not present
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        ) 
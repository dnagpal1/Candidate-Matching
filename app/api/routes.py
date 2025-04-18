from fastapi import APIRouter

from app.api.v1 import candidates, discovery

# Initialize main router
router = APIRouter()

# Include all API route modules
router.include_router(candidates.router, prefix="/v1/candidates", tags=["candidates"])
router.include_router(discovery.router, prefix="/v1/discovery", tags=["discovery"]) 
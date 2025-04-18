import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.config.settings import settings
from app.database.init_db import close_db_connections, init_db

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the FastAPI application.
    Handles database connections and other startup/shutdown tasks.
    """
    logger.info("Starting application...")
    
    # Initialize database
    await init_db()
    
    # Initialize browser (if needed)
    # await init_browser()
    
    logger.info("Application started successfully")
    
    yield
    
    # Cleanup resources
    logger.info("Shutting down application...")
    await close_db_connections()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="AI Candidate Matching Platform",
    description="API for AI-driven candidate and job matching",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/", tags=["Health Check"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": app.version}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    ) 
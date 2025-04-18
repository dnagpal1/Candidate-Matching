# AI-driven Hiring Platform - Setup Guide

This document provides instructions for setting up and running the AI-driven Hiring Platform (Phase 1: Candidate Discovery).

## Prerequisites

- Python 3.10+
- Docker and Docker Compose (optional, for containerized setup)
- PostgreSQL
- Redis
- LinkedIn account credentials
- OpenAI API key

## Environment Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd candidate-matching
   ```

2. Set up environment variables by copying the example file and editing it:
   ```bash
   cp .env.example .env
   ```

3. Edit the `.env` file with your credentials:
   - Set your LinkedIn credentials (`LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`)
   - Add your OpenAI API key (`OPENAI_API_KEY`)
   - Configure database connection details
   - Set secure values for `SECRET_KEY` and `ENCRYPTION_KEY`

## Running with Docker

The easiest way to run the application is using Docker Compose:

1. Build and start all services:
   ```bash
   docker-compose up -d
   ```

2. The API will be available at http://localhost:8000

3. Access the API documentation at http://localhost:8000/docs

## Manual Setup

If you prefer to run the application outside of Docker:

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e .
   ```

2. Install Playwright browsers:
   ```bash
   playwright install
   ```

3. Ensure PostgreSQL and Redis are running locally or update the connection details in your `.env` file.

4. Start the application:
   ```bash
   uvicorn app.main:app --reload
   ```

## API Endpoints

### Candidate Discovery

- **POST /api/v1/discovery/linkedin/search**: Search for candidates on LinkedIn
  - Parameters:
    - `title`: Job title to search for (required)
    - `location`: Location to search in (required)
    - `company`: Company name filter (optional)
    - `skills`: Skills to filter by (optional)
    - `max_results`: Maximum number of results (default: 20)
    - `run_in_background`: Whether to run the search as a background task (default: false)

- **GET /api/v1/discovery/status/{task_id}**: Get the status of a background search task

### Candidates Management

- **GET /api/v1/candidates**: List candidates with optional filtering
- **GET /api/v1/candidates/{candidate_id}**: Get a candidate by ID
- **POST /api/v1/candidates**: Create a new candidate
- **PATCH /api/v1/candidates/{candidate_id}**: Update a candidate
- **DELETE /api/v1/candidates/{candidate_id}**: Delete a candidate

## Troubleshooting

- If you encounter LinkedIn login issues, ensure your credentials are correct and try running without headless mode by setting `BROWSER_HEADLESS=false`
- For rate limiting issues, adjust the `MAX_PROFILES_PER_DAY` and `RATE_LIMIT_DELAY_SECONDS` in your `.env` file
- Check the logs for detailed error messages and debugging information

## Development

- Run tests with `pytest`
- Format code with `black .`
- Lint with `ruff check .` 
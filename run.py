#!/usr/bin/env python
"""
Run script for the AI Candidate Matching Platform.
"""
import argparse
import uvicorn


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the AI Candidate Matching Platform")
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host to bind the server to"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind the server to"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="Number of worker processes"
    )
    return parser.parse_args()


def main():
    """Main entry point for the application."""
    args = parse_args()
    
    print(f"Starting AI Candidate Matching Platform on {args.host}:{args.port}")
    
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
    )


if __name__ == "__main__":
    main() 
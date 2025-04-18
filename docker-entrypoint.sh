#!/bin/bash
set -e

# If command starts with an option, prepend uvicorn command
if [ "${1:0:1}" = '-' ]; then
  set -- uvicorn app.main:app "$@"
fi

# Initialize database if needed
if [ "$1" = 'uvicorn' ]; then
  echo "Running application setup..."
  # You can add database migrations or other setup here
fi

# Execute the command
exec "$@" 
#!/bin/bash
# Start Archiverr API Server

echo "============================================"
echo "Starting Archiverr API Server"
echo "============================================"
echo ""

# Activate venv
source .venv/bin/activate

# Check if MongoDB is needed
echo "Note: MongoDB is optional for testing"
echo "      API will work with or without MongoDB"
echo ""

# Start server
echo "Starting server on http://0.0.0.0:8000"
echo "Documentation: http://0.0.0.0:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

archiverr serve --port 8000

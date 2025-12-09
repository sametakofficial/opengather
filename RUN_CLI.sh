#!/bin/bash
# Run Archiverr CLI

echo "============================================"
echo "Running Archiverr CLI"
echo "============================================"
echo ""

# Activate venv
source .venv/bin/activate

# Run CLI
echo "Executing: archiverr"
echo ""

archiverr

echo ""
echo "============================================"
echo "CLI Execution Complete"
echo "============================================"
echo ""
echo "Check output directory for results:"
ls -lh output/*.json 2>/dev/null || echo "No output files yet"

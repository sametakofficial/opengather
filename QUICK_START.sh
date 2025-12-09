#!/bin/bash
# ============================================================================
# ARCHIVERR QUICK START
# ============================================================================
# Hızlı başlangıç için kullan
# ============================================================================

echo "======================================"
echo "ARCHIVERR QUICK START"
echo "======================================"
echo ""

# Activate venv
source .venv/bin/activate

echo "1. Testing CLI..."
echo "Running: archiverr"
echo ""
archiverr
echo ""

echo "2. Checking output..."
if [ -d "output" ]; then
    echo "✅ Output files:"
    ls -lht output/*.json | head -3
else
    echo "⚠️  No output directory"
fi
echo ""

echo "======================================"
echo "To start API server:"
echo "  archiverr serve"
echo ""
echo "To see more options:"
echo "  archiverr --help"
echo "======================================"

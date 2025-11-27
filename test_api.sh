#!/bin/bash
# =============================================================================
# ARCHİVERR API TEST SCRIPT
# =============================================================================
# Bu script API'yi test etmek için kullanılır.
# 
# Kullanım:
#   1. API'yi başlat: python -m archiverr serve
#   2. Bu scripti çalıştır: bash test_api.sh
# =============================================================================

BASE_URL="http://localhost:8000"
API_URL="$BASE_URL/api/v1"

echo "========================================"
echo "ARCHİVERR API TEST"
echo "========================================"
echo ""

# 1. Health Check
echo "📍 1. Health Check..."
curl -s "$API_URL/system/health" | python3 -m json.tool 2>/dev/null || echo "API not running!"
echo ""

# 2. System Info
echo "📍 2. System Info..."
curl -s "$API_URL/system/info" | python3 -m json.tool 2>/dev/null
echo ""

# 3. List Executions
echo "📍 3. List Executions..."
curl -s "$API_URL/executions" | python3 -m json.tool 2>/dev/null
echo ""

# 4. List Branches
echo "📍 4. List Branches..."
curl -s "$API_URL/versioning/branches" | python3 -m json.tool 2>/dev/null
echo ""

# 5. Run Default (DRY RUN)
echo "📍 5. Run with config.yml (dry_run)..."
echo "   POST $API_URL/run"
curl -s -X POST "$API_URL/run" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "debug": false}' | python3 -m json.tool 2>/dev/null
echo ""

echo "========================================"
echo "TEST TAMAMLANDI"
echo "========================================"

#!/bin/bash
# Full System Test - Archiverr End-to-End
# Tests: CLI, MongoDB, FastAPI, Custom Config

set -e  # Exit on error

echo "======================================"
echo "🚀 FULL SYSTEM TEST - ARCHIVERR"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_ROOT="/home/samet/Workspace/archiverr"
cd "$PROJECT_ROOT"

# Check MongoDB
echo -e "${YELLOW}1. Checking MongoDB...${NC}"
if ! pgrep -x mongod > /dev/null; then
    echo -e "${RED}❌ MongoDB not running!${NC}"
    echo "Start with: sudo systemctl start mongod"
    exit 1
fi
echo -e "${GREEN}✅ MongoDB running${NC}"
echo ""

# Clean MongoDB collections
echo -e "${YELLOW}2. Cleaning MongoDB collections...${NC}"
mongo archiverr --eval "
    db.runs.deleteMany({});
    db.jobs.deleteMany({});
    db.plugins.deleteMany({});
    print('✅ Collections cleaned');
"
echo ""

# Test 1: CLI with default config
echo -e "${YELLOW}3. TEST 1: CLI with default config.yml${NC}"
echo "Running: python -m archiverr"
python -m archiverr
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ CLI test passed${NC}"
else
    echo -e "${RED}❌ CLI test failed${NC}"
    exit 1
fi
echo ""

# Verify MongoDB data
echo -e "${YELLOW}4. Verifying MongoDB data...${NC}"
mongo archiverr --eval "
    var runs = db.runs.count();
    var jobs = db.jobs.count();
    var plugins = db.plugins.count();
    
    print('Collections:');
    print('  runs: ' + runs);
    print('  jobs: ' + jobs);
    print('  plugins: ' + plugins);
    
    if (runs == 0) {
        print('❌ NO runs found!');
        quit(1);
    }
    if (jobs == 0) {
        print('❌ NO jobs found!');
        quit(1);
    }
    if (plugins == 0) {
        print('❌ NO plugins found!');
        quit(1);
    }
    
    print('✅ MongoDB data verified');
"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ MongoDB verification passed${NC}"
else
    echo -e "${RED}❌ MongoDB verification failed${NC}"
    exit 1
fi
echo ""

# Test 2: FastAPI Health Check
echo -e "${YELLOW}5. TEST 2: FastAPI Health Check${NC}"
# Start FastAPI in background
python -m archiverr serve &
FASTAPI_PID=$!
sleep 3

# Check health
HEALTH=$(curl -s http://localhost:8000/health || echo "FAILED")
if [[ "$HEALTH" == *"ok"* ]]; then
    echo -e "${GREEN}✅ FastAPI health check passed${NC}"
else
    echo -e "${RED}❌ FastAPI health check failed${NC}"
    kill $FASTAPI_PID 2>/dev/null
    exit 1
fi
echo ""

# Test 3: API Run with default config
echo -e "${YELLOW}6. TEST 3: API Run (default config)${NC}"
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/run/ \
    -H "Content-Type: application/json")

if [[ "$RESPONSE" == *"success"* ]]; then
    echo -e "${GREEN}✅ API run (default) passed${NC}"
    echo "Response: $RESPONSE" | jq -r '.execution_id, .total_matches'
else
    echo -e "${RED}❌ API run (default) failed${NC}"
    echo "Response: $RESPONSE"
    kill $FASTAPI_PID 2>/dev/null
    exit 1
fi
echo ""

# Test 4: API Run with custom config
echo -e "${YELLOW}7. TEST 4: API Run (custom config)${NC}"
CUSTOM_CONFIG='{
  "config_override": {
    "options": {
      "log_level": "DEBUG",
      "dry_run": false
    }
  }
}'

RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/run/ \
    -H "Content-Type: application/json" \
    -d "$CUSTOM_CONFIG")

if [[ "$RESPONSE" == *"success"* ]]; then
    echo -e "${GREEN}✅ API run (custom config) passed${NC}"
    echo "Response: $RESPONSE" | jq -r '.execution_id, .total_matches'
else
    echo -e "${RED}❌ API run (custom config) failed${NC}"
    echo "Response: $RESPONSE"
    kill $FASTAPI_PID 2>/dev/null
    exit 1
fi
echo ""

# Cleanup
echo -e "${YELLOW}8. Cleanup${NC}"
kill $FASTAPI_PID 2>/dev/null
echo -e "${GREEN}✅ FastAPI stopped${NC}"
echo ""

# Final MongoDB check - NO LEGACY COLLECTIONS!
echo -e "${YELLOW}9. Final Check: NO LEGACY COLLECTIONS${NC}"
mongo archiverr --eval "
    var executions = db.executions.count();
    var matches = db.matches.count();
    var plugin_results = db.plugin_results.count();
    
    print('Legacy Collections (SHOULD BE ZERO):');
    print('  executions: ' + executions);
    print('  matches: ' + matches);
    print('  plugin_results: ' + plugin_results);
    
    if (executions > 0 || matches > 0 || plugin_results > 0) {
        print('❌ LEGACY COLLECTIONS FOUND!');
        print('System is using old collections!');
        quit(1);
    }
    
    print('✅ NO legacy collections - CLEAN!');
"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Legacy collections check passed${NC}"
else
    echo -e "${RED}❌ Legacy collections still exist!${NC}"
    exit 1
fi
echo ""

# Summary
echo "======================================"
echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
echo "======================================"
echo ""
echo "Tests completed:"
echo "  ✅ MongoDB running"
echo "  ✅ CLI with default config"
echo "  ✅ MongoDB data verified"
echo "  ✅ FastAPI health check"
echo "  ✅ API run (default config)"
echo "  ✅ API run (custom config)"
echo "  ✅ NO legacy collections"
echo ""
echo "System is PRODUCTION READY! 🚀"

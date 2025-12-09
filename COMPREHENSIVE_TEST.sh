#!/bin/bash
# ============================================================================
# ARCHIVERR COMPREHENSIVE TEST SUITE
# ============================================================================
# Bu script archiverr sisteminin tüm bileşenlerini test eder
# ============================================================================

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
print_header() {
    echo -e "\n${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    ((TESTS_PASSED++))
}

print_failure() {
    echo -e "${RED}❌ $1${NC}"
    ((TESTS_FAILED++))
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# ============================================================================
# TEST 1: Package Installation
# ============================================================================
print_header "TEST 1: Package Installation Check"

if .venv/bin/pip show archiverr > /dev/null 2>&1; then
    VERSION=$(.venv/bin/pip show archiverr | grep Version | cut -d' ' -f2)
    print_success "archiverr package installed (version $VERSION)"
else
    print_failure "archiverr package NOT installed"
fi

# ============================================================================
# TEST 2: Command Availability
# ============================================================================
print_header "TEST 2: Command Availability"

if [ -f ".venv/bin/archiverr" ]; then
    print_success "archiverr command exists"
else
    print_failure "archiverr command NOT found"
fi

# ============================================================================
# TEST 3: Command Help
# ============================================================================
print_header "TEST 3: Command Help"

if .venv/bin/archiverr --help > /dev/null 2>&1; then
    print_success "archiverr --help works"
else
    print_failure "archiverr --help failed"
fi

# ============================================================================
# TEST 4: Serve Command
# ============================================================================
print_header "TEST 4: Serve Command Help"

if .venv/bin/archiverr serve --help > /dev/null 2>&1; then
    print_success "archiverr serve --help works"
else
    print_failure "archiverr serve --help failed"
fi

# ============================================================================
# TEST 5: Python Module
# ============================================================================
print_header "TEST 5: Python Module Import"

if .venv/bin/python -c "import archiverr; print('OK')" > /dev/null 2>&1; then
    print_success "archiverr module can be imported"
else
    print_failure "archiverr module import failed"
fi

# ============================================================================
# TEST 6: Test Files Setup
# ============================================================================
print_header "TEST 6: Test Files Setup"

# Create test directories
mkdir -p /tmp/test_movies
mkdir -p "/tmp/friends/friends s01"

# Create test files
touch "/tmp/test_movies/The.Matrix.1999.1080p.mkv"
touch "/tmp/friends/friends s01/friends s01 e02.mkv"

if [ -f "/tmp/test_movies/The.Matrix.1999.1080p.mkv" ]; then
    print_success "Test files created"
else
    print_failure "Test files creation failed"
fi

# ============================================================================
# TEST 7: Config File
# ============================================================================
print_header "TEST 7: Config File Check"

if [ -f "config.yml" ]; then
    print_success "config.yml exists"
else
    print_failure "config.yml NOT found"
fi

# ============================================================================
# TEST 8: Environment Variables
# ============================================================================
print_header "TEST 8: Environment Variables"

if [ -f ".env" ]; then
    source .env
    if [ -n "$TMDB_API_KEY" ]; then
        print_success "TMDB_API_KEY is set"
    else
        print_warning "TMDB_API_KEY not set (TMDB plugin will fail)"
    fi
else
    print_warning ".env file not found"
fi

# ============================================================================
# TEST 9: CLI Execution (Dry Run)
# ============================================================================
print_header "TEST 9: CLI Execution (Dry Run)"

echo "Running: .venv/bin/archiverr"
echo "This will process config.yml in dry-run mode..."
echo ""

# Run archiverr CLI
if .venv/bin/archiverr 2>&1 | tee /tmp/archiverr_test_output.log; then
    if grep -q "Archiverr complete" /tmp/archiverr_test_output.log; then
        print_success "CLI execution completed successfully"
    else
        print_warning "CLI ran but completion message not found"
    fi
else
    print_failure "CLI execution failed"
fi

# ============================================================================
# TEST 10: Output Files
# ============================================================================
print_header "TEST 10: Output Files Check"

if [ -d "output" ]; then
    FILE_COUNT=$(find output -name "*.json" | wc -l)
    if [ "$FILE_COUNT" -gt 0 ]; then
        print_success "Found $FILE_COUNT output file(s)"
        echo "Latest output files:"
        ls -lht output/*.json | head -3
    else
        print_warning "Output directory exists but no JSON files found"
    fi
else
    print_warning "Output directory not found"
fi

# ============================================================================
# TEST 11: Start FastAPI Server (Background)
# ============================================================================
print_header "TEST 11: FastAPI Server Test"

echo "Starting FastAPI server on port 8000..."
.venv/bin/archiverr serve --port 8000 > /tmp/archiverr_api.log 2>&1 &
API_PID=$!

# Wait for server to start
sleep 5

# Test health endpoint
if curl -s http://localhost:8000/api/v1/system/health > /dev/null 2>&1; then
    print_success "API server started and responding"
    
    # Test API endpoints
    echo ""
    echo "Testing API endpoints..."
    
    # Health check
    if curl -s http://localhost:8000/api/v1/system/health | grep -q "status"; then
        print_success "Health endpoint works"
    fi
    
    # System info
    if curl -s http://localhost:8000/api/v1/system/status > /dev/null 2>&1; then
        print_success "System status endpoint works"
    fi
    
    # Kill server
    kill $API_PID 2>/dev/null || true
    wait $API_PID 2>/dev/null || true
else
    print_failure "API server failed to start or not responding"
    kill $API_PID 2>/dev/null || true
fi

# ============================================================================
# TEST 12: MongoDB Connection (Optional)
# ============================================================================
print_header "TEST 12: MongoDB Connection (Optional)"

if docker ps | grep -q archiverr-mongo; then
    print_success "MongoDB container is running"
    
    # Test connection
    if .venv/bin/python -c "
from pymongo import MongoClient
try:
    client = MongoClient('mongodb://admin:admin123@localhost:27017/', serverSelectionTimeoutMS=2000)
    client.server_info()
    print('OK')
except:
    print('FAIL')
" | grep -q "OK"; then
        print_success "MongoDB connection successful"
    else
        print_failure "MongoDB connection failed"
    fi
else
    print_warning "MongoDB container not running (optional for testing)"
    echo "To start MongoDB: docker run -d --name archiverr-mongo -p 27017:27017 \\"
    echo "  -e MONGO_INITDB_ROOT_USERNAME=admin -e MONGO_INITDB_ROOT_PASSWORD=admin123 mongo:latest"
fi

# ============================================================================
# SUMMARY
# ============================================================================
print_header "TEST SUMMARY"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
echo -e "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CRITICAL TESTS PASSED!${NC}"
    echo -e "${GREEN}✅ System is working correctly${NC}"
    echo ""
    echo "You can now use:"
    echo "  .venv/bin/archiverr              # CLI mode"
    echo "  .venv/bin/archiverr serve        # API mode"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo "Please check the errors above"
    exit 1
fi

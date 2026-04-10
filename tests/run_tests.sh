#!/bin/bash
# Agens Test Runner - Run all tests

set -e

echo "========================================"
echo "Agens Multi-Agent System - Test Suite"
echo "========================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Function to run a test and capture result
run_test() {
    local name="$1"
    local command="$2"
    echo ""
    echo -e "${YELLOW}Running: $name${NC}"
    if eval "$command"; then
        echo -e "${GREEN}✓ $name passed${NC}"
        return 0
    else
        echo -e "${RED}✗ $name failed${NC}"
        return 1
    fi
}

# Track results
TOTAL=0
PASSED=0
FAILED=0

# Backend API Tests
echo ""
echo "========================================"
echo "Backend API Tests"
echo "========================================"

if [ -f "$PROJECT_DIR/tests/test_api.py" ]; then
    if run_test "API Tests (test_api.py)" "python tests/test_api.py"; then
        ((PASSED++))
    else
        ((FAILED++))
    fi
else
    echo -e "${YELLOW}Skipping API tests - test_api.py not found${NC}"
fi
((TOTAL++))

# Frontend Tests
echo ""
echo "========================================"
echo "Frontend Tests"
echo "========================================"

if [ -d "$PROJECT_DIR/frontend" ]; then
    if run_test "Frontend Tests (test_frontend.py)" "python tests/test_frontend.py"; then
        ((PASSED++))
    else
        ((FAILED++))
    fi
else
    echo -e "${YELLOW}Skipping frontend tests - frontend directory not found${NC}"
fi
((TOTAL++))

# Test API with curl (basic connectivity)
echo ""
echo "========================================"
echo "Basic Connectivity Tests"
echo "========================================"

# Check if server is running
if curl -s --max-time 5 http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend server is running at http://localhost:8000${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Backend server is not running${NC}"
    echo "  Start with: python -m uvicorn api.main:app --reload --port 8000"
    ((FAILED++))
fi
((TOTAL++))

# Check if frontend dev server is running
if curl -s --max-time 5 http://localhost:5173 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Frontend dev server is running at http://localhost:5173${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ Frontend dev server is not running${NC}"
    echo "  Start with: cd frontend && npm run dev"
    echo "  (This is optional for development)"
    ((PASSED++))  # Not a failure
fi
((TOTAL++))

# Summary
echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo -e "Total:  $TOTAL"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"

if [ $FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi

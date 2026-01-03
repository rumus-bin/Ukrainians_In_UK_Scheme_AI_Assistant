#!/bin/bash
# Train Monitor Docker Integration Verification Script
# Verifies that Docker Compose and environment configuration is correct

set -e

echo "======================================================================"
echo "TRAIN MONITOR DEPLOYMENT VERIFICATION"
echo "======================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

# Test 1: Docker Compose syntax
echo "Test 1: Docker Compose Syntax Validation"
echo "----------------------------------------------------------------------"
if docker compose config --quiet 2>&1 | grep -q "ERROR"; then
    echo -e "${RED}❌ FAILED: Invalid docker-compose.yml syntax${NC}"
    ((FAILED++))
else
    echo -e "${GREEN}✅ PASSED: docker-compose.yml syntax is valid${NC}"
    ((PASSED++))
fi
echo ""

# Test 2: Train Monitor service definition
echo "Test 2: Train Monitor Service Definition"
echo "----------------------------------------------------------------------"
if docker compose config 2>/dev/null | grep -q "train-monitor:"; then
    echo -e "${GREEN}✅ PASSED: train-monitor service is defined${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ FAILED: train-monitor service not found${NC}"
    ((FAILED++))
fi
echo ""

# Test 3: Container name check
echo "Test 3: Container Name Configuration"
echo "----------------------------------------------------------------------"
CONTAINER_NAME=$(docker compose config 2>/dev/null | grep -A 20 "train-monitor:" | grep "container_name:" | awk '{print $2}')
if [ "$CONTAINER_NAME" = "ukraine-bot-train-monitor" ]; then
    echo -e "${GREEN}✅ PASSED: Container name is correct: $CONTAINER_NAME${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ FAILED: Wrong container name: $CONTAINER_NAME${NC}"
    ((FAILED++))
fi
echo ""

# Test 4: Health check configuration
echo "Test 4: Health Check Configuration"
echo "----------------------------------------------------------------------"
if docker compose config 2>/dev/null | grep -A 30 "train-monitor:" | grep -q "healthcheck:"; then
    echo -e "${GREEN}✅ PASSED: Health check is configured${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ FAILED: Health check not found${NC}"
    ((FAILED++))
fi
echo ""

# Test 5: Environment variables documentation
echo "Test 5: Environment Variables Documentation"
echo "----------------------------------------------------------------------"
if [ -f ".env.example" ]; then
    MISSING_VARS=""

    for VAR in "TRAIN_MONITOR_ENABLED" "TRAIN_MONITOR_DRY_RUN" "DARWIN_API_KEY" "TRAIN_MONITOR_STATIONS"; do
        if ! grep -q "$VAR" .env.example; then
            MISSING_VARS="$MISSING_VARS $VAR"
        fi
    done

    if [ -z "$MISSING_VARS" ]; then
        echo -e "${GREEN}✅ PASSED: All required variables documented in .env.example${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ FAILED: Missing variables in .env.example:$MISSING_VARS${NC}"
        ((FAILED++))
    fi
else
    echo -e "${RED}❌ FAILED: .env.example file not found${NC}"
    ((FAILED++))
fi
echo ""

# Test 6: Volume mounts
echo "Test 6: Volume Mounts Configuration"
echo "----------------------------------------------------------------------"
CONFIG_OUTPUT=$(docker compose config 2>/dev/null)
REQUIRED_VOLUMES=("./src:/app/src" "./logs:/app/logs" "./.env:/app/.env")
VOLUMES_OK=true

for VOL in "${REQUIRED_VOLUMES[@]}"; do
    if ! echo "$CONFIG_OUTPUT" | grep -A 50 "train-monitor:" | grep -q "$VOL"; then
        echo -e "${RED}❌ Missing volume: $VOL${NC}"
        VOLUMES_OK=false
    fi
done

if [ "$VOLUMES_OK" = true ]; then
    echo -e "${GREEN}✅ PASSED: All required volumes are mounted${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ FAILED: Some volumes are missing${NC}"
    ((FAILED++))
fi
echo ""

# Test 7: Command configuration
echo "Test 7: Start Command Configuration"
echo "----------------------------------------------------------------------"
if docker compose config 2>/dev/null | grep -A 50 "train-monitor:" | grep "command:" | grep -q "src.train_monitor.monitor"; then
    echo -e "${GREEN}✅ PASSED: Correct start command configured${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ FAILED: Wrong or missing start command${NC}"
    ((FAILED++))
fi
echo ""

# Summary
echo "======================================================================"
echo "TEST SUMMARY"
echo "======================================================================"
echo "Total tests: $((PASSED + FAILED))"
echo -e "${GREEN}✅ Passed: $PASSED${NC}"
echo -e "${RED}❌ Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL DEPLOYMENT TESTS PASSED! 🎉${NC}"
    echo "======================================================================"
    echo "Docker integration is ready for deployment"
    echo "======================================================================"
    exit 0
else
    echo -e "${RED}⚠️ $FAILED test(s) failed${NC}"
    echo "======================================================================"
    exit 1
fi

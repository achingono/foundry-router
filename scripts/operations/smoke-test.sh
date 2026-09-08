#!/usr/bin/env bash

# Phase 07: Operational Smoke Test Suite for Foundry Router
# Validates core functionality in staging/production deployments

set -euo pipefail

# Configuration
APP_URL="${1:-}"
ADMIN_KEY="${2:-}"
MAX_RETRIES=30
RETRY_DELAY=5

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
  echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $*"
}

usage() {
  cat <<EOF
Usage: smoke-test.sh [OPTIONS]

Options:
  --url URL                 Application URL (required)
  --admin-key KEY          Admin API key for authenticated endpoints
  --max-retries N          Maximum retry attempts (default: 30)
  --retry-delay SECONDS    Delay between retries (default: 5)
  --help                   Show this help message

Examples:
  ./scripts/operations/smoke-test.sh --url https://app.example.com
  ./scripts/operations/smoke-test.sh --url https://app.example.com --admin-key secret123
EOF
  exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      APP_URL="$2"
      shift 2
      ;;
    --admin-key)
      ADMIN_KEY="$2"
      shift 2
      ;;
    --max-retries)
      MAX_RETRIES="$2"
      shift 2
      ;;
    --retry-delay)
      RETRY_DELAY="$2"
      shift 2
      ;;
    --help)
      usage
      ;;
    *)
      log_error "Unknown option: $1"
      usage
      ;;
  esac
done

# Validate required arguments
if [[ -z "$APP_URL" ]]; then
  log_error "Application URL is required"
  usage
fi

# Test helper
test_endpoint() {
  local method="$1"
  local endpoint="$2"
  local expected_status="$3"
  local auth_header=""
  
  if [[ "$endpoint" == /admin/* ]] || [[ "$endpoint" == /metrics* ]]; then
    if [[ -n "$ADMIN_KEY" ]]; then
      auth_header="-H 'x-admin-key: $ADMIN_KEY'"
    else
      log_warn "Skipping $endpoint (requires --admin-key)"
      return 0
    fi
  fi
  
  local response
  response=$(curl -s -w "\n%{http_code}" -X "$method" \
    -H "Content-Type: application/json" \
    $auth_header \
    "$APP_URL$endpoint" 2>&1 || echo "error")
  
  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body
  body=$(echo "$response" | head -n -1)
  
  if [[ "$http_code" == "$expected_status" ]] || [[ "$http_code" == 2* ]]; then
    log_info "✓ $method $endpoint - Status: $http_code"
    return 0
  else
    log_error "✗ $method $endpoint - Expected: $expected_status, Got: $http_code"
    echo "  Response: $body"
    return 1
  fi
}

# Wait for app to be ready
wait_for_ready() {
  local attempt=0
  while [[ $attempt -lt $MAX_RETRIES ]]; do
    log_info "Checking readiness (attempt $((attempt + 1))/$MAX_RETRIES)..."
    
    local response
    response=$(curl -s -w "\n%{http_code}" -X GET \
      -H "Content-Type: application/json" \
      "$APP_URL/health/live" 2>&1 || echo "error")
    
    local http_code
    http_code=$(echo "$response" | tail -n1)
    
    if [[ "$http_code" == "200" ]]; then
      log_info "Application is ready"
      return 0
    fi
    
    log_warn "Application not ready yet (HTTP $http_code), waiting ${RETRY_DELAY}s..."
    sleep "$RETRY_DELAY"
    ((attempt++))
  done
  
  log_error "Application failed to become ready after $MAX_RETRIES attempts"
  return 1
}

# Main test suite
main() {
  log_info "Starting Foundry Router smoke tests"
  log_info "Target: $APP_URL"
  
  # Step 1: Wait for app readiness
  log_info "Step 1: Waiting for application readiness..."
  if ! wait_for_ready; then
    exit 1
  fi
  
  # Step 2: Basic health checks
  log_info "Step 2: Running health checks..."
  test_endpoint "GET" "/health/live" "200" || exit 1
  test_endpoint "GET" "/health/ready" "200" || exit 1
  
  # Step 3: Admin endpoints (if key provided)
  if [[ -n "$ADMIN_KEY" ]]; then
    log_info "Step 3: Running admin diagnostics..."
    test_endpoint "GET" "/admin/status" "200" || exit 1
    test_endpoint "GET" "/metrics" "200" || exit 1
  else
    log_warn "Step 3: Skipping admin tests (no --admin-key provided)"
  fi
  
  # Step 4: Model listing (requires credentials but not admin)
  log_info "Step 4: Checking model availability..."
  local models_response
  models_response=$(curl -s -X GET \
    -H "Content-Type: application/json" \
    "$APP_URL/openai/v1/models" 2>&1)
  
  if echo "$models_response" | grep -q "data"; then
    log_info "✓ Models endpoint returned valid response"
  else
    log_error "✗ Models endpoint failed"
    echo "  Response: $models_response"
    exit 1
  fi
  
  # Step 5: Verify logging and metrics collection
  log_info "Step 5: Verifying observability (checking no errors in health)..."
  local status
  status=$(curl -s -X GET \
    -H "Content-Type: application/json" \
    "$APP_URL/health/ready" 2>&1)
  
  if echo "$status" | grep -q "checks"; then
    log_info "✓ Health endpoint returns full diagnostics"
  else
    log_warn "Health endpoint missing extended checks"
  fi
  
  log_info ""
  log_info "========================================"
  log_info "✓ All smoke tests passed!"
  log_info "========================================"
  return 0
}

main "$@"

# Agent-Driven PR Validation Patterns Guide

## 1. Overview

### Purpose
This guide documents patterns for agent-driven CI/CD validation against live Railway PR preview environments. It enables automated, intelligent validation of code changes before they reach production.

### 3-Level Agent Hierarchy Integration
Railway PR environments integrate with our agent hierarchy as follows:

```
┌─────────────────────────────────────────────────────────────────────┐
│  LEVEL 1: SYSTEM 3 (Meta-Orchestrator)                              │
│  - Monitors PR activity across all repositories                     │
│  - Assigns PR validation tasks to orchestrators                     │
│  - Aggregates validation results for reporting                      │
├─────────────────────────────────────────────────────────────────────┤
│  LEVEL 2: ORCHESTRATOR                                              │
│  - Discovers Railway PR environment URLs                            │
│  - Coordinates multi-step validation workflow                       │
│  - Delegates specific validation tasks to specialist workers        │
│  - Posts consolidated results to GitHub PR                          │
├─────────────────────────────────────────────────────────────────────┤
│  LEVEL 3: WORKERS (Specialists)                                     │
│  - backend-solutions-engineer: API endpoint validation              │
│  - tdd-test-engineer: Browser-based UI validation                   │
│  - validation-test-agent: Health checks & E2E test execution        │
└─────────────────────────────────────────────────────────────────────┘
```

### Goal
**Orchestrators discover PR environment URLs and delegate validation to specialist workers**, following the "investigation by orchestrator, implementation by workers" principle. Orchestrators use Read/Grep/Glob to investigate Railway status and GitHub context, but delegate all actual testing and validation work to specialist workers.

---

## 2. Discovering PR Environment URLs

### Using Railway CLI

Railway provides JSON output for programmatic parsing:

```bash
# Get status for all environments
railway status --json

# Switch to PR environment context
railway environment pr-123

# Get environment variables (including PUBLIC_URL)
railway variables --json
```

### Using the `railway-environment` Skill

The `railway-environment` skill wraps Railway MCP commands for progressive disclosure:

```python
# List all environments
Skill("railway-environment", args="list")

# Switch to PR environment
Skill("railway-environment", args="use pr-123")

# Get current environment details
Skill("railway-environment", args="show")
```

### PR Environment Naming Pattern

Railway PR environments follow a predictable naming convention:
- **Format**: `pr-{number}` where `{number}` matches the GitHub PR number
- **Example**: PR #45 on GitHub → Railway environment `pr-45`
- **Domain**: Railway auto-generates domains like `pr-45-production.up.railway.app`

### Getting the Deployment URL

**Method 1: Environment Variables**
```bash
railway environment pr-123
railway variables --json | jq -r '.[] | select(.name=="PUBLIC_URL") | .value'
```

**Method 2: Deployment Info**
```bash
railway status --json | jq -r '.deployments[0].url'
```

**Method 3: Predictable Domain Pattern**
```
https://pr-{number}-{service-name}.up.railway.app
```

### Orchestrator Pattern for Discovery

```markdown
## Investigation Phase (Orchestrator)

1. **Check GitHub PR Number**:
   ```bash
   gh pr view {pr-number} --json number,headRefName
   ```

2. **Verify Railway Environment Exists**:
   ```bash
   railway environment list | grep "pr-{number}"
   ```

3. **Extract Deployment URL**:
   ```bash
   railway environment pr-{number}
   railway status --json > /tmp/pr-{number}-status.json
   # Read the JSON and extract URL
   ```

4. **Delegate to Worker**:
   Create TaskCreate with discovered URL as ADDITIONAL_CONTEXT
```

---

## 3. Health Check Pattern

### Pre-Validation Health Verification

Before delegating any testing work, orchestrators should verify the PR environment is deployed and responsive.

### Basic Health Check

```bash
# Simple connectivity check
curl -sf https://{pr-env-url}/health || echo "Not ready"

# With timeout
timeout 10s curl -sf https://{pr-env-url}/health
```

### Health Endpoints by Priority

1. **Explicit Health Endpoints**:
   - `/health`
   - `/api/health`
   - `/healthz` (Kubernetes convention)
   - `/.well-known/health`

2. **Fallback to Root**:
   - `/` (expect HTTP 200 or redirect)

### Polling Pattern for Deployment Readiness

```bash
#!/bin/bash
# Wait for PR environment to be ready (max 5 minutes)

PR_URL="https://{pr-env-url}"
MAX_ATTEMPTS=60  # 60 attempts × 5 seconds = 5 minutes
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  if curl -sf "$PR_URL/health" > /dev/null 2>&1; then
    echo "PR environment is ready!"
    exit 0
  fi

  echo "Attempt $((ATTEMPT+1))/$MAX_ATTEMPTS - waiting..."
  sleep 5
  ATTEMPT=$((ATTEMPT+1))
done

echo "ERROR: PR environment failed to become ready within 5 minutes"
exit 1
```

### Checking Deployment Status via Railway

```bash
# List recent deployments for current environment
railway deployment list --json | jq '.deployments[0] | {status, createdAt, url}'

# Get deployment logs if build failed
railway logs --deployment {deployment-id}
```

### Worker Task for Health Check

Orchestrator creates this task for a validation worker:

```markdown
## Task: Verify PR Environment Health

**TARGET_URL**: https://pr-123-myapp.up.railway.app
**TIMEOUT**: 5 minutes

**Validation Steps**:
1. Poll `/health` endpoint until responsive (5s intervals)
2. Verify HTTP 200 status code
3. Check response body contains expected health indicators
4. Record response time (should be < 2s)

**Report Format**:
- Status: PASS/FAIL
- Response time: {ms}
- First successful response: {timestamp}
- Deployment logs: {link if failed}
```

---

## 4. API Validation Pattern

### Orchestrator Creates API Validation Task

The orchestrator delegates API testing to a `backend-solutions-engineer` worker:

```python
TaskCreate(
    subject="Validate PR #123 API Endpoints",
    description="""
## Task: API Validation for PR Environment

**Bead**: claude-harness-setup-{id}
**TARGET_URL**: https://pr-123-myapp.up.railway.app

### Endpoints to Test

#### 1. Health & Status
```
GET /health
Expected: 200 OK
Body: {"status": "healthy"}
```

#### 2. Authentication
```
POST /api/auth/login
Body: {"email": "test@example.com", "password": "testpass123"}
Expected: 200 OK with access_token
Error cases:
- Invalid credentials → 401
- Missing fields → 400
```

#### 3. Protected Endpoints
```
GET /api/protected
Expected: 401 Unauthorized (no token)

GET /api/protected
Headers: {"Authorization": "Bearer {token}"}
Expected: 200 OK with protected data
```

#### 4. CRUD Operations
```
POST /api/resource → 201 Created
GET /api/resource/{id} → 200 OK
PUT /api/resource/{id} → 200 OK
DELETE /api/resource/{id} → 204 No Content
```

### Acceptance Criteria
- All endpoints return expected status codes
- Response bodies match schema expectations
- Error handling works correctly (4xx/5xx)
- Authentication flow completes successfully
- CRUD operations maintain data integrity

### Report Format
For each endpoint, report:
- URL tested
- Status code (expected vs actual)
- Response time
- Pass/Fail status
- Error details if failed

**Tools Available**:
- `curl` for HTTP requests
- `jq` for JSON parsing
- Railway CLI for environment access
    """,
    activeForm="Validating PR API endpoints"
)
```

### cURL Patterns for Common Tests

**GET with JSON parsing**:
```bash
curl -s https://{pr-url}/api/endpoint | jq -e '.status == "success"'
```

**POST with authentication**:
```bash
TOKEN=$(curl -s -X POST https://{pr-url}/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test"}' \
  | jq -r '.access_token')

curl -s https://{pr-url}/api/protected \
  -H "Authorization: Bearer $TOKEN"
```

**Test error handling**:
```bash
# Should return 400
curl -s -w "%{http_code}" -X POST https://{pr-url}/api/resource \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Worker Implementation Pattern

The `backend-solutions-engineer` worker:
1. Reads the task description to get TARGET_URL and test specifications
2. Writes a test script (Bash or Python) to execute all tests
3. Runs the script, capturing results
4. Reports back via SendMessage with structured results

---

## 5. Browser Testing Pattern

### Orchestrator Creates Browser Testing Task

The orchestrator delegates UI validation to a `tdd-test-engineer` worker:

```python
TaskCreate(
    subject="Browser Validation for PR #123 UI",
    description="""
## Task: Browser Testing for PR Environment

**Bead**: claude-harness-setup-{id}
**TARGET_URL**: https://pr-123-myapp.up.railway.app

### Browser Tests Required

#### 1. Page Load Verification
```
- Navigate to TARGET_URL
- Wait for page load event
- Verify no console errors (check browser console)
- Verify page title matches expected value
- Capture screenshot: page-load.png
```

#### 2. Authentication Flow
```
- Click "Login" button
- Fill email: test@example.com
- Fill password: testpass123
- Submit form
- Verify redirect to /dashboard
- Verify "Welcome" message appears
- Capture screenshot: login-success.png
```

#### 3. Interactive Elements
```
- Test navigation menu (click each item)
- Test dropdown functionality
- Test form validation (submit empty form)
- Verify error messages display correctly
- Capture screenshot: validation-errors.png
```

#### 4. Responsive Design
```
- Test at viewport 1920×1080 (desktop)
- Test at viewport 768×1024 (tablet)
- Test at viewport 375×667 (mobile)
- Verify layout adapts correctly
- Capture screenshots for each viewport
```

### Tools to Use
- **browser-mcp** (Chrome DevTools MCP): Use for Chrome automation
- Reference: `chrome-devtools` MCP skill in `.claude/skills/mcp-skills/chrome-devtools/`

### Browser-MCP Pattern
```python
# Example using browser automation
Skill("chrome-devtools", args="navigate https://{pr-url}")
Skill("chrome-devtools", args="screenshot page-load.png")
Skill("chrome-devtools", args="console-errors")
```

### Acceptance Criteria
- All page loads complete without console errors
- Authentication flow works end-to-end
- Interactive elements respond correctly
- Responsive design verified at 3 breakpoints
- Screenshots captured as evidence

### Report Format
- Test name
- Pass/Fail status
- Console errors (if any)
- Screenshot links
- Performance metrics (page load time)
    """,
    activeForm="Browser testing PR environment"
)
```

### Chrome DevTools MCP Skill Reference

The `chrome-devtools` MCP skill provides:
- Page navigation and interaction
- Screenshot capture
- Console log reading
- Network request monitoring
- Performance profiling
- DOM inspection

**Example Commands**:
```bash
# Navigate to page
python ~/.claude/skills/mcp-skills/executor.py --skill chrome-devtools \
  --call '{"tool": "navigate", "arguments": {"url": "https://pr-123.railway.app"}}'

# Capture screenshot
python ~/.claude/skills/mcp-skills/executor.py --skill chrome-devtools \
  --call '{"tool": "screenshot", "arguments": {"path": "screenshot.png"}}'

# Read console errors
python ~/.claude/skills/mcp-skills/executor.py --skill chrome-devtools \
  --call '{"tool": "get_console_messages", "arguments": {}}'
```

---

## 6. GitHub PR Comment Integration

### Posting Validation Results to PR

After collecting results from all workers, the orchestrator posts a consolidated report to the GitHub PR.

### Using the `github` MCP Skill

```python
# Post comment to PR
Skill("github", args="comment pr-123 --body 'Validation results...'")
```

### Using `gh` CLI

```bash
gh pr comment 123 --body "## 🤖 Agent Validation Results

### ✅ API Validation
- Health Check: **PASS** (127ms)
- Authentication: **PASS** (234ms)
- Protected Routes: **PASS** (156ms)
- CRUD Operations: **PASS** (312ms)

### ✅ Browser Testing
- Page Load: **PASS** ([screenshot](https://example.com/page-load.png))
- Login Flow: **PASS** ([screenshot](https://example.com/login.png))
- Responsive Design: **PASS** (3 viewports tested)
- Console Errors: None detected

### 📊 Summary
- **Total Tests**: 12
- **Passed**: 12
- **Failed**: 0
- **Total Time**: 2.3s

🚀 All validations passed! This PR is ready for review.
"
```

### Structured Results Format

```json
{
  "pr_number": 123,
  "environment_url": "https://pr-123-myapp.up.railway.app",
  "validation_timestamp": "2025-01-15T10:30:00Z",
  "tests": [
    {
      "category": "api",
      "name": "Health Check",
      "status": "pass",
      "duration_ms": 127,
      "details": "Endpoint returned 200 OK"
    },
    {
      "category": "browser",
      "name": "Page Load",
      "status": "pass",
      "duration_ms": 1534,
      "evidence": "https://example.com/screenshot.png"
    }
  ],
  "summary": {
    "total": 12,
    "passed": 12,
    "failed": 0,
    "duration_ms": 2300
  }
}
```

### Markdown Template for PR Comments

```markdown
## 🤖 Agent Validation Report

**PR Environment**: https://pr-{number}-{service}.up.railway.app
**Validated**: {timestamp}
**Orchestrator**: {orchestrator-id}

---

### API Validation
| Endpoint | Status | Time | Details |
|----------|--------|------|---------|
| GET /health | ✅ PASS | 127ms | - |
| POST /api/auth/login | ✅ PASS | 234ms | Token received |
| GET /api/protected | ✅ PASS | 156ms | Authorization verified |

### Browser Testing
| Test | Status | Evidence |
|------|--------|----------|
| Page Load | ✅ PASS | [Screenshot](url) |
| Login Flow | ✅ PASS | [Screenshot](url) |
| Responsive Design | ✅ PASS | [Screenshots](url) |

### Performance Metrics
- **First Contentful Paint**: 1.2s
- **Time to Interactive**: 2.1s
- **Total Blocking Time**: 150ms

### Console Errors
None detected ✅

---

**Summary**: All 12 tests passed in 2.3s. PR is validated and ready for review.

<sub>Generated by [orchestrator-{id}] via Railway PR validation pipeline</sub>
```

---

## 7. Orchestrator Workflow (End-to-End)

### Complete PR Validation Workflow

This workflow demonstrates how an orchestrator coordinates the entire validation process from PR detection to result reporting.

### Phase 1: Detection & Setup

```markdown
## Step 1: Detect New PR

**Trigger**: GitHub webhook or scheduled polling

**Actions**:
1. Use `gh pr list --json number,headRefName,updatedAt`
2. Filter for PRs with recent updates (< 5 minutes)
3. Check if PR has a corresponding Railway environment
4. Proceed if environment exists and is deployed
```

### Phase 2: Environment Discovery

```markdown
## Step 2: Discover PR Environment URL

**Investigation** (Orchestrator uses Read/Grep):
```bash
# Get PR details
gh pr view {pr-number} --json number,headRefName,state > /tmp/pr-{number}.json

# Check Railway environment
railway environment list > /tmp/railway-envs.txt
grep "pr-{number}" /tmp/railway-envs.txt

# Extract deployment URL
railway environment pr-{number}
railway status --json > /tmp/pr-{number}-status.json
# Read the JSON to extract URL
```

**Output**: PR_URL stored for delegation to workers
```

### Phase 3: Wait for Deployment

```markdown
## Step 3: Wait for Railway Deployment to Complete

**Orchestrator creates waiting task**:
- Check deployment status every 30s
- Max wait time: 5 minutes
- If build fails → extract logs and report to PR
- If timeout → report failure to PR

**Implementation**:
```bash
for i in {1..10}; do
  STATUS=$(railway status --json | jq -r '.deployments[0].status')
  if [ "$STATUS" = "ACTIVE" ]; then
    echo "Deployment ready"
    break
  fi
  echo "Waiting for deployment... ($i/10)"
  sleep 30
done
```
```

### Phase 4: Health Check Delegation

```markdown
## Step 4: Delegate Health Check

**Orchestrator creates task**:
```python
TaskCreate(
    subject="Health check for PR #{pr-number}",
    description=f"""
    **TARGET_URL**: {pr_url}
    **TASK**: Poll /health endpoint until responsive (max 5 min)
    **REPORT**: Status (PASS/FAIL), response time, timestamp
    """,
    activeForm="Checking PR environment health"
)
```

**Assign to**: validation-test-agent worker

**Wait for**: SendMessage from worker with results
```

### Phase 5: API Validation Delegation

```markdown
## Step 5: Delegate API Validation

**Orchestrator creates task** (see §4 for full pattern):
```python
TaskCreate(
    subject="API validation for PR #{pr-number}",
    description="[Full API test spec from §4]",
    activeForm="Validating PR API endpoints"
)
```

**Assign to**: backend-solutions-engineer worker

**Wait for**: SendMessage with structured results
```

### Phase 6: Browser Testing Delegation

```markdown
## Step 6: Delegate Browser Testing

**Orchestrator creates task** (see §5 for full pattern):
```python
TaskCreate(
    subject="Browser validation for PR #{pr-number}",
    description="[Full browser test spec from §5]",
    activeForm="Browser testing PR environment"
)
```

**Assign to**: tdd-test-engineer worker

**Wait for**: SendMessage with screenshots and results
```

### Phase 7: Results Collection

```markdown
## Step 7: Collect Results from All Workers

**Orchestrator waits for**:
1. Health check completion (validation-test-agent)
2. API validation completion (backend-solutions-engineer)
3. Browser testing completion (tdd-test-engineer)

**Pattern**:
- Workers send SendMessage with results
- Orchestrator aggregates into unified structure
- Determines overall PASS/FAIL status
```

### Phase 8: PR Comment Posting

```markdown
## Step 8: Post Consolidated Results

**Orchestrator action**:
```bash
gh pr comment {pr-number} --body "$(cat <<'EOF'
[Markdown template from §6 with aggregated results]
EOF
)"
```

**Include**:
- Summary table (tests passed/failed)
- Individual test details
- Performance metrics
- Screenshots/evidence links
- Overall recommendation (approve/request changes)
```

### Phase 9: Optional PR Approval

```markdown
## Step 9: Auto-Approve (if configured)

**Conditions for auto-approval**:
- All tests passed
- No console errors
- Performance metrics within thresholds
- PR from authorized contributor

**Action**:
```bash
gh pr review {pr-number} --approve --body "🤖 Automated validation passed. Approved."
```

**Note**: Only enable if team policy allows automated approvals
```

### Phase 10: Failure Handling

```markdown
## Step 10: Handle Failures

**If any test fails**:

1. **Request Changes on PR**:
   ```bash
   gh pr review {pr-number} --request-changes --body "🚨 Validation failed. See details below."
   ```

2. **Post Detailed Failure Report**:
   - Which tests failed
   - Error messages and stack traces
   - Deployment logs (if build failed)
   - Recommendations for fixes

3. **Create Task for Investigation** (optional):
   - If failure is unexpected
   - Orchestrator can spawn investigator worker
   - Worker analyzes logs and provides diagnosis
```

### Complete Orchestrator Script Template

```python
# orchestrator-pr-validation.py
# This would be the workflow an orchestrator follows

import json
import subprocess
import time

def validate_pr(pr_number):
    """Complete PR validation workflow"""

    # Phase 1: Detection
    pr_info = get_pr_info(pr_number)

    # Phase 2: Discovery
    pr_url = discover_pr_url(pr_number)

    # Phase 3: Wait for deployment
    wait_for_deployment(pr_number, max_wait=300)

    # Phase 4-6: Delegate to workers (using Task/SendMessage)
    health_task = create_health_check_task(pr_url)
    api_task = create_api_validation_task(pr_url)
    browser_task = create_browser_testing_task(pr_url)

    # Phase 7: Collect results
    results = collect_worker_results([health_task, api_task, browser_task])

    # Phase 8: Post results
    post_pr_comment(pr_number, results)

    # Phase 9-10: Approve or request changes
    if all_tests_passed(results):
        approve_pr(pr_number)
    else:
        request_changes(pr_number, results)
```

---

## 8. Integration with Existing Skills

### Railway Skills Suite

The harness includes several Railway-specific skills for progressive disclosure:

#### `railway-status` Skill
**Use for**: Checking deployment status, monitoring progress
```python
Skill("railway-status")  # Returns current project/environment status
```

#### `railway-environment` Skill
**Use for**: Listing, switching, and managing Railway environments
```python
Skill("railway-environment", args="list")       # List all environments
Skill("railway-environment", args="use pr-123") # Switch to PR environment
Skill("railway-environment", args="show")       # Show current environment
```

#### `railway-deployment` Skill
**Use for**: Managing deployments, viewing logs, triggering rebuilds
```python
Skill("railway-deployment", args="list")              # List recent deployments
Skill("railway-deployment", args="logs {deploy-id}")  # View deployment logs
```

### MCP Skills for Testing

#### `chrome-devtools` MCP Skill
**Location**: `.claude/skills/mcp-skills/chrome-devtools/`
**Use for**: Browser automation, screenshot capture, console monitoring

**Key Tools**:
- `navigate` - Navigate to URL
- `screenshot` - Capture page screenshot
- `get_console_messages` - Read browser console
- `get_network_requests` - Monitor network traffic
- `evaluate_javascript` - Run JS in page context

**Example**:
```bash
python ~/.claude/skills/mcp-skills/executor.py \
  --skill chrome-devtools \
  --call '{"tool": "navigate", "arguments": {"url": "https://pr-123.railway.app"}}'
```

#### `github` MCP Skill
**Location**: `.claude/skills/mcp-skills/github/`
**Use for**: PR commenting, issue creation, repo management

**Key Tools**:
- `create_pull_request_review` - Submit PR review
- `add_issue_comment` - Add comment to issue/PR
- `get_pull_request` - Get PR details
- `list_commits` - List commits in PR

**Example**:
```bash
python ~/.claude/skills/mcp-skills/executor.py \
  --skill github \
  --call '{"tool": "add_issue_comment", "arguments": {"owner": "myorg", "repo": "myrepo", "issue_number": 123, "body": "Validation results..."}}'
```

#### `playwright` MCP Skill
**Location**: `.claude/skills/mcp-skills/playwright/`
**Use for**: Advanced browser testing, cross-browser validation

**Alternative to chrome-devtools** for more complex testing scenarios.

### Skill Discovery Pattern

```bash
# List all Railway skills
ls -1 ~/.claude/skills/railway-*/SKILL.md

# List all MCP skills
ls -1 ~/.claude/skills/mcp-skills/*/SKILL.md

# Read skill documentation
cat ~/.claude/skills/railway-status/SKILL.md
cat ~/.claude/skills/mcp-skills/github/SKILL.md
```

### Integration Example in Orchestrator

```python
# Orchestrator investigating PR environment
def investigate_pr_environment(pr_number):
    """Use skills to gather environment information"""

    # Step 1: Get GitHub PR details
    Skill("github", args=f"get-pr {pr_number}")

    # Step 2: Check Railway deployment status
    Skill("railway-status")

    # Step 3: Switch to PR environment
    Skill("railway-environment", args=f"use pr-{pr_number}")

    # Step 4: Get deployment URL from Railway
    result = Skill("railway-environment", args="show")
    # Parse result to extract URL

    return pr_url
```

---

## 9. Error Handling

### Common Failure Modes and Resolutions

#### 1. PR Environment Fails to Deploy

**Symptoms**:
- Railway deployment status shows "FAILED"
- Environment URL returns 502/503
- `railway status` shows build errors

**Diagnosis**:
```bash
# Check build logs
railway logs --build

# Check deployment status
railway deployment list --json | jq '.deployments[0] | {status, buildLogs}'

# Check for resource constraints
railway status --json | jq '.resources'
```

**Common Causes**:
- Missing environment variables
- Build script errors
- Resource limits exceeded
- Invalid Railway configuration

**Resolution Steps**:
1. Extract build logs: `railway logs --build > /tmp/build-error.log`
2. Read logs to identify specific error
3. Post build error details to PR comment
4. Request developer to fix build issues
5. Do NOT proceed with validation if build failed

#### 2. Environment Not Found

**Symptoms**:
- `railway environment list` doesn't show `pr-{number}`
- Railway CLI returns "Environment not found"

**Diagnosis**:
```bash
# List all environments
railway environment list

# Check if PR is from authorized contributor
gh pr view {pr-number} --json author,authorAssociation
```

**Common Causes**:
- PR from external fork (Railway doesn't auto-deploy forks)
- Railway GitHub integration not configured
- PR branch not from authorized workspace member
- Environment hasn't been created yet (deployment in progress)

**Resolution Steps**:
1. Check PR author: `gh pr view {pr-number} --json authorAssociation`
2. If external contributor → Post comment explaining manual review required
3. If internal PR → Wait 2 minutes and retry (deployment may be in progress)
4. If still missing → Check Railway dashboard for configuration issues

#### 3. Domain Not Provisioned

**Symptoms**:
- Environment exists but has no public URL
- `railway status` shows no domain
- `railway variables` doesn't include PUBLIC_URL

**Diagnosis**:
```bash
# Check domain settings
railway status --json | jq '.domains'

# Check service configuration
railway variables --json | grep -i url
```

**Common Causes**:
- Service not configured for public exposure
- Domain provisioning in progress
- Railway plan doesn't include custom domains
- Base environment domain misconfigured

**Resolution Steps**:
1. Check if base environment has domain: `railway environment production && railway status`
2. If base has domain, PR environment should inherit pattern
3. If no domain → Contact team to configure Railway service settings
4. As workaround: Use internal railway.app domain if available

#### 4. Test Timeouts

**Symptoms**:
- Health check polls timeout after 5 minutes
- API requests hang indefinitely
- Browser tests fail with timeout errors

**Diagnosis**:
```bash
# Check if environment is responsive at all
timeout 5s curl -v https://{pr-url}/health

# Check Railway service status
railway status --json | jq '.deployments[0] | {status, cpu, memory}'

# Check for deployment crashes
railway logs --tail 50
```

**Common Causes**:
- Service crashed after deployment
- Insufficient resources (CPU/memory)
- Database connection failures
- Cold start delays

**Resolution Steps**:
1. Increase polling interval: 5s → 10s
2. Increase max wait time: 5min → 10min
3. Check resource limits: `railway status --json | jq '.resources'`
4. If consistently timing out → Post logs to PR and request investigation

#### 5. Authentication Failures in Tests

**Symptoms**:
- API tests fail at login step
- All protected endpoint tests fail with 401
- Browser tests can't complete authentication flow

**Diagnosis**:
```bash
# Test authentication manually
curl -X POST https://{pr-url}/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test"}' \
  -v

# Check if test user exists in PR database
# (May need database access)
```

**Common Causes**:
- Test credentials not seeded in PR database
- Authentication service not configured
- Environment variables (JWT_SECRET, etc.) missing
- CORS issues preventing auth requests

**Resolution Steps**:
1. Verify test user credentials in task specification
2. Check if PR environment has seed data: `railway logs | grep seed`
3. Try alternative test credentials (may be documented in repo)
4. If all fail → Skip auth-dependent tests, report to PR

### Error Reporting Template

When posting errors to PR, use this format:

```markdown
## ⚠️ Validation Error

**Environment**: https://pr-{number}-{service}.railway.app
**Error Type**: {Build Failure / Deployment Timeout / Test Failure}
**Timestamp**: {timestamp}

### Error Details
```
{error_message}
{stack_trace or logs}
```

### Diagnosis
{root cause analysis}

### Recommended Actions
1. {action 1}
2. {action 2}

### Logs
<details>
<summary>Full deployment logs</summary>

```
{full logs from railway logs --build}
```
</details>

---

<sub>Validation orchestrator: {orchestrator-id}</sub>
```

---

## 10. Security Considerations

### Threat Model for PR Environments

PR environments can contain malicious code from external contributors. Orchestrators and workers must follow security best practices.

### 1. Validate PR Source Authorization

**Before any validation**, verify the PR is from an authorized contributor:

```bash
# Check PR author association
AUTHOR_ASSOC=$(gh pr view {pr-number} --json authorAssociation -q '.authorAssociation')

# Only validate PRs from these associations
ALLOWED=("OWNER" "MEMBER" "COLLABORATOR")

if [[ ! " ${ALLOWED[@]} " =~ " ${AUTHOR_ASSOC} " ]]; then
    echo "PR from unauthorized contributor: $AUTHOR_ASSOC"
    gh pr comment {pr-number} --body "⚠️ External PRs require manual validation by a maintainer."
    exit 0
fi
```

**Rationale**: External contributors can submit PRs with malicious code designed to:
- Steal environment variables
- Exfiltrate secrets
- Attack validation infrastructure
- Mine cryptocurrency

### 2. Use Read-Only API Tokens

When testing authenticated endpoints, use tokens with minimal privileges:

```bash
# Generate read-only test token (example)
TEST_TOKEN=$(curl -s -X POST https://{pr-url}/api/auth/test-token \
  -H "Content-Type: application/json" \
  -d '{"scope": "read"}')

# Use for validation only
curl https://{pr-url}/api/protected \
  -H "Authorization: Bearer $TEST_TOKEN"
```

**Never use**:
- Production API keys
- Admin tokens
- Tokens with write/delete permissions

### 3. Isolate Browser Testing

Browser-based validation can execute arbitrary JavaScript:

```bash
# Run browser tests in isolated container (if using Docker)
docker run --rm \
  --network none \
  --read-only \
  --tmpfs /tmp \
  playwright-runner \
  npx playwright test {pr-url}
```

**Best practices**:
- Disable network access after page load (if possible)
- Don't persist cookies/local storage between tests
- Clear browser data after each test run
- Monitor for suspicious network requests

### 4. Environment Variable Protection

Railway PR environments inherit some environment variables from the base environment:

```bash
# Check what variables are exposed
railway environment pr-{number}
railway variables --json

# Look for sensitive variables that shouldn't be in PR envs
SENSITIVE=("DATABASE_URL" "API_SECRET" "STRIPE_KEY")

for var in "${SENSITIVE[@]}"; do
  if railway variables | grep -q "$var"; then
    echo "WARNING: Sensitive variable $var exposed in PR environment"
  fi
done
```

**Recommendation**: Configure Railway to use separate databases/services for PR environments.

### 5. Limit Validation Timeout

Malicious PRs might deploy services designed to keep validation hanging:

```bash
# Always enforce maximum timeouts
timeout 10m validate-pr.sh {pr-number}

if [ $? -eq 124 ]; then
  echo "Validation timed out after 10 minutes"
  gh pr comment {pr-number} --body "⏱️ Validation timeout exceeded. Manual review required."
fi
```

### 6. Clean Up Environments Promptly

Don't leave PR environments running indefinitely:

```bash
# After validation completes (pass or fail)
railway environment pr-{number}
railway environment delete --yes

# Or set auto-cleanup policy in Railway dashboard
```

**Benefits**:
- Reduces cost (Railway charges per active environment)
- Limits attack surface
- Prevents resource exhaustion

### 7. Monitor for Suspicious Behavior

Log all validation activities and monitor for anomalies:

```bash
# Log validation start
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [PR-{pr-number}] Validation started by orchestrator-{id}" \
  >> ~/.claude/logs/pr-validation.log

# Log all HTTP requests
curl https://{pr-url}/api/endpoint 2>&1 | tee -a ~/.claude/logs/pr-{pr-number}-requests.log

# Alert on suspicious patterns
if grep -q "Authorization: Bearer" ~/.claude/logs/pr-{pr-number}-requests.log; then
  echo "WARNING: Token may have been logged"
fi
```

### 8. Code Review Before Validation

For PRs from new contributors or large changes:

```bash
# Check PR size
FILES_CHANGED=$(gh pr view {pr-number} --json files -q '.files | length')
LINES_CHANGED=$(gh pr view {pr-number} --json additions,deletions \
  -q '(.additions + .deletions)')

if [ $FILES_CHANGED -gt 50 ] || [ $LINES_CHANGED -gt 1000 ]; then
  gh pr comment {pr-number} --body "⚠️ Large PR detected. Manual review required before automated validation."
  exit 0
fi
```

### Security Checklist for Orchestrators

Before delegating validation tasks, verify:

- [ ] PR is from authorized contributor (OWNER/MEMBER/COLLABORATOR)
- [ ] PR changes have been reviewed by a human (for large PRs)
- [ ] Test credentials are read-only / limited scope
- [ ] Timeouts are enforced on all operations
- [ ] Sensitive environment variables are not exposed
- [ ] Validation runs in isolated environment (if possible)
- [ ] PR environment will be deleted after validation
- [ ] All validation activities are logged

---

## Conclusion

This guide provides comprehensive patterns for agent-driven PR validation using Railway environments. Key principles:

1. **Orchestrators discover, workers validate** - Maintain the investigation vs. implementation boundary
2. **Progressive disclosure** - Use skills to reduce context usage
3. **Structured delegation** - Create clear, detailed tasks for specialist workers
4. **Evidence-based reporting** - Include screenshots, logs, and metrics
5. **Security first** - Validate PR source, limit permissions, clean up promptly

By following these patterns, orchestrators can coordinate sophisticated CI/CD validation workflows while delegating all implementation details to specialist workers.

---

**Document Statistics**:
- **Word Count**: ~6,500 words
- **Sections**: 10 (as required)
- **Code Examples**: 50+
- **Integration Points**: 8 skills/tools referenced
- **Security Considerations**: 8 threat mitigations

**Related Documentation**:
- Railway Skills: `.claude/skills/railway-*/SKILL.md`
- Chrome DevTools MCP: `.claude/skills/mcp-skills/chrome-devtools/SKILL.md`
- GitHub MCP: `.claude/skills/mcp-skills/github/SKILL.md`
- Agent Hierarchy: `.claude/CLAUDE.md`

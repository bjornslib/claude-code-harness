# Railway PR Environment Setup Guide

## Overview

Railway PR (Pull Request) environments allow you to automatically create ephemeral deployments for each pull request in your GitHub repository. This enables preview deployments for code review, testing, and demonstration before merging to production.

## What Are PR Environments?

PR environments are temporary, isolated Railway environments that:
- Automatically deploy when a PR is created
- Update when new commits are pushed to the PR
- Are destroyed when the PR is closed or merged
- Have their own configuration, domains, and resources
- Can be configured to include automated bots (Dependabot, Renovate)

## Prerequisites

- Railway CLI v4.27.3 or higher (check with `railway --version`)
- GitHub repository connected to your Railway project
- Railway project with at least one service
- Appropriate Railway role permissions (Editor or Admin)

## Enable PR Deploys

### Option 1: Via GraphQL API

Get your project ID first:
```bash
railway status --json
```

Enable PR deploys using the Railway API:
```bash
bash <<'SCRIPT'
scripts/railway-api.sh \
  'mutation updateProject($id: String!, $input: ProjectUpdateInput!) {
    projectUpdate(id: $id, input: $input) {
      name
      prDeploys
      isPublic
      botPrEnvironments
    }
  }' \
  '{"id": "YOUR_PROJECT_ID", "input": {"prDeploys": true}}'
SCRIPT
```

### Option 2: Via Railway Dashboard

1. Navigate to your project in the Railway dashboard
2. Go to Project Settings
3. Enable "PR Deploys" toggle
4. (Optional) Enable "Bot PR Environments" for Dependabot/Renovate

## Configuration

### Basic PR Environment Settings

PR environments inherit configuration from your base environment (usually `production`). You can customize this behavior:

**ProjectUpdateInput Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `prDeploys` | Boolean | Enable/disable PR deploys |
| `botPrEnvironments` | Boolean | Enable Dependabot/Renovate PR environments |

### Duplicate Production Environment for PR Template

Create a staging environment to use as a PR template:
```bash
railway environment new staging --duplicate production
```

With service-specific variables for the PR template:
```bash
railway environment new pr-template --duplicate production \
  --service-variable api PORT=3001 \
  --service-variable web NODE_ENV=preview
```

### Configure PR Environment Variables

PR environments often need different configuration than production. Use the `environment` skill to set PR-specific variables:

```bash
railway environment edit -m "add PR environment vars" --json <<< '{
  "services": {
    "SERVICE_ID": {
      "variables": {
        "NODE_ENV": {"value": "preview"},
        "ENABLE_DEBUG": {"value": "true"},
        "FEATURE_FLAGS": {"value": "experimental"}
      }
    }
  }
}'
```

### Set Up Service Domains for PRs

PR environments automatically get Railway-provided domains. To configure custom domain patterns:

```bash
railway environment edit --json <<< '{
  "services": {
    "SERVICE_ID": {
      "networking": {
        "serviceDomains": {
          "pr-{{ PR_NUMBER }}": {
            "path": "/"
          }
        }
      }
    }
  }
}'
```

## Workflow

### Typical PR Environment Lifecycle

1. **PR Created**: Railway detects the new PR and creates an environment
2. **Initial Deploy**: First deployment starts automatically
3. **Code Updates**: Each push to the PR branch triggers a redeploy
4. **Testing**: Use the PR environment URL for testing and review
5. **PR Merged/Closed**: Environment is automatically destroyed

### Monitoring PR Deployments

List deployments for a PR environment:
```bash
railway deployment list --environment pr-123 --json
```

View logs from a PR deployment:
```bash
railway logs --environment pr-123 --latest --lines 100 --json
```

Check deployment status:
```bash
railway status --json
```

## Best Practices

### 1. Use Environment Variables for Feature Flags

Enable experimental features only in PR environments:
```bash
# In PR environments
ENABLE_EXPERIMENTAL=true

# In production
ENABLE_EXPERIMENTAL=false
```

### 2. Isolate PR Environment Data

Use separate databases or database schemas for PR environments:
```bash
railway environment edit --json <<< '{
  "sharedVariables": {
    "DATABASE_URL": {
      "value": "${{DATABASE_PR.DATABASE_URL}}"
    }
  }
}'
```

### 3. Set Resource Limits

PR environments don't need production-scale resources:
```bash
railway environment edit --json <<< '{
  "services": {
    "SERVICE_ID": {
      "deploy": {
        "multiRegionConfig": {
          "us-west2": {
            "numReplicas": 1
          }
        }
      }
    }
  }
}'
```

### 4. Configure Health Checks

Ensure PR deployments are healthy before marking as ready:
```bash
railway environment edit --json <<< '{
  "services": {
    "SERVICE_ID": {
      "deploy": {
        "healthcheckPath": "/health",
        "healthcheckTimeout": 300
      }
    }
  }
}'
```

### 5. Enable Bot PR Environments Selectively

Only enable bot PR environments if you actively use Dependabot or Renovate and want to test dependency updates:
```bash
scripts/railway-api.sh \
  'mutation updateProject($id: String!, $input: ProjectUpdateInput!) {
    projectUpdate(id: $id, input: $input) { botPrEnvironments }
  }' \
  '{"id": "PROJECT_ID", "input": {"botPrEnvironments": true}}'
```

## Troubleshooting

### PR Environment Not Created

**Symptoms:** No environment created when PR is opened

**Solutions:**
1. Verify PR deploys are enabled:
   ```bash
   railway status --json
   ```
   Check `project.prDeploys` field

2. Ensure repository is connected:
   ```bash
   railway environment config --json
   ```
   Verify `source.repo` is set

3. Check Railway GitHub App permissions in repository settings

### Deployment Failures in PR Environment

**Symptoms:** PR deployment fails but production works

**Solutions:**
1. Check deployment logs:
   ```bash
   railway logs --environment pr-123 --latest --build --lines 100 --json
   ```

2. Verify environment variables are correctly set:
   ```bash
   railway environment config --environment pr-123 --json
   ```

3. Check for missing shared variables:
   ```bash
   railway variables --environment pr-123 --json
   ```

### PR Environment Not Destroyed

**Symptoms:** Environment persists after PR is closed

**Solutions:**
1. Manually remove the environment:
   ```bash
   railway environment delete pr-123
   ```

2. Check Railway GitHub webhook status in repository settings

3. Verify Railway App has permission to receive PR events

### Resource Exhaustion

**Symptoms:** Too many PR environments consuming resources

**Solutions:**
1. Disable bot PR environments:
   ```bash
   scripts/railway-api.sh \
     'mutation updateProject($id: String!, $input: ProjectUpdateInput!) {
       projectUpdate(id: $id, input: $input) { botPrEnvironments }
     }' \
     '{"id": "PROJECT_ID", "input": {"botPrEnvironments": false}}'
   ```

2. Set resource limits per service (see Best Practices #3)

3. Implement automatic cleanup for stale PR environments

## Advanced Patterns

### Conditional Services in PR Environments

Deploy only specific services in PR environments:
```bash
railway environment edit --json <<< '{
  "services": {
    "FRONTEND_SERVICE_ID": {
      "source": {"repo": "owner/repo", "branch": "${{ PR_BRANCH }}"}
    },
    "BACKEND_SERVICE_ID": {
      "isDeleted": true
    }
  }
}'
```

### Database Seeding for PR Environments

Create a seed script that runs only in PR environments:
```bash
# In your package.json or deployment script
if [ "$RAILWAY_ENVIRONMENT" = "pr-*" ]; then
  npm run db:seed
fi
```

### Integration with CI/CD

Trigger additional testing when PR environment is ready:
```yaml
# .github/workflows/pr-test.yml
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  e2e-test:
    runs-on: ubuntu-latest
    steps:
      - name: Wait for Railway deployment
        run: |
          # Wait for deployment to complete
          railway deployment list --environment pr-${{ github.event.pull_request.number }} --json

      - name: Run E2E tests
        run: |
          export TEST_URL="https://pr-${{ github.event.pull_request.number }}.railway.app"
          npm run test:e2e
```

## Related Skills

- **railway-environment**: Configure variables, build settings, and deploy settings
- **railway-deployment**: View logs, redeploy, or remove deployments
- **railway-status**: Check project, environment, and service status
- **railway-domain**: Add custom domains to PR environments
- **railway-service**: Manage services within PR environments

## References

- [Railway Environment Configuration Reference](references/environment-config.md)
- [Railway Variables Reference](references/variables.md)
- [Railway Deployment Management](../skills/railway-deployment/SKILL.md)
- [Railway Project Management](../skills/railway-projects/SKILL.md)

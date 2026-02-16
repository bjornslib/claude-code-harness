#!/usr/bin/env node
/**
 * Sync Task Master tasks.json → {project-name}-feature_list.json
 *
 * Purpose: One-way generation of execution state from planning state
 * - Task Master owns: Structure, dependencies, test strategies
 * - Orchestrator owns: Execution state, worker assignment, validation results
 *
 * Usage: node .claude/skills/orchestrator-multiagent/sync-taskmaster-to-features.js [--dry-run] [--output=path]
 *
 * Examples:
 *   --output=.claude/state/room-instantiation-parameterization-feature_list.json
 *   --output=.claude/state/my-project-feature_list.json
 *
 * IMPORTANT: Always specify --output with project-specific filename to avoid collisions
 */

const fs = require('fs');
const path = require('path');

// Configuration
const CONFIG = {
  TASKS_PATH: '.taskmaster/tasks/tasks.json',
  FEATURES_PATH: '.claude/state/feature_list.json',
  BACKUP_DIR: '.claude/state/backups',
};

// Parse CLI arguments
const args = process.argv.slice(2);
const isDryRun = args.includes('--dry-run');
const outputArg = args.find(arg => arg.startsWith('--output='));
const customOutputPath = outputArg ? outputArg.split('=')[1] : null;

// Utility functions
function loadJSON(filepath) {
  try {
    const content = fs.readFileSync(filepath, 'utf8');
    return JSON.parse(content);
  } catch (error) {
    if (error.code === 'ENOENT') {
      console.log(`ℹ️  File not found: ${filepath}`);
      return null;
    }
    throw error;
  }
}

function saveJSON(filepath, data) {
  const dir = path.dirname(filepath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(filepath, JSON.stringify(data, null, 2) + '\n');
}

function createBackup(filepath) {
  if (!fs.existsSync(filepath)) return null;

  const backupDir = CONFIG.BACKUP_DIR;
  if (!fs.existsSync(backupDir)) {
    fs.mkdirSync(backupDir, { recursive: true });
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
  const filename = path.basename(filepath, '.json');
  const backupPath = path.join(backupDir, `${filename}-${timestamp}.json`);

  fs.copyFileSync(filepath, backupPath);
  return backupPath;
}

// Mapping functions
function taskToFeature(task, index, allTasks) {
  const featureId = generateFeatureId(task.id);

  return {
    id: featureId,
    task_id: task.id, // Link back to Task Master

    // Structure from Task Master
    description: task.title || task.description || '',
    steps: extractSteps(task),
    dependencies: mapDependencies(task.dependencies || [], allTasks),

    // Test metadata from Task Master
    test_strategy: task.testStrategy || task.test_strategy || '',
    acceptance_criteria: extractAcceptanceCriteria(task),

    // Orchestrator-specific fields (generated from Task Master data)
    scope: extractScope(task),
    validation: extractValidation(task),
    worker_type: inferWorkerType(task),

    // Execution state (default values, will be preserved if feature exists)
    passes: task.status === 'done',
    worker_assigned: null,
    started_at: null,
    completed_at: null,
    validation_result: null,
    git_worktree: null,
  };
}

function generateFeatureId(taskId) {
  // Convert Task Master ID format to Feature ID format
  // "1" → "F001"
  // "1.1" → "F001.1"
  // "1.2.3" → "F001.2.3"

  const parts = String(taskId).split('.');
  const mainId = parseInt(parts[0]);
  const featureMainId = `F${String(mainId).padStart(3, '0')}`;

  if (parts.length === 1) {
    return featureMainId;
  }

  return `${featureMainId}.${parts.slice(1).join('.')}`;
}

function extractSteps(task) {
  // Extract implementation steps from task details
  const details = task.details || '';

  if (!details) return [];

  // Look for numbered lists or bullet points
  const lines = details.split('\n');
  const steps = [];

  for (const line of lines) {
    const trimmed = line.trim();
    // Match: "1. Step", "- Step", "* Step"
    if (trimmed.match(/^(\d+\.|\-|\*)\s+(.+)$/)) {
      const step = trimmed.replace(/^(\d+\.|\-|\*)\s+/, '');
      if (step && !step.toLowerCase().startsWith('test') && !step.toLowerCase().startsWith('validate')) {
        steps.push(step);
      }
    }
  }

  return steps.length > 0 ? steps : [task.description || task.title];
}

function extractScope(task) {
  // Extract file scope from task details
  const details = task.details || '';
  const scope = [];

  // Look for file patterns
  const filePatterns = [
    /(?:files?|modify|edit|update|create):\s*([^\n]+)/gi,
    /(?:path|location):\s*([^\n]+)/gi,
    /`([^`]+\.(ts|tsx|js|jsx|py|sql|md))`/gi,
    /(?:^|\s)([a-zA-Z0-9_\-\/]+\/[a-zA-Z0-9_\-\/]+\.(ts|tsx|js|jsx|py|sql|md))/gi,
  ];

  for (const pattern of filePatterns) {
    const matches = details.matchAll(pattern);
    for (const match of matches) {
      const file = match[1].trim();
      if (file && !scope.includes(file)) {
        scope.push(file);
      }
    }
  }

  // Infer scope from task title/description
  const text = (task.title + ' ' + (task.description || '')).toLowerCase();

  if (text.includes('hook') || text.includes('usevectorsearch')) {
    scope.push('app/university-contacts/hooks/');
  }
  if (text.includes('component') || text.includes('ui')) {
    scope.push('app/university-contacts/components/');
  }
  if (text.includes('api') || text.includes('endpoint')) {
    scope.push('app/api/');
  }
  if (text.includes('type') || text.includes('interface')) {
    scope.push('app/university-contacts/lib/types/');
  }

  return scope;
}

function extractValidation(task) {
  // Extract validation command from test strategy
  const strategy = (task.testStrategy || task.test_strategy || '').toLowerCase();
  const details = (task.details || '').toLowerCase();
  const combined = strategy + ' ' + details;

  // Detect test type and command
  if (combined.includes('playwright') || combined.includes('e2e') || combined.includes('chrome-devtools')) {
    return {
      type: 'browser',
      command: 'npm run test:e2e -- --grep "search flow"',
      timeout: 30000
    };
  }

  if (combined.includes('jest') || combined.includes('unit test')) {
    return {
      type: 'unit',
      command: 'npm test -- --testNamePattern="search"',
      timeout: 10000
    };
  }

  if (combined.includes('integration') || combined.includes('api test')) {
    return {
      type: 'api',
      command: 'curl -X POST http://localhost:8000/api/search/universities',
      timeout: 5000
    };
  }

  if (combined.includes('pytest') || combined.includes('python')) {
    return {
      type: 'unit',
      command: 'pytest tests/',
      timeout: 10000
    };
  }

  // Default: manual validation
  return {
    type: 'manual',
    command: '',
    timeout: 0
  };
}

function inferWorkerType(task) {
  // Infer worker from task description and scope
  const text = (task.title + ' ' + (task.description || '') + ' ' + (task.details || '')).toLowerCase();

  // Frontend patterns
  if (text.match(/react|component|hook|ui|ux|frontend|tailwind|next\.js|typescript|tsx|css|style|animation/)) {
    return 'frontend-dev-expert';
  }

  // Backend patterns
  if (text.match(/api|backend|python|fastapi|endpoint|server|database|supabase|sql|migration|vector|faiss/)) {
    return 'backend-solutions-engineer';
  }

  // Testing patterns
  if (text.match(/test|e2e|playwright|jest|pytest|validation/)) {
    return 'tdd-test-engineer';
  }

  // Documentation patterns
  if (text.match(/documentation|readme|docs|guide/)) {
    return 'general-purpose';
  }

  // Default
  return 'general-purpose';
}

function mapDependencies(taskDeps, allTasks) {
  // Convert Task Master task IDs to feature IDs
  return taskDeps
    .map(depId => {
      // Validate dependency exists
      const depTask = allTasks.find(t => String(t.id) === String(depId));
      if (!depTask) {
        console.warn(`⚠️  Dependency ${depId} not found in tasks`);
        return null;
      }
      return generateFeatureId(depId);
    })
    .filter(Boolean);
}

function extractAcceptanceCriteria(task) {
  // Extract Given/When/Then from details or description
  const details = task.details || task.description || '';
  const criteria = [];

  const lines = details.split('\n');
  let currentCriterion = null;

  for (const line of lines) {
    const trimmed = line.trim();

    // Match: "Given:", "When:", "Then:", or continuation
    if (trimmed.match(/^(given|when|then):/i)) {
      if (currentCriterion) {
        criteria.push(currentCriterion);
      }
      currentCriterion = trimmed;
    } else if (currentCriterion && trimmed && !trimmed.startsWith('#')) {
      // Continuation of previous criterion
      currentCriterion += ' ' + trimmed;
    }
  }

  if (currentCriterion) {
    criteria.push(currentCriterion);
  }

  // Also look for acceptance criteria in test strategy
  const testStrategy = task.testStrategy || task.test_strategy || '';
  const acceptanceMatches = testStrategy.matchAll(/acceptance:([^\n]+)/gi);
  for (const match of acceptanceMatches) {
    criteria.push(match[1].trim());
  }

  return criteria.length > 0 ? criteria : null;
}

function mergeWithExisting(newFeature, existingFeature) {
  // Preserve execution state from existing feature
  // Update structure from Task Master
  return {
    ...newFeature,

    // Preserve execution state (orchestrator domain)
    passes: existingFeature.passes,
    worker_assigned: existingFeature.worker_assigned || null,
    started_at: existingFeature.started_at || null,
    completed_at: existingFeature.completed_at || null,
    validation_result: existingFeature.validation_result || null,
    git_worktree: existingFeature.git_worktree || null,
  };
}

// Main execution
function main() {
  console.log('🔄 Syncing Task Master → Orchestrator Feature List\n');

  // Load tasks.json
  console.log(`📖 Reading: ${CONFIG.TASKS_PATH}`);
  const tasksData = loadJSON(CONFIG.TASKS_PATH);

  if (!tasksData) {
    console.error('❌ Error: tasks.json not found or invalid');
    process.exit(1);
  }

  // Extract tasks array (handle different Task Master formats)
  let tasks = [];
  const tag = process.env.TASK_MASTER_TAG || 'master'; // Default to 'master' tag

  if (Array.isArray(tasksData)) {
    tasks = tasksData;
  } else if (tasksData[tag] && Array.isArray(tasksData[tag].tasks)) {
    // Task Master v0.37+ uses tag-based structure: { master: { tasks: [...] } }
    tasks = tasksData[tag].tasks;
  } else if (tasksData.tasks && Array.isArray(tasksData.tasks)) {
    // Older format: { tasks: [...] }
    tasks = tasksData.tasks;
  } else if (typeof tasksData === 'object') {
    // Task Master might store tasks as object with numeric keys
    tasks = Object.values(tasksData).filter(t => t && t.id);
  }

  console.log(`   Found ${tasks.length} tasks\n`);

  // Load existing feature_list.json (if exists)
  const outputPath = customOutputPath || CONFIG.FEATURES_PATH;
  console.log(`📖 Reading existing features: ${outputPath}`);
  const existingFeaturesData = loadJSON(outputPath);
  const existingFeatures = Array.isArray(existingFeaturesData) ? existingFeaturesData : [];
  console.log(`   Found ${existingFeatures.length} existing features\n`);

  // Create backup if not dry run
  if (!isDryRun && existingFeatures.length > 0) {
    const backupPath = createBackup(outputPath);
    if (backupPath) {
      console.log(`💾 Backup created: ${backupPath}\n`);
    }
  }

  // Build feature map from tasks
  console.log('🔨 Mapping tasks to features...\n');
  const newFeatures = tasks.map((task, idx) => {
    const newFeature = taskToFeature(task, idx, tasks);

    // Check if feature already exists (by task_id)
    const existing = existingFeatures.find(f => f.task_id === task.id);

    if (existing) {
      console.log(`   ♻️  ${newFeature.id}: Updating structure, preserving state`);
      return mergeWithExisting(newFeature, existing);
    } else {
      console.log(`   ✨ ${newFeature.id}: New feature from task ${task.id}`);
      return newFeature;
    }
  });

  console.log(`\n✅ Generated ${newFeatures.length} features\n`);

  // Summary
  console.log('📊 Summary:');
  console.log(`   Total features: ${newFeatures.length}`);
  console.log(`   New features: ${newFeatures.filter(f => !existingFeatures.find(e => e.task_id === f.task_id)).length}`);
  console.log(`   Updated features: ${newFeatures.filter(f => existingFeatures.find(e => e.task_id === f.task_id)).length}`);
  console.log(`   Frontend tasks: ${newFeatures.filter(f => f.worker_type === 'frontend-dev-expert').length}`);
  console.log(`   Backend tasks: ${newFeatures.filter(f => f.worker_type === 'backend-solutions-engineer').length}`);
  console.log(`   Test tasks: ${newFeatures.filter(f => f.worker_type === 'tdd-test-engineer').length}`);
  console.log(`   Other tasks: ${newFeatures.filter(f => f.worker_type === 'general-purpose').length}`);
  console.log('');

  // Validation
  console.log('🔍 Validation:');
  const invalidDeps = newFeatures.filter(f =>
    f.dependencies.some(depId => !newFeatures.find(nf => nf.id === depId))
  );
  if (invalidDeps.length > 0) {
    console.log(`   ⚠️  ${invalidDeps.length} features have invalid dependencies`);
    invalidDeps.forEach(f => {
      console.log(`      - ${f.id}: ${f.dependencies.join(', ')}`);
    });
  } else {
    console.log(`   ✅ All dependencies valid`);
  }
  console.log('');

  // Save or preview
  if (isDryRun) {
    console.log('🔍 DRY RUN - No files modified\n');
    console.log('Preview (first 3 features):');
    console.log(JSON.stringify(newFeatures.slice(0, 3), null, 2));
  } else {
    saveJSON(outputPath, newFeatures);
    console.log(`💾 Saved: ${outputPath}\n`);
    console.log('✅ Sync complete!\n');
    console.log('Next steps:');
    console.log(`   1. Review: git diff ${outputPath}`);
    console.log(`   2. Validate: cat ${outputPath} | jq "."`);
    console.log('   3. Use: Orchestrator skill Phase 2 (Incremental Progress)');
  }
}

// Execute
try {
  main();
} catch (error) {
  console.error('❌ Error:', error.message);
  console.error(error.stack);
  process.exit(1);
}

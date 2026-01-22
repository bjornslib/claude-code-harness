#!/usr/bin/env node
/**
 * Sync Task Master tasks.json → Beads
 *
 * Purpose: Convert planning tasks to execution-ready beads
 * - Task Master owns: Structure, dependencies, test strategies
 * - Beads owns: Execution state, dependency graph, ready detection
 *
 * IMPORTANT: Run from zenagent/ root (not agencheck/) to use the correct .beads database.
 *
 * Usage: node agencheck/.claude/skills/orchestrator-multiagent/scripts/sync-taskmaster-to-beads.js [options]
 *
 * Options:
 *   --dry-run                  Show what would be done without making changes
 *   --tasks-path=<path>        Path to tasks.json (default: .taskmaster/tasks/tasks.json)
 *   --uber-epic=<beads-id>     Link all tasks to this uber-epic via parent-child
 *   --from-id=<id>             Only sync tasks with ID >= this value
 *   --to-id=<id>               Only sync tasks with ID <= this value
 *
 * After sync:
 *   - Creates beads with description, design, and acceptance criteria
 *   - Links all beads to uber-epic via parent-child dependency
 *   - Sets up task dependencies in beads
 *   - Closes synced tasks in Task Master (status=done)
 *
 * Examples:
 *   # From zenagent/ root:
 *   node agencheck/.claude/skills/orchestrator-multiagent/scripts/sync-taskmaster-to-beads.js \
 *       --uber-epic=agencheck-001 --from-id=171 --to-id=210 \
 *       --tasks-path=agencheck/.taskmaster/tasks/tasks.json
 */

const { execSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Configuration
const CONFIG = {
  TASKS_PATH: '.taskmaster/tasks/tasks.json',
  BEADS_DIR: '.beads',
};

// Parse CLI arguments
const args = process.argv.slice(2);
const isDryRun = args.includes('--dry-run');
const tasksPathArg = args.find(arg => arg.startsWith('--tasks-path='));
const customTasksPath = tasksPathArg ? tasksPathArg.split('=')[1] : null;
const uberEpicArg = args.find(arg => arg.startsWith('--uber-epic='));
const uberEpicId = uberEpicArg ? uberEpicArg.split('=')[1] : null;
const fromIdArg = args.find(arg => arg.startsWith('--from-id='));
const toIdArg = args.find(arg => arg.startsWith('--to-id='));
const fromId = fromIdArg ? parseInt(fromIdArg.split('=')[1], 10) : null;
const toId = toIdArg ? parseInt(toIdArg.split('=')[1], 10) : null;

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

function runBd(command, dryRun = false) {
  const fullCommand = `bd ${command}`;
  if (dryRun) {
    console.log(`  [DRY RUN] ${fullCommand}`);
    return { success: true, output: 'dry-run-placeholder' };
  }
  try {
    const result = spawnSync('bd', command.split(' ').filter(Boolean), {
      encoding: 'utf8',
      shell: true,
    });
    if (result.error) {
      console.error(`  ❌ Command failed: ${fullCommand}`);
      console.error(`     ${result.error.message}`);
      return { success: false, output: '' };
    }
    if (result.status !== 0) {
      console.error(`  ❌ Command failed: ${fullCommand}`);
      console.error(`     ${result.stderr || result.stdout}`);
      return { success: false, output: '' };
    }
    return { success: true, output: (result.stdout || '').trim() };
  } catch (error) {
    console.error(`  ❌ Command failed: ${fullCommand}`);
    console.error(`     ${error.message}`);
    return { success: false, output: '' };
  }
}

function checkBeadsInstalled() {
  try {
    const result = spawnSync('bd', ['--version'], { encoding: 'utf8', shell: true });
    return result.status === 0;
  } catch {
    return false;
  }
}

function inferPriority(task) {
  // Map Task Master priority to Beads P0-P3
  const priority = task.priority || 'medium';
  const priorityMap = {
    'high': 0,
    'medium': 1,
    'low': 2,
    'optional': 3
  };
  if (typeof priority === 'number') {
    return Math.min(Math.max(priority, 0), 3);
  }
  return priorityMap[String(priority).toLowerCase()] ?? 1;
}

function inferWorkerType(task) {
  const text = (
    (task.title || '') + ' ' +
    (task.description || '') + ' ' +
    (task.details || '')
  ).toLowerCase();

  if (text.match(/react|component|hook|ui|ux|frontend|tailwind|next\.js|typescript|tsx|css|style/)) {
    return 'frontend-dev-expert';
  }
  if (text.match(/api|backend|python|fastapi|endpoint|server|database|supabase|sql|vector|faiss|pydantic/)) {
    return 'backend-solutions-engineer';
  }
  if (text.match(/test|e2e|playwright|jest|pytest|validation|spec/)) {
    return 'tdd-test-engineer';
  }
  return 'general-purpose';
}

function extractValidationType(task) {
  const strategy = (task.testStrategy || task.test_strategy || '').toLowerCase();
  const details = (task.details || '').toLowerCase();
  const combined = strategy + ' ' + details;

  if (combined.includes('playwright') || combined.includes('e2e') || combined.includes('browser') || combined.includes('chrome-devtools')) {
    return 'browser';
  }
  if (combined.includes('api') || combined.includes('curl') || combined.includes('integration') || combined.includes('endpoint')) {
    return 'api';
  }
  if (combined.includes('jest') || combined.includes('pytest') || combined.includes('unit') || combined.includes('vitest')) {
    return 'unit';
  }
  return 'manual';
}

function extractScope(task) {
  const details = task.details || '';
  const scope = [];

  // Look for file patterns
  const filePatterns = [
    /`([^`]+\.(ts|tsx|js|jsx|py|sql|md))`/gi,
    /(?:^|\s)([a-zA-Z0-9_\-\/]+\/[a-zA-Z0-9_\-\/]+\.(ts|tsx|js|jsx|py|sql|md))/gi,
    /(?:files?|modify|edit|update|create):\s*([^\n]+)/gi,
  ];

  for (const pattern of filePatterns) {
    const matches = details.matchAll(pattern);
    for (const match of matches) {
      const file = match[1].trim();
      if (file && !scope.includes(file) && file.length < 200) {
        scope.push(file);
      }
    }
  }

  return scope;
}

function extractSteps(task) {
  const details = task.details || '';

  if (!details) return [];

  const lines = details.split('\n');
  const steps = [];

  for (const line of lines) {
    const trimmed = line.trim();
    // Match: "1. Step", "- Step", "* Step"
    if (trimmed.match(/^(\d+\.|\-|\*)\s+(.+)$/)) {
      const step = trimmed.replace(/^(\d+\.|\-|\*)\s+/, '');
      if (step && step.length < 500) {
        steps.push(step);
      }
    }
  }

  return steps.slice(0, 10); // Limit to 10 steps
}

// Main sync logic
function syncTasksToBeads(tasks, isDryRun) {
  console.log('🔄 Syncing Task Master → Beads\n');

  // Track created beads for dependency mapping
  const taskToBeadId = new Map();
  const createdBeads = [];

  // First pass: Create all beads
  console.log('📝 Creating beads...\n');

  for (const task of tasks) {
    const title = (task.title || task.description || `Task ${task.id}`).slice(0, 200);
    const priority = inferPriority(task);
    const workerType = inferWorkerType(task);
    const validationType = extractValidationType(task);
    const scope = extractScope(task);
    const steps = extractSteps(task);

    // Build metadata JSON
    const metadata = {
      task_id: String(task.id),
      worker_type: workerType,
      validation_type: validationType,
      scope: scope,
      steps: steps,
      test_strategy: (task.testStrategy || task.test_strategy || '').slice(0, 500),
    };

    // Escape the title for shell
    const escapedTitle = title.replace(/"/g, '\\"').replace(/`/g, '\\`');

    // Create bead with priority
    console.log(`   Creating: ${title.slice(0, 60)}${title.length > 60 ? '...' : ''} (P${priority})`);

    // Build the bd create command with all rich fields
    let createCmd = `create "${escapedTitle}" -p ${priority}`;

    // Add description (summary paragraph)
    if (task.description) {
      const escapedDesc = task.description.slice(0, 1000).replace(/"/g, '\\"').replace(/`/g, '\\`').replace(/\n/g, '\\n');
      createCmd += ` --description "${escapedDesc}"`;
    }

    // Add design notes (full implementation details)
    if (task.details) {
      const escapedDesign = task.details.slice(0, 5000).replace(/"/g, '\\"').replace(/`/g, '\\`').replace(/\n/g, '\\n');
      createCmd += ` --design "${escapedDesign}"`;
    }

    // Add acceptance criteria (test strategy)
    const testStrategy = task.testStrategy || task.test_strategy;
    if (testStrategy) {
      const escapedAcceptance = testStrategy.slice(0, 2000).replace(/"/g, '\\"').replace(/`/g, '\\`').replace(/\n/g, '\\n');
      createCmd += ` --acceptance "${escapedAcceptance}"`;
    }

    const result = runBd(createCmd, isDryRun);

    if (result.success) {
      let beadId;
      if (isDryRun) {
        beadId = `bd-dry-${task.id}`;
      } else {
        // Parse bead ID from output (format: "Created issue: agencheck-xxxx" or similar)
        const match = result.output.match(/agencheck-[a-z0-9]+/i);
        beadId = match ? match[0] : null;
      }

      taskToBeadId.set(String(task.id), beadId);
      createdBeads.push({
        beadId,
        taskId: task.id,
        title,
        metadata,
      });

      if (beadId) {
        console.log(`   ✅ ${beadId} ← Task ${task.id}`);
      } else {
        console.log(`   ⚠️  Created but couldn't parse ID for task ${task.id}`);
      }

      // Link to uber-epic if specified
      if (uberEpicId && beadId) {
        console.log(`   📎 Linking to uber-epic: ${uberEpicId}`);
        runBd(`dep add ${beadId} ${uberEpicId} --type=parent-child`, isDryRun);
      }
    } else {
      console.log(`   ⚠️  Failed to create bead for task ${task.id}`);
    }
  }

  console.log('\n📎 Setting up dependencies...\n');

  // Second pass: Add dependencies
  let depCount = 0;
  for (const task of tasks) {
    const deps = task.dependencies || [];
    if (deps.length === 0) continue;

    const childBeadId = taskToBeadId.get(String(task.id));
    if (!childBeadId) continue;

    for (const depId of deps) {
      const parentBeadId = taskToBeadId.get(String(depId));
      if (!parentBeadId) {
        console.warn(`   ⚠️  Dependency ${depId} not found for task ${task.id}`);
        continue;
      }

      console.log(`   ${childBeadId} → depends on → ${parentBeadId}`);
      const depResult = runBd(`dep add ${childBeadId} ${parentBeadId}`, isDryRun);
      if (depResult.success) {
        depCount++;
      }
    }
  }

  console.log(`   Added ${depCount} dependencies\n`);

  // Third pass: Handle already-completed tasks
  console.log('✅ Closing completed tasks...\n');

  let closedCount = 0;
  for (const task of tasks) {
    if (task.status === 'done' || task.status === 'completed') {
      const beadId = taskToBeadId.get(String(task.id));
      if (beadId) {
        console.log(`   Closing: ${beadId} (task ${task.id} was done)`);
        const closeResult = runBd(`close ${beadId}`, isDryRun);
        if (closeResult.success) {
          closedCount++;
        }
      }
    }
  }

  console.log(`   Closed ${closedCount} completed tasks\n`);

  return { taskToBeadId, createdBeads };
}

// Close Task Master tasks after sync (they're now tracked in Beads)
function closeTaskMasterTasks(taskIds, isDryRun) {
  if (taskIds.length === 0) return 0;

  console.log('\n📋 Closing Task Master tasks (now tracked in Beads)...\n');

  let closedCount = 0;
  for (const taskId of taskIds) {
    const cmd = `task-master set-status --id=${taskId} --status=done`;
    if (isDryRun) {
      console.log(`   [DRY RUN] ${cmd}`);
      closedCount++;
    } else {
      try {
        execSync(cmd, { encoding: 'utf8', stdio: 'pipe' });
        console.log(`   ✅ Closed Task Master task ${taskId}`);
        closedCount++;
      } catch (error) {
        console.log(`   ⚠️  Failed to close task ${taskId}: ${error.message}`);
      }
    }
  }

  console.log(`   Closed ${closedCount}/${taskIds.length} Task Master tasks`);
  return closedCount;
}

// Main execution
function main() {
  console.log('╔════════════════════════════════════════════════════╗');
  console.log('║     Task Master → Beads Sync                       ║');
  console.log('╚════════════════════════════════════════════════════╝\n');

  // Check beads is installed
  if (!checkBeadsInstalled()) {
    console.error('❌ Error: Beads CLI not installed');
    console.error('');
    console.error('   Install with:');
    console.error('   curl -fsSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash');
    console.error('');
    process.exit(1);
  }

  console.log('✅ Beads CLI detected\n');

  // Initialize beads if needed
  if (!fs.existsSync(CONFIG.BEADS_DIR)) {
    console.log('📁 Initializing .beads/ directory...\n');
    const initResult = runBd('init', isDryRun);
    if (!initResult.success && !isDryRun) {
      console.error('❌ Failed to initialize beads');
      process.exit(1);
    }
  }

  // Load tasks
  const tasksPath = customTasksPath || CONFIG.TASKS_PATH;
  console.log(`📖 Reading: ${tasksPath}`);
  const tasksData = loadJSON(tasksPath);

  if (!tasksData) {
    console.error('❌ Error: tasks.json not found');
    console.error(`   Expected at: ${tasksPath}`);
    process.exit(1);
  }

  // Extract tasks array (handle different Task Master formats)
  let tasks = [];
  const tag = process.env.TASK_MASTER_TAG || 'master';

  if (Array.isArray(tasksData)) {
    tasks = tasksData;
  } else if (tasksData[tag] && Array.isArray(tasksData[tag].tasks)) {
    // Task Master v0.37+ uses tag-based structure
    tasks = tasksData[tag].tasks;
  } else if (tasksData.tasks && Array.isArray(tasksData.tasks)) {
    // Older format
    tasks = tasksData.tasks;
  } else if (typeof tasksData === 'object') {
    // Task Master might store tasks as object with numeric keys
    tasks = Object.values(tasksData).filter(t => t && t.id);
  }

  console.log(`   Found ${tasks.length} tasks in tasks.json\n`);

  // Filter by ID range if specified
  if (fromId !== null || toId !== null) {
    const beforeCount = tasks.length;
    tasks = tasks.filter(t => {
      const id = parseInt(t.id, 10);
      if (fromId !== null && id < fromId) return false;
      if (toId !== null && id > toId) return false;
      return true;
    });
    console.log(`🔍 Filtering by ID range: ${fromId ?? 'start'} to ${toId ?? 'end'}`);
    console.log(`   Filtered: ${beforeCount} → ${tasks.length} tasks\n`);
  }

  if (tasks.length === 0) {
    console.log('ℹ️  No tasks to sync (after filtering)');
    process.exit(0);
  }

  // Sync
  const { taskToBeadId, createdBeads } = syncTasksToBeads(tasks, isDryRun);

  // Summary
  console.log('╔════════════════════════════════════════════════════╗');
  console.log('║     Summary                                        ║');
  console.log('╚════════════════════════════════════════════════════╝\n');

  const workerTypes = {};
  createdBeads.forEach(b => {
    const wt = b.metadata.worker_type;
    workerTypes[wt] = (workerTypes[wt] || 0) + 1;
  });

  console.log(`   Tasks processed:     ${tasks.length}`);
  console.log(`   Beads created:       ${taskToBeadId.size}`);
  console.log('');
  console.log('   Worker type distribution:');
  Object.entries(workerTypes).forEach(([type, count]) => {
    console.log(`     - ${type}: ${count}`);
  });

  // Close synced tasks in Task Master (now tracked in Beads)
  const syncedTaskIds = tasks.map(t => t.id);
  closeTaskMasterTasks(syncedTaskIds, isDryRun);

  if (isDryRun) {
    console.log('\n🔍 DRY RUN - No changes made');
    console.log('   Run without --dry-run to execute');
  } else {
    console.log('\n✅ Sync complete!');
    console.log('\n📋 Next steps:');
    console.log('   1. Check ready tasks:  bd ready');
    console.log('   2. View all tasks:     bd list');
    console.log('   3. Show dependencies:  bd dep list <bd-id>');
  }
}

// Execute
try {
  main();
} catch (error) {
  console.error('❌ Error:', error.message);
  if (process.env.DEBUG) {
    console.error(error.stack);
  }
  process.exit(1);
}

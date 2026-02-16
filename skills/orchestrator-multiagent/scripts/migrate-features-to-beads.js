#!/usr/bin/env node
/**
 * Migrate feature_list.json → Beads
 *
 * Purpose: One-time migration for existing projects using feature_list.json
 * Preserves: Status (passes → closed), dependencies, metadata
 *
 * Usage: node migrate-features-to-beads.js --input=<path-to-feature_list.json> [--dry-run]
 *
 * Examples:
 *   node migrate-features-to-beads.js --input=.claude/state/room-instantiation-parameterization-feature_list.json
 *   node migrate-features-to-beads.js --input=.claude/state/my-project-feature_list.json --dry-run
 */

const { execSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Parse CLI arguments
const args = process.argv.slice(2);
const isDryRun = args.includes('--dry-run');
const inputArg = args.find(arg => arg.startsWith('--input='));
const inputPath = inputArg ? inputArg.split('=')[1] : null;

if (!inputPath) {
  console.error('❌ Usage: node migrate-features-to-beads.js --input=<path-to-feature_list.json> [--dry-run]');
  console.error('');
  console.error('Examples:');
  console.error('  node migrate-features-to-beads.js --input=.claude/state/my-project-feature_list.json');
  console.error('  node migrate-features-to-beads.js --input=.claude/state/my-project-feature_list.json --dry-run');
  process.exit(1);
}

// Utility functions
function loadJSON(filepath) {
  try {
    const content = fs.readFileSync(filepath, 'utf8');
    return JSON.parse(content);
  } catch (error) {
    if (error.code === 'ENOENT') {
      console.error(`❌ File not found: ${filepath}`);
      process.exit(1);
    }
    console.error(`❌ Invalid JSON in: ${filepath}`);
    console.error(`   ${error.message}`);
    process.exit(1);
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
      return { success: false, output: '' };
    }
    if (result.status !== 0) {
      // Some commands may fail gracefully (e.g., closing already closed bead)
      return { success: false, output: (result.stderr || result.stdout || '').trim() };
    }
    return { success: true, output: (result.stdout || '').trim() };
  } catch (error) {
    console.error(`  ❌ Command failed: ${fullCommand}`);
    return { success: false, output: '' };
  }
}

function inferPriority(feature) {
  // Map feature properties to priority
  // Features with no dependencies tend to be foundational (higher priority)
  const deps = feature.dependencies || [];
  if (deps.length === 0) return 0;
  if (deps.length <= 2) return 1;
  return 2;
}

// Main migration
function migrateFeaturesToBeads(features, isDryRun) {
  console.log('🔄 Migrating feature_list.json → Beads\n');

  // Map feature IDs to bead IDs
  const featureToBeadId = new Map();
  const migrationStats = {
    created: 0,
    closed: 0,
    dependencies: 0,
    failed: 0,
  };

  // First pass: Create beads for all features
  console.log('📝 Creating beads from features...\n');

  for (const feature of features) {
    const title = (feature.description || `Feature ${feature.id}`).slice(0, 200);
    const priority = inferPriority(feature);

    // Build metadata from feature properties
    const metadata = {
      feature_id: feature.id,
      task_id: feature.task_id || null,
      worker_type: feature.worker_type || 'general-purpose',
      validation_type: typeof feature.validation === 'object'
        ? feature.validation.type
        : feature.validation || 'manual',
      scope: feature.scope || [],
      steps: feature.steps || [],
      test_strategy: feature.test_strategy || '',
      acceptance_criteria: feature.acceptance_criteria || [],
    };

    // Escape title for shell
    const escapedTitle = title.replace(/"/g, '\\"').replace(/`/g, '\\`');

    console.log(`   ${feature.id}: ${title.slice(0, 50)}${title.length > 50 ? '...' : ''}`);

    const createCmd = `create "${escapedTitle}" -p ${priority}`;
    const result = runBd(createCmd, isDryRun);

    if (result.success) {
      let beadId;
      if (isDryRun) {
        beadId = `bd-dry-${feature.id}`;
      } else {
        const match = result.output.match(/bd-[a-z0-9]+/i);
        beadId = match ? match[0] : `bd-${feature.id}`;
      }

      featureToBeadId.set(feature.id, beadId);
      migrationStats.created++;
      console.log(`   ✅ ${beadId} ← ${feature.id}`);
    } else {
      migrationStats.failed++;
      console.log(`   ⚠️  Failed to create bead for ${feature.id}`);
    }
  }

  // Second pass: Add dependencies
  console.log('\n📎 Setting up dependencies...\n');

  for (const feature of features) {
    const deps = feature.dependencies || [];
    if (deps.length === 0) continue;

    const childBeadId = featureToBeadId.get(feature.id);
    if (!childBeadId) continue;

    for (const depId of deps) {
      const parentBeadId = featureToBeadId.get(depId);
      if (!parentBeadId) {
        console.warn(`   ⚠️  Dependency ${depId} not found for ${feature.id}`);
        continue;
      }

      console.log(`   ${childBeadId} → depends on → ${parentBeadId}`);
      const depResult = runBd(`dep add ${childBeadId} ${parentBeadId}`, isDryRun);
      if (depResult.success) {
        migrationStats.dependencies++;
      }
    }
  }

  // Third pass: Close passed features
  console.log('\n✅ Closing passed features...\n');

  for (const feature of features) {
    if (feature.passes === true) {
      const beadId = featureToBeadId.get(feature.id);
      if (beadId) {
        console.log(`   Closing: ${beadId} (${feature.id} passes: true)`);
        const closeResult = runBd(`close ${beadId}`, isDryRun);
        if (closeResult.success) {
          migrationStats.closed++;
        }
      }
    }
  }

  return { featureToBeadId, migrationStats };
}

// Save mapping file
function saveMappingFile(mapping, features, outputPath) {
  const mappingData = {
    migrated_at: new Date().toISOString(),
    source_file: inputPath,
    total_features: features.length,
    mappings: Array.from(mapping.entries()).map(([featureId, beadId]) => {
      const feature = features.find(f => f.id === featureId);
      return {
        feature_id: featureId,
        bead_id: beadId,
        task_id: feature?.task_id || null,
        passed: feature?.passes || false,
      };
    }),
  };

  const dir = path.dirname(outputPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  fs.writeFileSync(outputPath, JSON.stringify(mappingData, null, 2) + '\n');
  return outputPath;
}

// Main execution
function main() {
  console.log('╔════════════════════════════════════════════════════╗');
  console.log('║     Feature List → Beads Migration                 ║');
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
  if (!fs.existsSync('.beads')) {
    console.log('📁 Initializing .beads/ directory...\n');
    runBd('init', isDryRun);
  }

  // Load features
  console.log(`📖 Reading: ${inputPath}`);
  const features = loadJSON(inputPath);

  if (!Array.isArray(features)) {
    console.error('❌ Error: Expected array of features in JSON file');
    process.exit(1);
  }

  console.log(`   Found ${features.length} features\n`);

  if (features.length === 0) {
    console.log('ℹ️  No features to migrate');
    process.exit(0);
  }

  // Show feature status before migration
  const passedCount = features.filter(f => f.passes === true).length;
  const pendingCount = features.filter(f => f.passes !== true).length;

  console.log('📊 Feature status:');
  console.log(`   Passed:  ${passedCount}`);
  console.log(`   Pending: ${pendingCount}`);
  console.log('');

  // Migrate
  const { featureToBeadId, migrationStats } = migrateFeaturesToBeads(features, isDryRun);

  // Summary
  console.log('\n╔════════════════════════════════════════════════════╗');
  console.log('║     Migration Summary                              ║');
  console.log('╚════════════════════════════════════════════════════╝\n');

  console.log(`   Features processed: ${features.length}`);
  console.log(`   Beads created:      ${migrationStats.created}`);
  console.log(`   Dependencies added: ${migrationStats.dependencies}`);
  console.log(`   Beads closed:       ${migrationStats.closed}`);
  if (migrationStats.failed > 0) {
    console.log(`   ⚠️  Failed:         ${migrationStats.failed}`);
  }

  // Save mapping file
  if (!isDryRun && featureToBeadId.size > 0) {
    const mappingPath = inputPath.replace('.json', '-bead-mapping.json');
    saveMappingFile(featureToBeadId, features, mappingPath);
    console.log(`\n💾 Mapping saved: ${mappingPath}`);
  }

  if (isDryRun) {
    console.log('\n🔍 DRY RUN - No changes made');
    console.log('   Run without --dry-run to execute');
  } else {
    console.log('\n✅ Migration complete!');
    console.log('\n📋 Next steps:');
    console.log('   1. Verify migration:   bd list');
    console.log('   2. Check ready tasks:  bd ready');
    console.log(`   3. Archive old file:   mv ${inputPath} ${inputPath}.bak`);
    console.log('   4. Update SKILL.md references to use beads workflow');
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

# Parallel Development Cleanup

## Clean Up Multi-Process Development Resources

**Remove completed worktrees, stop processes, and clean coordination infrastructure after parallel development work is complete.**

## Usage

```bash
/project:parallel/cleanup
/project:parallel/cleanup --force
/project:parallel/cleanup --keep-worktrees
```

## What This Command Does

### 1. Process Management
```bash
# Identify all Claude Code processes
ps aux | grep claude-code | grep -v grep

# Gracefully terminate processes
for pid in $(ps aux | grep claude-code | grep -v grep | awk '{print $2}'); do
  kill -TERM $pid
  sleep 5
  kill -KILL $pid 2>/dev/null || true
done
```

### 2. Git Worktree Cleanup
```bash
# List active worktrees
git worktree list

# Remove worktrees safely
for worktree in $(cat .parallel-coordination/active-worktrees.json | jq -r '.worktrees[].path'); do
  if [ -d "$worktree" ]; then
    cd "$worktree"
    git add . && git commit -m "Auto-commit before cleanup" || true
    cd - 
    git worktree remove "$worktree" --force
  fi
done
```

### 3. Coordination Infrastructure
```bash
# Archive coordination data
mkdir -p .parallel-coordination/archive/$(date +%Y%m%d_%H%M%S)
cp .parallel-coordination/*.json .parallel-coordination/archive/$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true

# Clean active coordination files
rm -f .parallel-coordination/active-worktrees.json
rm -f .parallel-coordination/progress.json
rm -f .parallel-coordination/merge-queue.json
```

## Advanced Usage

### Selective Cleanup
```bash
# Keep specific worktrees
/project:parallel/cleanup --keep feature/user-auth

# Force cleanup without confirmation
/project:parallel/cleanup --force

# Archive only, don't remove
/project:parallel/cleanup --archive-only
```

### Safe Cleanup with Merge Check
```bash
# Check for unmerged work first
for worktree in $(git worktree list --porcelain | grep worktree | cut -d' ' -f2); do
  cd $worktree
  unmerged=$(git log --oneline origin/main..HEAD | wc -l)
  if [ $unmerged -gt 0 ]; then
    echo "WARNING: $worktree has $unmerged unmerged commits"
  fi
done
```

## Safety Features

### Pre-Cleanup Validation
- **Commit Check**: Ensures all worktrees have committed changes
- **Merge Status**: Warns about unmerged commits ahead of main
- **Process Status**: Verifies processes are safely stoppable
- **File Locks**: Checks for active file locks or ongoing operations

### Data Preservation
- **Automatic Archiving**: All coordination data preserved with timestamps
- **Commit Auto-Save**: Uncommitted changes automatically committed
- **Backup Creation**: Git refs backed up before worktree removal
- **Recovery Information**: Instructions for data recovery stored in archive

### Confirmation Prompts
```bash
# Interactive mode (default)
/project:parallel/cleanup
# Shows:
# - Active worktrees and their status
# - Unmerged commits warning
# - Process termination plan
# - Confirmation prompt

# Force mode (no prompts)
/project:parallel/cleanup --force
```

## Error Handling

### Common Issues
```bash
# Worktree removal fails (active processes)
# Solution: Kill processes first, then retry

# Permission denied on worktree directory
# Solution: Check file permissions and ownership

# Git worktree in inconsistent state
# Solution: Use --force flag or manual git worktree repair

# Coordination files corrupted
# Solution: Manual cleanup with archived data
```

### Recovery Procedures
```bash
# Recover from failed cleanup
ls .parallel-coordination/archive/
# Find latest archive and restore if needed

# Manual worktree removal
git worktree list
git worktree remove [path] --force

# Process cleanup if automated cleanup fails
ps aux | grep claude-code
kill -9 [PID]
```

## Integration with Other Commands

### Pre-Cleanup Status Check
```bash
# Always run status before cleanup
/project:parallel/status
/project:parallel/cleanup
```

### Post-Cleanup Verification
```bash
# Verify cleanup completed successfully
git worktree list  # Should show only main worktree
ps aux | grep claude-code  # Should show no background processes
ls .parallel-coordination/  # Should be empty except archive/
```

## Cleanup Scenarios

### Complete Project Cleanup
```bash
# End all parallel development
/project:parallel/cleanup

# Removes: All worktrees, stops all processes, archives coordination
# Keeps: Archive data, git history, main branch
```

### Feature-Specific Cleanup
```bash
# Remove only specific feature worktree
/project:parallel/cleanup --worktree feature/user-auth

# Useful when: One feature complete, others continue
```

### Emergency Cleanup
```bash
# Force remove everything immediately
/project:parallel/cleanup --force --no-archive

# Use when: System resources critical, processes hung
```

## Best Practices

### When to Clean Up
- **Feature Complete**: Individual features merged and deployed
- **Project Phase Complete**: Major milestone reached
- **Resource Constraints**: System memory or disk space low
- **Process Issues**: Background processes causing problems

### Pre-Cleanup Checklist
- ✅ All important work committed and pushed
- ✅ Merge conflicts resolved  
- ✅ Feature branches merged to main if ready
- ✅ Documentation updated
- ✅ Team notified if shared development

### Post-Cleanup Actions
- ✅ Verify main branch is clean and up to date
- ✅ Confirm no orphaned processes remain
- ✅ Check system resources recovered
- ✅ Update project documentation

## Command Line Usage

### Use with argument support
```bash
/project:parallel/cleanup force        # Force cleanup without prompts
/project:parallel/cleanup selective    # Choose which resources to clean
/project:parallel/cleanup verify       # Dry run - show what would be cleaned
```

## Resource Recovery

### Disk Space Recovery
- **Worktrees**: Each worktree ~500MB-2GB depending on project size
- **Coordination Files**: Usually <10MB but can accumulate over time
- **Git Objects**: Shared with main repository, minimal additional space

### Memory Recovery  
- **Background Processes**: Each Claude Code instance ~200-500MB
- **Git Operations**: Worktree operations hold memory temporarily
- **Coordination**: JSON files and status tracking minimal memory

### Performance Impact
- **Cleanup Time**: 30-120 seconds depending on number of worktrees
- **Network**: No network activity during cleanup
- **CPU**: Minimal impact, mostly file operations

**🧹 Essential for maintaining clean development environment and system resources after parallel development sessions.**
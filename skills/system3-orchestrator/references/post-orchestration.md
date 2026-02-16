# Post-Orchestration Reference

Workflow after an orchestrator completes its mission.

---

## Overview

When an orchestrator completes (or is terminated), System 3 should:

1. **Collect Outcomes** - Gather all results and progress
2. **Apply Process Supervision** - Validate reasoning paths
3. **Store Learnings** - Retain patterns in Hindsight
4. **Merge Work** - Integrate code changes
5. **Cleanup** - Remove worktree and registry entry

---

## Step 1: Collect Outcomes

### Read Progress Log

```python
progress_log = Read(f"trees/{initiative}/.claude/progress/orch-{initiative}-log.md")
```

### Capture Final State

```bash
# Last session output
tmux capture-pane -t "orch-[name]" -p -S -500 > /tmp/final-output.txt

# Git status in worktree
cd trees/[name]/agencheck && git status
```

### Analyze Task Completion

```python
task_analysis = mcp__hindsight__reflect(
    f"""
    Analyze orchestrator completion:

    Progress Log:
    {progress_log}

    Questions:
    - What tasks were completed?
    - What tasks remain incomplete?
    - Were there any blockers?
    - What was the overall outcome?
    """,
    budget="mid"
)
```

---

## Step 2: Process Supervision

Apply the Guardian LLM pattern to validate reasoning paths.

### Validate Success Patterns

```python
if "COMPLETE" in task_analysis or "SUCCESS" in task_analysis:
    # Extract reasoning path
    reasoning_path = extract_reasoning_from_log(progress_log)

    validation = mcp__hindsight__reflect(
        f"""
        PROCESS SUPERVISION: Validate orchestrator reasoning

        INITIATIVE: {initiative}
        OUTCOME: Successful completion

        REASONING PATH:
        {reasoning_path}

        VALIDATION CRITERIA:
        1. Was the goal clearly defined?
        2. Were steps logically sequenced?
        3. Were decisions justified?
        4. Were potential risks considered?
        5. Was the outcome verified?

        VERDICT: VALID or INVALID
        CONFIDENCE: 0.0 to 1.0
        REASONING: Why this verdict?
        """,
        budget="high",
        bank_id="system3-orchestrator"
    )
```

### Validate Failure Patterns

```python
if "BLOCKED" in task_analysis or "FAILED" in task_analysis:
    # Extract what went wrong
    failure_analysis = mcp__hindsight__reflect(
        f"""
        PROCESS SUPERVISION: Analyze orchestrator failure

        INITIATIVE: {initiative}
        OUTCOME: Blocked/Failed

        ANALYSIS QUESTIONS:
        1. What was the root cause?
        2. Was the failure predictable?
        3. What warning signs were missed?
        4. How could this be prevented?
        5. What's the recovery path?

        PATTERN TYPE: Anti-pattern to avoid
        CONFIDENCE: 0.0 to 1.0
        """,
        budget="high",
        bank_id="system3-orchestrator"
    )
```

---

## Step 3: Store Learnings

### Store Validated Pattern

```python
if "VALID" in validation and confidence > 0.7:
    mcp__hindsight__retain(
        content=f"""
        ## Validated Orchestration Pattern

        **Initiative**: {initiative}
        **Domain**: {domain}
        **Outcome**: Success

        ### Pattern Summary
        {pattern_summary}

        ### Key Decisions
        {key_decisions}

        ### Conditions for Reuse
        - {condition_1}
        - {condition_2}

        ### Validation
        - Confidence: {confidence}
        - Validated by: Process Supervision (reflect budget=high)
        """,
        context="system3-patterns",
        bank_id="system3-orchestrator"
    )
```

### Store Anti-Pattern

```python
if "INVALID" in validation or "FAILED" in task_analysis:
    mcp__hindsight__retain(
        content=f"""
        ## Anti-Pattern: Avoid This

        **Initiative**: {initiative}
        **Domain**: {domain}
        **Outcome**: Failure/Invalid

        ### What Went Wrong
        {failure_description}

        ### Warning Signs
        - {warning_1}
        - {warning_2}

        ### Prevention Strategy
        {prevention_strategy}

        ### Recovery Path
        {recovery_path}
        """,
        context="system3-anti-patterns",
        bank_id="system3-orchestrator"
    )
```

### Update Capability Self-Model

```python
# Update capability tracking based on outcome
mcp__hindsight__retain(
    content=f"""
    ## Capability Update

    **Capability**: {capability_name}
    **Initiative**: {initiative}
    **Previous Confidence**: {prev_confidence}
    **New Confidence**: {new_confidence}

    ### Evidence
    - Outcome: {outcome}
    - Tasks completed: {task_count}
    - Complexity: {complexity}

    ### Notes
    {capability_notes}
    """,
    context="system3-capabilities",
    bank_id="system3-orchestrator"
)
```

### Share Domain Learnings

```python
# Store domain-specific learnings in shared bank
mcp__hindsight__retain(
    content=f"""
    ## Development Pattern: {pattern_name}

    **Domain**: {domain}
    **Context**: {context}

    ### Pattern
    {pattern_description}

    ### When to Use
    {use_cases}

    ### Source
    Discovered during initiative: {initiative}
    """,
    context="patterns",
    bank_id="claude-code-agencheck"
)
```

---

## Step 4: Merge Work

### Check Git Status

```bash
cd trees/[name]/agencheck

# Check for uncommitted changes
git status

# Check branch ahead/behind
git log origin/main..HEAD --oneline
```

### Push Branch

```bash
# Push all commits
git push -u origin [branch-name]

# If branch exists, just push
git push
```

### Create Pull Request

```bash
gh pr create \
    --title "[initiative-name] Implementation" \
    --body "$(cat << EOF
## Summary
[Summary of changes from orchestrator]

## Changes
$(git log origin/main..HEAD --oneline)

## Testing
- [ ] Tests pass
- [ ] Manual verification done

## Notes
Orchestrated by: System 3 System 3
Initiative: $INITIATIVE
EOF
)"
```

---

## Step 5: Cleanup

### Update Registry

```bash
REGISTRY=".claude/state/active-orchestrators.json"

jq --arg name "orch-$INITIATIVE" \
   '.orchestrators = [.orchestrators[] | select(.name != $name)]' \
   "$REGISTRY" > "${REGISTRY}.tmp" && mv "${REGISTRY}.tmp" "$REGISTRY"
```

### Remove Worktree

```bash
/remove_worktree [initiative-name]
```

### Archive Logs

```bash
# Move progress log to archive
mkdir -p .claude/archive/orchestrators
mv trees/[name]/.claude/progress/orch-[name]-log.md \
   .claude/archive/orchestrators/$(date +%Y%m%d)-[name]-log.md
```

---

## Complete Post-Orchestration Script

```bash
#!/bin/bash
# post-orchestration.sh [initiative-name]

INITIATIVE="${1:?Usage: $0 <initiative-name>}"
SESSION="orch-${INITIATIVE}"
WORKTREE="trees/${INITIATIVE}/agencheck"

echo "=== Post-Orchestration: $INITIATIVE ==="

# 1. Capture final state
echo "[1/5] Capturing final state..."
tmux capture-pane -t "$SESSION" -p -S -500 > /tmp/final-$INITIATIVE.txt 2>/dev/null || true

# 2. Check if PR needed
echo "[2/5] Checking git status..."
cd "$WORKTREE"
COMMITS=$(git log origin/main..HEAD --oneline 2>/dev/null | wc -l)
if [ "$COMMITS" -gt 0 ]; then
    echo "  Found $COMMITS unpushed commits"
    echo "  Run: cd $WORKTREE && git push"
fi

# 3. Update registry
echo "[3/5] Updating registry..."
cd -
REGISTRY=".claude/state/active-orchestrators.json"
if [ -f "$REGISTRY" ]; then
    jq --arg name "$SESSION" \
       '.orchestrators = [.orchestrators[] | select(.name != $name)]' \
       "$REGISTRY" > "${REGISTRY}.tmp" && mv "${REGISTRY}.tmp" "$REGISTRY"
fi

# 4. Kill session if still running
echo "[4/5] Terminating session..."
if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
fi

# 5. Summary
echo "[5/5] Summary..."
echo "  Progress log: $WORKTREE/.claude/progress/orch-${INITIATIVE}-log.md"
echo "  Final output: /tmp/final-$INITIATIVE.txt"
echo ""
echo "Next steps:"
echo "  1. Review progress log"
echo "  2. Merge changes: cd $WORKTREE && git push && gh pr create"
echo "  3. Remove worktree: /remove_worktree $INITIATIVE"
```

---

## GEO Chain Retention

For significant outcomes, store Goal-Experience-Outcome chains:

```python
mcp__hindsight__retain(
    content=f"""
    ## GEO Chain: {initiative}

    ### GOAL
    **Objective**: {original_goal}
    **Success Criteria**: {success_criteria}
    **Constraints**: {constraints}

    ### EXPERIENCE
    **Approach Taken**: {approach}
    **Key Decisions**:
    - {decision_1}: {rationale_1}
    - {decision_2}: {rationale_2}
    **Challenges Encountered**: {challenges}
    **Adaptations Made**: {adaptations}

    ### OUTCOME
    **Result**: {Success/Partial/Failure}
    **What Worked**: {successes}
    **What Didn't**: {failures}
    **Key Learnings**: {learnings}

    ### Meta
    **Transferability**: {High/Medium/Low}
    **Conditions for Reuse**: {conditions}
    """,
    context="system3-geo-chains",
    bank_id="system3-orchestrator"
)
```

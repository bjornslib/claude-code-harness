# OKR-Driven Development Reference

Business Epic and Key Result tracking for human-AI partnership in steering toward business outcomes.

---

## The Partnership Model

| Role | Responsibilities |
|------|------------------|
| **User** | Strategic direction, domain expertise, PRD feedback, business outcome definition |
| **System 3** | Execution steering, orchestration, outcome verification, autonomous work within boundaries |

**Core Principle**: User defines *what success looks like*; System 3 figures out *how to get there* and verifies *whether we arrived*.

---

## OKR Hierarchy in Beads

```
Strategic Theme (direction - what area we're investing in)
    │ tag: theme
    │
    └── Business Epic (capability - what we're building for customers)
            │ tag: bo
            │
            ├── Key Result 1 (measurement - how we know it worked)
            │   tag: kr
            ├── Key Result 2
            │   tag: kr
            │
            └── blocked-by:
                    ├── Enabler Epic A (technical implementation)
                    │   tag: epic
                    ├── Enabler Epic B
                    │   tag: epic
                    └── Enabler Epic C
                        tag: epic
```

---

## Terminology

| Term | Beads Tag | Level | Description | Example |
|------|-----------|-------|-------------|---------|
| **Strategic Theme** | `theme` | Direction | High-level business investment area | "Automated Employment Verification" |
| **Business Epic** | `bo` | Capability | Customer-facing capability | "First paying verification customer" |
| **Key Result** | `kr` | Measurement | Measurable outcome proving success | "Customer completes paid verification" |
| **Enabler Epic** | `epic` | Implementation | Technical work enabling capability | "Epic 2: Case Creation + Manual Dispatch" |
| **Task** | `task` | Work Item | Individual implementation unit | "Create Pydantic models for work history" |

---

## Creating Business Outcomes

### Step 1: Create Strategic Theme (if new area)

```bash
bd create --title="Automated Employment Verification" --type=epic --tag=theme
```

### Step 2: Create Business Epic

```bash
bd create --title="First paying work history verification customer" \
    --type=epic --tag=bo \
    --description="Customer successfully uses voice agent for employment verification"
```

### Step 3: Create Key Results

```bash
bd create --title="Customer completes paid verification" --type=task --tag=kr
bd create --title="Customer receives structured results" --type=task --tag=kr
bd create --title="Customer charged via Clerk/Stripe" --type=task --tag=kr
```

### Step 4: Link Dependencies

```bash
# Key Results block Business Epic closure
bd dep add <bo-id> <kr-1-id>
bd dep add <bo-id> <kr-2-id>

# Business Epic blocked by Enabler Epics
bd dep add <enabler-epic-id> <bo-id>  # Enabler enables BO
```

---

## Dependency Semantics

### Enabler Epics Block Business Epics

Technical work *enables* business outcomes.

```
bo-work-history-revenue (open)
    └── blocked-by:
        ├── epic-1-livekit-adjustments (done)
        ├── epic-2-case-creation (done)
        ├── epic-3-ai-research (in_progress)
        └── ...
```

### Key Results Block Business Epic Closure

Business Epic can only close when Key Results are verified.

```
bo-work-history-revenue (open)
    ├── kr-first-customer-paid (open) ← Must verify
    ├── kr-structured-results-delivered (open) ← Must verify
    └── blocked-by: [enabler epics]
```

---

## System 3 Workflow

### At Session Start

```bash
# Check active Business Epics
bd list --tag=bo --status=open

# Get business context from Hindsight
mcp__hindsight__reflect(
    query="What are the active business outcomes and their Key Results?",
    budget="mid"
)

# Identify highest-priority Business Epic
# Priority order: P0 > P1 > P2
```

### During Work

For every piece of technical work, ask:
> "Which Business Epic does this serve? Which Key Result does this advance?"

### Before Closing Enabler Epic

```python
# 1. Identify which Business Epic this enables
bo_epic = find_business_epic_enabled_by(enabler_epic)

# 2. Check if any Key Results are now verifiable
for kr in get_key_results_for(bo_epic):
    if can_verify_now(kr):
        # Delegate to validation-agent --mode=business
        verify_kr_via_validation_agent(kr)

# 3. Check if Business Epic can close
if all_key_results_verified(bo_epic) and all_enabler_epics_done(bo_epic):
    # Delegate closure to validation-agent --mode=business
    Task(subagent_type="validation-agent",
         prompt=f"--mode=business --task_id={bo_epic.id}")
```

---

## Key Result Verification Protocol

**When an Enabler Epic completes:**

1. Invoke verification skill:
   ```python
   Skill("verification-before-completion")
   ```

2. Delegate KR verification:
   ```python
   Task(
       subagent_type="validation-agent",
       prompt=f"""
       --mode=business
       --task_id={kr_id}

       Verify Key Result: "{kr_description}"

       Required:
       1. Run actual verification (not just tests)
       2. Capture shareable evidence
       3. If verified: Close KR with evidence
       4. If not verified: Report gap, do NOT close
       """
   )
   ```

**Key Principle**: Every Key Result closure needs **shareable proof** - evidence the user can review.

---

## Closure Order

```
AT tasks → AT epic → Functional epic → Key Results → Business Epic
```

**All business-level closures (KR, BO) go through validation-agent with `--mode=business`.**

---

## Partnership Communication

### User to System 3

| User Says | System 3 Interprets |
|-----------|---------------------|
| "We need our first paying customer" | Create Business Epic + Key Results, plan Enabler Epics |
| "This PRD describes what we're building" | Extract Business Epic + Key Results from PRD |
| "We should also think about X" | Potential new Theme or Business Epic - clarify scope |
| "That's not quite right" | Course correction on implementation |
| "What do you think?" | Exercise judgment, act autonomously, report results |

### System 3 to User

| System 3 Reports | When |
|------------------|------|
| "Business Epic X is at Y% (3/5 KRs verified)" | After any Key Result verification |
| "Enabler Epic N complete. KR K now verifiable." | After closing enabler work |
| "Gap identified: [description]" | When verification reveals gaps |
| "Business Epic X ACHIEVED. All KRs verified." | When Business Epic closes |
| "Blocked: Need [domain expertise / PRD clarification]" | When user input genuinely needed |

---

## Session End Report

Before transitioning to idle mode, report:

```markdown
## Business Epic Progress

**[BO Title]**: X/Y Key Results verified

### Verified This Session
- KR1: [description] - Evidence: [proof]

### Newly Verifiable
- KR2: [description] - Ready for verification

### Gaps Identified
- [Gap description] - Follow-up task created

### Next Session Focus
- Target KR: [description]
```

---

## Anti-Patterns

| Anti-Pattern | Why Wrong | Correct Approach |
|--------------|-----------|------------------|
| Close Enabler without checking KRs | Technical != business outcome | Always attempt KR verification |
| Create tasks without linking to BO | Orphaned work | Every task traces to KR → BO |
| Wait for user to say "verify" | Slows progress | Verify automatically after enabler work |
| Close BO when Enablers done | Enablers necessary, not sufficient | Must verify KRs independently |

---

## Memory Contexts

| Context | Bank | Purpose |
|---------|------|---------|
| `system3-okr-tracking` | Private | Active Business Epics, KR status |
| `system3-prd-tracking` | Private | PRD-extracted goals |
| `roadmap` | Shared | Strategic Themes, long-term direction |

---

**Version**: 1.0.0
**Source**: System 3 Output Style - OKR-Driven Development: Human-AI Partnership Model

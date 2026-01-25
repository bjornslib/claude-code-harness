# Homepage Redesign - Worker Assignments

**Orchestrator Session**: orch-homepage
**Initiative**: Homepage Hero Redesign
**Date**: 2026-01-23
**PRD**: `.taskmaster/docs/homepage-redesign-prd.md`

---

## Worker Delegation Strategy

**Pattern**: Orchestrator coordinates 3 parallel tmux workers (frontend specialists)
**Tool**: `launchcc` (Claude Code with --dangerously-skip-permissions)
**Monitoring**: Haiku sub-agents for each worker session

---

## Worker 1: UI Foundation Specialist

**Session Name**: `worker-homepage-foundation`
**Agent Type**: frontend-dev-expert
**Epic**: Epic 1 - UI Foundation Components (dspy-6d4)
**Ready Tasks**:
- dspy-aep: Task 1.1 - Install UI dependencies
- dspy-9d2: Task 1.2 - Create searchSlice (Zustand)
- dspy-2jo: Task 1.3 - Implement HeroHeading component
- dspy-8ke: Task 1.4 - Implement SearchBar component
- dspy-w7i: Task 1.5 - Implement FilterChip component

**Assignment Template**:
```markdown
MISSION: Implement UI Foundation components for homepage hero

GOALS:
1. Install shadcn/ui components (button, input, badge, card) and lucide-react icons
2. Create searchSlice in Zustand with state management for searchQuery, activeFilters, selectedState
3. Implement HeroHeading with fade-in animation and responsive typography
4. Implement SearchBar as composite component (input + icon + orange CTA button)
5. Implement FilterChip with toggle states, hover effects, and keyboard accessibility

ACCEPTANCE_CRITERIA:
- All shadcn/ui components installed and imports working
- searchSlice integrated into main Zustand store with TypeScript types
- HeroHeading renders with text-3xl → text-5xl responsive sizing
- SearchBar connects to searchSlice, Enter key submits, aria-label implemented
- FilterChip toggles gray/orange states, scale 1.05 on hover, role="button" + aria-pressed
- All components have unit tests passing (Jest + RTL)
- All components responsive (mobile-first design)

ADDITIONAL_CONTEXT:
- **Technology Stack**: Next.js 14+, React 18+, TypeScript, Tailwind CSS 4, shadcn/ui, Zustand
- **Color Palette**: Primary #FF6B35 (orange), Muted #F5F5F5 (gray), Border #E0E0E0
- **Design Spec**: workspace/preemploymentdirectory-improvements/design-concepts/specs/homepage-hero-spec.jsonc
- **Zustand Store**: Create stores/slices/searchSlice.ts with actions: setSearchQuery, toggleFilter, setSelectedState, executeSearch, clearFilters
- **Component Directory**: components/homepage/
- **Icons**: lucide-react (import SearchIcon, BriefcaseIcon, ShieldCheckIcon, FlaskConicalIcon, GraduationCapIcon)
- **Accessibility**: All components keyboard accessible (Tab + Enter/Space), proper ARIA labels
- **Testing**: Unit tests for each component in *.test.tsx files

TASKS (Beads):
- dspy-aep (READY): Install UI dependencies
- dspy-9d2 (blocked by dspy-aep): Create searchSlice
- dspy-2jo (blocked by dspy-aep): Implement HeroHeading
- dspy-8ke (blocked by dspy-9d2): Implement SearchBar
- dspy-w7i (blocked by dspy-9d2): Implement FilterChip

WORKFLOW:
1. Mark dspy-aep as in-progress: `bd update dspy-aep --status in_progress`
2. Install dependencies (shadcn/ui, lucide-react)
3. Close dspy-aep: `bd close dspy-aep --reason "Dependencies installed, all imports working"`
4. Proceed sequentially through remaining tasks
5. Update beads status as you progress
6. Commit changes after each component completes
7. Report completion to orchestrator

VALIDATION PROTOCOL (3-Level):
- Level 1 (Unit): Write tests for each component, ensure all passing
- Level 2 (API): Not applicable for UI foundation (no API calls yet)
- Level 3 (E2E): Visual verification - components render correctly in browser

**Do NOT close tasks without validation evidence. Orchestrator will delegate final validation to validation-agent after your completion report.**
```

---

## Worker 2: Navigation Components Specialist

**Session Name**: `worker-homepage-navigation`
**Agent Type**: frontend-dev-expert
**Epic**: Epic 2 - Navigation Components (dspy-1mr)
**Ready Tasks**:
- dspy-ctp: Task 2.1 - Install react-usa-map
- dspy-3nh: Task 2.2 - Implement CategoryCard component
- dspy-8xy: Task 2.3 - Implement CategorySection container
- dspy-3et: Task 2.4 - Implement InteractiveUSMap component
- dspy-rdr: Task 2.5 - Implement StateDropdown (mobile)
- dspy-jq9: Task 2.6 - Implement MapSection container

**Assignment Template**:
```markdown
MISSION: Implement navigation components (category browsing + interactive map)

GOALS:
1. Install react-usa-map library for SVG-based US state map
2. Implement CategoryCard with icon, label, hover effects (scale 1.05, shadow-lg)
3. Implement CategorySection container with 2x2 grid layout (responsive: 1→2 columns)
4. Implement InteractiveUSMap with provider density visualization and click handlers
5. Implement StateDropdown as mobile alternative (<640px screens only)
6. Implement MapSection container with responsive map/dropdown logic

ACCEPTANCE_CRITERIA:
- react-usa-map installed and working
- CategoryCard: hover scale 1.05 + shadow-lg, transitions 300ms, navigates to /category/{slug}
- CategorySection: 'Browse by Category' heading, grid 1-col mobile → 2-col desktop
- InteractiveUSMap: state colors based on provider density (opacity 0.3-1.0), hover tooltips, click navigates to /search?state={code}
- StateDropdown: shadcn/ui select component, hidden on lg+ screens, navigates to /search?state={code}
- MapSection: 'Browse by Location' heading, shows map on desktop, dropdown on mobile
- All components have unit tests passing
- All navigation routes working correctly

ADDITIONAL_CONTEXT:
- **Map Library**: react-usa-map (npm install react-usa-map)
- **Map Colors**: Primary #4A90E2 (blue), Hover #7AABEA (light blue), Default #E5E7EB (gray-200)
- **Category Icons**: ShieldCheckIcon (Criminal), FlaskConicalIcon (Drug Testing), GraduationCapIcon (Education), BriefcaseIcon (Employment)
- **Category Data**: Mock initially, later fetch from /api/categories
- **State Data**: Mock initially, later fetch from /api/states/providers
- **Mobile Breakpoint**: lg:hidden for StateDropdown, hidden lg:block for InteractiveUSMap
- **Navigation**: Use Next.js router.push() for all clicks
- **Component Directory**: components/homepage/

TASKS (Beads):
- dspy-ctp (READY): Install react-usa-map
- dspy-3nh (READY): Implement CategoryCard
- dspy-8xy (blocked by dspy-3nh): Implement CategorySection
- dspy-3et (blocked by dspy-ctp): Implement InteractiveUSMap
- dspy-rdr (READY): Implement StateDropdown
- dspy-jq9 (blocked by dspy-3et, dspy-rdr): Implement MapSection

WORKFLOW:
1. Start with parallel tasks: dspy-ctp (install), dspy-3nh (CategoryCard), dspy-rdr (StateDropdown)
2. Update beads status to in_progress before starting each
3. Close tasks with evidence after completion
4. Proceed to blocked tasks after dependencies complete
5. Commit after each component
6. Report completion to orchestrator

VALIDATION PROTOCOL (3-Level):
- Level 1 (Unit): Tests for CategoryCard, InteractiveUSMap, StateDropdown
- Level 2 (API): Mock /api/categories and /api/states/providers responses
- Level 3 (E2E): Browser test - click category card → navigate, click state → navigate

**Do NOT close tasks without validation evidence.**
```

---

## Worker 3: Responsive & Polish Specialist

**Session Name**: `worker-homepage-polish`
**Agent Type**: frontend-dev-expert
**Epic**: Epic 3 - Responsive Design & Polish (dspy-cbf)
**Blocked By**: Epic 1 (dspy-6d4), Epic 2 (dspy-1mr) must complete first
**Ready Tasks**: NONE (Epic 3 blocked until Epic 1 & 2 done)

**Assignment Template** (For later delegation after Epic 1 & 2 complete):
```markdown
MISSION: Implement responsive design, animations, and accessibility polish

GOALS:
1. Ensure all components adapt correctly across mobile/tablet/desktop breakpoints
2. Add page load animations (heading fade-in, search slide-up, filter stagger)
3. Run accessibility audit and fix all issues (WCAG AA compliance)
4. Optimize performance (bundle size, lazy loading, tree-shaking)
5. Test browser compatibility across all major browsers

ACCEPTANCE_CRITERIA:
- Mobile: Search stacks, filters scroll, cards 1-column, dropdown shown
- Tablet: Filters wrap, cards 2-column, map reduced
- Desktop: Side-by-side (40% categories, 60% map), centered container max-width 1280px
- Framer Motion animations smooth and performant
- axe-core audit score >95, all WCAG AA issues resolved
- Keyboard navigation works (Tab, Enter, Space, Escape)
- Bundle size <50KB, LCP <2.5s, CLS <0.1
- Tested on Chrome, Firefox, Safari, Edge, iOS Safari, Chrome Mobile

ADDITIONAL_CONTEXT:
- **Responsive Breakpoints**: sm(640px), md(768px), lg(1024px), xl(1280px)
- **Animations**: Framer Motion (optional), prefer CSS transitions for hover
- **Accessibility Tools**: axe-core, jest-axe for automated testing
- **Performance Tools**: next/bundle-analyzer, Lighthouse
- **Touch Targets**: Minimum 44x44px on mobile
- **Focus Indicators**: ring-2 ring-ring ring-offset-2

TASKS (Beads):
- dspy-cak: Implement responsive breakpoints
- dspy-b4e: Add page load animations
- dspy-c7f: Accessibility audit and fixes
- dspy-bdt: Performance optimization
- dspy-od8: Browser compatibility testing

**NOTE**: This worker should only be launched AFTER Epic 1 and Epic 2 are complete and verified.
```

---

## Validation Worker (Launched After Implementation)

**Session Name**: `worker-homepage-validation`
**Agent Type**: validation-agent
**Mode**: --mode=implementation
**Epic**: AT-Epic - 3-Level Validation (dspy-rqz)
**Trigger**: When Epic 1, 2, 3 implementation complete

**Assignment Template**:
```markdown
MISSION: Execute 3-level validation protocol for homepage hero redesign

MODE: --mode=implementation
TASK_ID: dspy-rqz (AT-Epic)

VALIDATION LEVELS:

**Level 1: Unit Tests (Task dspy-jhc)**
- Run all Jest + RTL tests for components
- Verify >90% coverage
- Capture test output logs + coverage report

**Level 2: API Integration Tests (Task dspy-p1o)**
- Verify mock endpoints working (/api/categories, /api/states/providers, /api/search)
- Test error handling (network failures, 404s)
- Capture API test logs

**Level 3: E2E Browser Tests (Task dspy-322)**
- Search flow: Enter query → Submit → Verify /search navigation
- Filter flow: Toggle filters → Submit → Verify filtered results
- Category navigation: Click card → Verify /category page
- Map interaction: Click state → Verify state-filtered results
- Keyboard navigation: Tab through elements → Enter/Space activates
- Mobile responsive: Verify dropdown shown, map hidden <640px
- Capture screenshots + execution logs

**Accessibility Compliance (Task dspy-kp3)**
- Run axe-core audit → must score >95
- Verify keyboard navigation on all elements
- Test screen reader compatibility
- Verify color contrast (4.5:1 minimum)
- Verify focus indicators visible
- Verify touch targets 44x44px minimum
- Capture axe-core report + manual test checklist

IF ALL PASS:
- Close all 4 AT tasks with evidence
- Close AT epic (dspy-rqz)
- Report to orchestrator → Functional epics can now close

IF ANY FAIL:
- Report failures to orchestrator
- Do NOT close tasks or epic
- Orchestrator will coordinate fixes before retrying validation
```

---

## Orchestrator Monitoring Strategy

**Background Haiku Agents**: Launch 3 monitoring agents (one per active worker)

**Monitor Template** (Per Worker):
```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=True,
    description=f"Monitor {worker_session_name}",
    prompt=f"""Monitor tmux session '{worker_session_name}' for completion signals.

CHECK EVERY 5 MINUTES:
- tmux capture-pane -t {worker_session_name} -p | tail -50
- Look for completion phrases: "All tasks complete", "Ready for validation", "Worker finished"
- Check beads status: bd list --status=in_progress | grep {worker_epic_id}

REPORT TO ORCHESTRATOR:
- Worker completion signals
- Blocked workers (stuck for >30 minutes)
- Error messages or failures
- Task status changes

DO NOT INTERVENE - Only observe and report."""
)
```

---

## Execution Sequence

1. **Phase 1**: Launch Worker 1 (Foundation) + Worker 2 (Navigation) in parallel
   - Create tmux sessions: `tmux new-session -d -s worker-homepage-foundation`, `tmux new-session -d -s worker-homepage-navigation`
   - Launch Claude Code: `tmux send-keys -t {session} "launchcc"`, `tmux send-keys -t {session} Enter`
   - Send assignments via tmux send-keys
   - Launch Haiku monitors for both workers

2. **Phase 2**: Monitor progress, intervene if blocked
   - Haiku agents report every 5 minutes
   - Orchestrator checks beads: `bd list --status=in_progress`
   - If worker stuck >30 min: inspect logs, provide guidance

3. **Phase 3**: Launch Worker 3 (Polish) after Epic 1 & 2 complete
   - Epic 3 dependencies automatically unblock when Epic 1 & 2 close
   - Same tmux delegation pattern

4. **Phase 4**: Launch Validation Worker after all implementation complete
   - Use validation-agent in implementation mode
   - Validation-agent runs 3-level protocol
   - Validation-agent closes tasks with evidence

5. **Phase 5**: Close functional epics after AT epic closes
   - AT epic closure unblocks Epic 1, 2, 3
   - Orchestrator delegates epic closures to validation-agent
   - Finally close business epic (dspy-o2t) after all functional epics closed

---

## Progress Tracking

**Beads Commands**:
```bash
# Check overall progress
bd stats

# Check ready work
bd ready --limit=20

# Check specific epic progress
bd show dspy-6d4  # Epic 1
bd show dspy-1mr  # Epic 2
bd show dspy-cbf  # Epic 3
bd show dspy-rqz  # AT Epic

# Check blocked issues
bd blocked
```

**Session Log**: `.claude/progress/orch-homepage-log.md`
**Worker Outputs**: Background task output files (Haiku monitors)
**Final Report**: To be sent to System 3 via message bus upon completion

---

**Status**: Ready for worker delegation
**Next Action**: Launch Worker 1 and Worker 2 in parallel via tmux


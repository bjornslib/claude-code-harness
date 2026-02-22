# Double-Fire Fix NEEDS_REWORK — 5a3f5bd0

**Date**: 2026-02-21
**Validator**: tdd-test-engineer (independent, agent a9c16c2)
**Commit validated**: 5a3f5bd0

## Verdict: FAIL — Fix Incomplete

### Static Checks: PASS (4/4)

| Check | Location | Result |
|---|---|---|
| `runFinishedFiredRef = useRef(false)` | Line 130 | PASS |
| `runFinishedFiredRef.current = false` reset before `sseClient.stream()` | Line 183 | PASS |
| Guard `if (runFinishedFiredRef.current) return;` as first statement in RUN_FINISHED | Lines 319-322 | PASS |
| `runFinishedFiredRef.current = true` immediately after guard | Line 323 | PASS |

### Browser Validation: FAIL

"Agent update successful" fired **2 times** per save operation.

Console evidence:
```
[9:24:01 AM] [SSE] RUN_FINISHED detected
[9:24:01 AM] [State Update] RUN_FINISHED - Final state: Object
[9:24:01 AM] [UniversityContactSheet] Agent update successful null   <-- fire #1
[9:24:01 AM] [State Update] RUN_FINISHED - Final state: Object       <-- SECOND setState call
[9:24:01 AM] [UniversityContactSheet] Agent update successful null   <-- fire #2
```

JavaScript counter confirmed: `__agentSuccessCount: 6` with RUN_FINISHED appearing twice at timestamps 22:24:01.333 and 22:24:01.336.

## Root Cause Analysis

The `runFinishedFiredRef` guard correctly prevents a **second SSE event** from entering the `RUN_FINISHED` handler. But the double-fire is happening **inside the `setState` updater function**, not from a second SSE event.

React 18 StrictMode calls `setState` updater functions **twice** to detect side effects. The `queueMicrotask(onSuccessCallback)` call is inside the updater, so it gets enqueued twice. The ref guard at the event handler level does not stop the updater from running twice.

```typescript
// Current code (BROKEN)
setState(prev => {
    // ...
    if (event.type === 'RUN_FINISHED') {
        const onSuccessCallback = options?.onSuccess;
        if (onSuccessCallback) {
            queueMicrotask(() => {   // <-- enqueued TWICE by StrictMode
                onSuccessCallback(finalState.current_result);
            });
        }
    }
    return newState;
});
```

## Required Fix

Move the `queueMicrotask` call **outside** the `setState` updater. React 18 StrictMode does not double-call code outside updaters.

```typescript
// Correct approach
let shouldCallSuccess = false;
setState(prev => {
    if (event.type === 'RUN_FINISHED') {
        shouldCallSuccess = true;  // flag only
        return { ...prev, status: 'success' };
    }
    return prev;
});

if (shouldCallSuccess && options?.onSuccess) {
    queueMicrotask(() => {
        options.onSuccess(finalState.current_result);
    });
}
```

Or use `useEffect` with a completion state instead of `queueMicrotask` inside updater.

**Note**: This double-fire does NOT break the F3.1 fix (779c9290). The stale sidebar fix is independent and validated. The double-fire causes the `handleAgentSuccess` to run twice, which triggers two optimistic Zustand updates — both with the same values, so the sidebar shows correct data. However it is wasteful and causes redundant progressive loader triggers.

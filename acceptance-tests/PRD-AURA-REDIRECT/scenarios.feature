Feature: /aura-call Post-Task Redirect Fix
  The Phone Call tab's Create Task button should NOT navigate to /verify-call/
  after successful task creation. It should show success feedback on the
  current /aura-call page. The Web Call tab's Make Call button should continue
  navigating to /verify-call/ as before.

  # ─────────────────────────────────────────────────────────────
  # F1: Phone Call tab post-submit behavior (weight: 0.45)
  # ─────────────────────────────────────────────────────────────

  Scenario: phone_call_no_redirect
    Given the user is on /aura-call with the Phone Call tab selected
    And valid employer details are filled in including a phone number
    When the user clicks "Create Task"
    And the POST to /api/verify returns HTTP 201
    Then the browser URL should remain on /aura-call (NOT /verify-call/)
    And no navigation to /verify-call/{taskId} should occur

    # Confidence scoring guide:
    # 1.0 — Code clearly prevents navigation for Phone Call flow; handleCreateTask
    #        does NOT call window.location.href or router.push to /verify-call/
    # 0.5 — Navigation removed but replaced with something ambiguous
    # 0.0 — handleCreateTask still navigates to /verify-call/{taskId}

    # Evidence to check:
    # - page.tsx: handleCreateTask function (~line 240-260)
    # - Look for window.location.href or router.push with /verify-call
    # - Verify callMode === 'phone' branch does NOT redirect

    # Red flags:
    # - window.location.href = `/verify-call/${taskId}` still present in handleCreateTask
    # - Conditional redirect based on callMode not implemented

  Scenario: phone_call_success_feedback
    Given the user is on /aura-call with the Phone Call tab selected
    When the Create Task POST succeeds with a taskId
    Then the user should see visual success feedback on the /aura-call page
    And the feedback should include the task ID or confirmation message

    # Confidence scoring guide:
    # 1.0 — Clear success UI: toast notification, banner, status change,
    #        or "Task created successfully" message visible to user
    # 0.5 — Some indication of success but unclear (e.g., console.log only)
    # 0.0 — No visible feedback; page just stays with no change

    # Evidence to check:
    # - page.tsx: state variable for success (e.g., taskCreated, showSuccess)
    # - JSX rendering success state (banner, toast, alert)
    # - Look for setTaskCreated(true) or similar after successful POST

    # Red flags:
    # - Only console.log without user-visible feedback
    # - Success feedback exists but is hidden behind wrong callMode check

  # ─────────────────────────────────────────────────────────────
  # F2: Web Call tab no-regression (weight: 0.35)
  # ─────────────────────────────────────────────────────────────

  Scenario: web_call_still_works
    Given the user is on /aura-call with the Web Call tab selected (default)
    When the user clicks "Make Call"
    Then the LiveKit session should start via onStartSession()
    And eventually the page should navigate to /verify-call/{taskId}

    # Confidence scoring guide:
    # 1.0 — Web Call flow is completely unchanged; onStartSession() still
    #        triggers LiveKit room creation and /verify-call navigation
    # 0.5 — Web Call flow works but has minor changes that could affect behavior
    # 0.0 — Web Call flow is broken or also prevented from navigating

    # Evidence to check:
    # - VoiceInterface.tsx: callMode !== 'phone' still calls onStartSession()
    # - page.tsx: handleCall / onStartSession function still navigates to /verify-call
    # - No callMode checks added that would block Web Call navigation

    # Red flags:
    # - All /verify-call navigation removed (not just for Phone Call)
    # - onStartSession() modified to skip navigation
    # - callMode check wrapping ALL navigation (should only wrap Phone Call)

  # ─────────────────────────────────────────────────────────────
  # F3: Error handling preserved (weight: 0.20)
  # ─────────────────────────────────────────────────────────────

  Scenario: api_error_no_redirect
    Given the user is on /aura-call with the Phone Call tab selected
    When the Create Task POST fails (4xx or 5xx)
    Then an error message should be displayed on the /aura-call page
    And NO navigation should occur

    # Confidence scoring guide:
    # 1.0 — Error handling in handleCreateTask shows error to user,
    #        no redirect occurs on failure
    # 0.5 — Errors are caught but feedback is unclear
    # 0.0 — Error causes redirect or unhandled exception

    # Evidence to check:
    # - page.tsx: catch block in handleCreateTask
    # - Error state displayed to user (setError or similar)
    # - No navigation in error path

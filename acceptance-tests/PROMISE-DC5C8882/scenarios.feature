Feature: Post-task-creation redirect fix on /aura-call

  Background:
    Given the /aura-call page is loaded
    And the user has filled in candidate and employer details
    And the Phone Call tab is active

  @F1-no-redirect
  Scenario: create-task-no-redirect
    """
    CRITICAL (weight: 0.40)
    After clicking Create Task, the page must NOT navigate to /verify-call/.
    The user should remain on /aura-call or see an in-page success state.

    Confidence Guide:
      0.0 - window.location.href = `/verify-call/${taskId}` still exists in handleCreateTask
      0.3 - Navigation removed but replaced with nothing (no feedback)
      0.5 - Navigation removed, some feedback exists but unclear
      0.8 - Navigation removed, clear success feedback, user stays on page
      1.0 - Navigation removed, clear success feedback, form resets or shows task ID

    Evidence to check:
      - page.tsx handleCreateTask function (around line 252-255)
      - Search for "verify-call" in handleCreateTask
      - Look for any replacement behavior (setState, toast, alert)

    Red flags:
      - verify-call still present in handleCreateTask
      - No replacement feedback mechanism
      - Redirect to a different wrong page
    """
    When the user clicks the "Create Task" button
    And the POST /api/verify returns 201 with a taskId
    Then the page URL should remain "/aura-call"
    And no navigation to "/verify-call/" should occur

  @F2-success-feedback
  Scenario: success-feedback-shown
    """
    IMPORTANT (weight: 0.25)
    After successful task creation, the user must see confirmation.
    This could be a toast, banner, status text, or visual state change.

    Confidence Guide:
      0.0 - No feedback at all after task creation
      0.3 - Console.log only (not visible to user)
      0.5 - Brief flash or easily-missed feedback
      0.8 - Clear visible feedback (toast, banner, or status text)
      1.0 - Clear feedback with task ID, option to view task, and form reset

    Evidence to check:
      - What replaces the navigation in handleCreateTask
      - Search for toast, notification, alert, or status state changes
      - Check if isLoading state is properly reset

    Red flags:
      - Only console.log as feedback
      - isLoading stays true forever after success
      - Error state shown despite success
    """
    When the user clicks "Create Task"
    And the task is created successfully
    Then the user should see a visible success indication
    And the success message should include the task ID or confirmation

  @F3-web-call-regression
  Scenario: web-call-still-navigates
    """
    IMPORTANT (weight: 0.25)
    The Web Call tab's "Make Call" button must still work as before.
    It should start a LiveKit session — this is the EXISTING behavior
    that must not be broken.

    Confidence Guide:
      0.0 - Make Call button broken or removed
      0.3 - Make Call exists but handler changed
      0.5 - Make Call handler exists, unclear if LiveKit flow intact
      0.8 - Make Call handler calls onStartSession (correct)
      1.0 - Make Call handler verified, LiveKit flow fully intact

    Evidence to check:
      - VoiceInterface.tsx handleStartCall function
      - Web Call (callMode !== 'phone') branch
      - onStartSession callback still called
      - startSession function in page.tsx unchanged

    Red flags:
      - onStartSession not called for web call mode
      - handleStartCall routing logic broken
      - startSession function modified
    """
    Given the Web Call tab is active
    When the user clicks "Make Call"
    Then the LiveKit voice session should start (onStartSession called)
    And the behavior should be identical to before the fix

  @F4-build
  Scenario: build-no-errors
    """
    BASIC (weight: 0.10)
    npx next build must pass with no errors.

    Confidence Guide:
      0.0 - Build fails
      0.5 - Build passes with warnings
      1.0 - Build passes cleanly

    Evidence to check:
      - Run: npx next build
      - Check exit code and output
    """
    When running "npx next build"
    Then the build should complete successfully
    And no TypeScript or compilation errors should appear

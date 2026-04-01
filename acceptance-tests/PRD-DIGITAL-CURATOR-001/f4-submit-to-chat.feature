@feature F4-SUBMIT-TO-CHAT
@method browser-required
@weight 0.30

Feature: Submit Comments to Chat Input
  Users must be able to submit all accumulated annotations as a single
  formatted message into Claude's chat input area. The message format
  uses quoted blocks for highlighted text and plain text for comments.
  After submission, all annotations and highlights are cleared.

  Background:
    Given the Digital Curator extension is active on claude.ai
    And the side panel is open
    And I have created at least 2 annotations with comments

  # -------------------------------------------------------------------
  # Scoring Guide (0.0 - 1.0):
  #   1.0: Submit injects formatted text, chat input populated, cleanup works
  #   0.8: Text injected correctly but minor formatting issues
  #   0.6: Text appears in chat input but missing some annotations or formatting
  #   0.4: Submit triggers but text injection fails (clipboard fallback used)
  #   0.2: Submit button exists but no text reaches the chat input
  #   0.0: No submit functionality at all
  # -------------------------------------------------------------------

  @critical
  Scenario: Submit button is visible and enabled with annotations
    Then the sidebar footer should display a "Submit All Comments" button
    And the button should be styled in coral/primary color (#D97757)
    And the button should be enabled (clickable)
    And the button should have an arrow icon indicating action

  @critical
  Scenario: Clicking Submit injects formatted text into chat input
    When I click the "Submit All Comments" button
    Then Claude's chat input area should contain formatted text
    And the formatted text should start with an introductory line
    And for each annotation, the text should contain:
      | Element                | Format                                    |
      | Quoted highlighted text | Prefixed with ">" as a blockquote         |
      | Comment text           | Plain text below the quote                 |
      | Separator              | "---" or blank line between annotations    |

  @critical
  Scenario: Submitted text is editable before sending
    When I click "Submit All Comments"
    And the formatted text appears in Claude's chat input
    Then the chat input should have focus
    And I should be able to edit the inserted text
    And I should be able to position my cursor within the text
    And the text should NOT be automatically sent to Claude

  @critical
  Scenario: Highlights and sidebar clear after submission
    When I click "Submit All Comments"
    Then all coral highlights in the conversation should be removed
    And the sidebar should show the empty state ("No comments yet")
    And the sidebar badge count should show 0 or be hidden

  Scenario: Submit button state machine
    When I click "Submit All Comments"
    Then the button should show "Processing..." with reduced opacity
    And after approximately 1-2 seconds the button should show "Sent Successfully!"
    And the button background should change to green
    And after approximately 2 seconds the button should reset to its default state

  Scenario: Submit with no annotations shows disabled button
    Given I have deleted all annotations so the sidebar is empty
    Then the "Submit All Comments" button should be disabled or hidden
    And clicking it should have no effect

  Scenario: Format preserves annotation order
    Given I created annotation A on text "First paragraph text"
    And I created annotation B on text "Second paragraph text"
    When I click "Submit All Comments"
    Then the formatted text in the chat input should contain both annotations
    And annotation A's quoted text should appear in the output
    And annotation B's quoted text should appear in the output
    And each annotation should have its quoted text followed by its comment

  Scenario: Chat input injection handles contenteditable correctly
    When I click "Submit All Comments"
    Then the text should appear in Claude's contenteditable chat input div
    And the console should log "[DC]:EVENT:submit.injected"
    And the event data should include the injection method used
    And Claude's UI should recognize the inserted text (send button enabled)

  Scenario: Clipboard fallback when injection fails
    Given Claude's chat input structure has changed unexpectedly
    When I click "Submit All Comments"
    And the primary injection method fails
    Then the formatted text should be copied to the clipboard
    And a notification should inform the user to paste manually
    And the console should log "[DC]:EVENT:submit.fallback" with method "clipboard"

  Scenario: Submit with single annotation works correctly
    Given I have exactly 1 annotation
    When I click "Submit All Comments"
    Then the chat input should contain the single annotation's quoted text and comment
    And the formatting should be clean (no extra separators or blank lines)

  Scenario: Long annotations format correctly
    Given I have an annotation where the highlighted text is longer than 200 characters
    When I click "Submit All Comments"
    Then the full highlighted text should appear in the quoted block
    And the formatting should remain readable (properly line-wrapped in the blockquote)

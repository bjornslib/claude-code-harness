@feature F3-COMMENT-SIDEBAR
@method browser-required
@weight 0.30

Feature: Comment Popover & Annotation Sidebar
  Users must be able to create, edit, and delete comments via an inline
  popover editor. All annotations appear in a right-hand sidebar panel
  with quoted text excerpts, timestamps, and action buttons. The sidebar
  and content highlights are bidirectionally linked.

  Background:
    Given the Digital Curator extension is active on claude.ai
    And there is at least one completed assistant response visible
    And the side panel is open

  # -------------------------------------------------------------------
  # Scoring Guide (0.0 - 1.0):
  #   1.0: Full CRUD works, sidebar displays correctly, bidirectional linking
  #   0.8: Create and display work, minor issues with edit/delete
  #   0.6: Comments save and display but popover positioning or styling off
  #   0.4: Comments save but sidebar doesn't update or vice versa
  #   0.2: Popover appears but save fails or sidebar is empty
  #   0.0: No comment creation flow at all
  # -------------------------------------------------------------------

  @critical
  Scenario: Comment popover opens after clicking floating icon
    Given I have selected text in an assistant message
    And a floating comment icon is visible
    When I click the floating comment icon
    Then a comment editor popover should appear near the selected text
    And the popover should contain a textarea with placeholder text
    And the popover should have "Discard" and "Save" buttons
    And the popover should show user identity (e.g., "You (Reviewing)")

  @critical
  Scenario: Saving a comment creates an annotation
    Given the comment editor popover is open
    When I type "This needs more detail on the origin story" into the textarea
    And I click the "Save" button
    Then the popover should close
    And the selected text should receive a persistent coral highlight
    And the console should log "[DC]:EVENT:annotation.created"
    And the annotation should appear in the sidebar as a new card

  @critical
  Scenario: Annotation card displays correctly in sidebar
    Given I have created an annotation with comment "Fix this section"
    Then the sidebar should show an annotation card containing:
      | Field            | Expected Content                    |
      | Header badge     | Count showing at least "1"          |
      | Quoted text      | The text I originally selected       |
      | Comment body     | "Fix this section"                  |
      | User avatar      | Initials or avatar visible           |
      | Timestamp        | Relative time (e.g., "Just now")     |

  @critical
  Scenario: Sidebar badge count updates with each annotation
    Given I have created 0 annotations
    Then the sidebar header should show "0" or empty badge
    When I create one annotation
    Then the sidebar badge should show "1"
    When I create a second annotation
    Then the sidebar badge should show "2"

  Scenario: Keyboard shortcut Cmd+Enter saves comment
    Given the comment editor popover is open
    And I have typed a comment into the textarea
    When I press Cmd+Enter (or Ctrl+Enter on non-Mac)
    Then the comment should be saved
    And the popover should close
    And a new annotation card should appear in the sidebar

  Scenario: Escape key discards comment
    Given the comment editor popover is open
    When I press the Escape key
    Then the popover should close
    And no annotation should be created
    And the text selection highlight should be removed

  Scenario: Editing an existing annotation
    Given I have created an annotation with comment "Initial comment"
    When I click the edit icon on the annotation card in the sidebar
    Then the comment body should become editable (textarea or inline edit)
    When I change the text to "Updated comment"
    And I confirm the edit (Save or Enter)
    Then the annotation card should display "Updated comment"
    And the highlight in the content should remain unchanged

  Scenario: Deleting an annotation
    Given I have created an annotation
    When I click the delete icon on the annotation card in the sidebar
    Then the annotation card should be removed from the sidebar
    And the corresponding highlight in the content should be removed
    And the sidebar badge count should decrease by 1

  Scenario: Clicking sidebar card scrolls to highlight
    Given I have created an annotation on text that is currently off-screen
    When I click on the annotation card in the sidebar
    Then the conversation should scroll to the highlighted text
    And the highlight should pulse or flash briefly to draw attention

  Scenario: Hovering highlight emphasizes sidebar card
    Given I have created multiple annotations
    When I hover over a specific highlight in the conversation content
    Then the corresponding annotation card in the sidebar should be visually emphasized
    And other cards should remain in their default state

  Scenario: Popover renders in Shadow DOM isolation
    Given the comment editor popover is open
    Then the popover should not inherit any Claude.ai CSS styles
    And the popover should use the Digital Curator design tokens (Inter font, coral accents)
    And Claude.ai elements behind the popover should not be affected

  Scenario: Multiple annotations display in chronological order
    Given I create annotation A at time T1
    And I create annotation B at time T2
    Then annotation B should appear above annotation A in the sidebar
    Or annotations should be ordered with newest first

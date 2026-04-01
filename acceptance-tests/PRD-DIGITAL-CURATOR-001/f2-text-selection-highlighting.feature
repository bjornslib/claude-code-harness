@feature F2-TEXT-SELECTION-HIGHLIGHTING
@method browser-required
@weight 0.25

Feature: Text Selection & Highlighting
  Users must be able to select text within Claude's assistant responses
  and see a floating comment icon appear. Upon initiating an annotation,
  the selected text receives a persistent coral highlight. Selections in
  user messages, streaming responses, and non-message areas are ignored.

  Background:
    Given the Digital Curator extension is active on claude.ai
    And there is at least one completed assistant response visible

  # -------------------------------------------------------------------
  # Scoring Guide (0.0 - 1.0):
  #   1.0: All selection scenarios work, highlights persist, streaming excluded
  #   0.8: Selection works on prose text, minor issues with edge cases
  #   0.6: Selection captures text but highlights have visual issues
  #   0.4: Selection works but floating icon doesn't appear
  #   0.2: Selection detected but anchoring fails (cannot re-find text)
  #   0.0: No text selection detection at all
  # -------------------------------------------------------------------

  @critical
  Scenario: Selecting text in assistant response shows comment icon
    When I select a portion of text within an assistant message
    Then a floating comment icon should appear near the selection
    And the console should log "[DC]:EVENT:selection.captured"
    And the event data should include the selected text

  @critical
  Scenario: Highlight renders with correct styling after annotation
    Given I have selected text in an assistant message
    When I complete an annotation on that text
    Then the selected text should have a visible coral-colored highlight
    And the highlight should have approximately 20% opacity background
    And the highlight should have a 2px solid bottom border in coral (#D97757)

  @critical
  Scenario: Highlight persists after scrolling
    Given I have created an annotation with a visible highlight
    When I scroll the conversation away from the highlighted text
    And I scroll back to the highlighted text
    Then the coral highlight should still be visible on the annotated text

  Scenario: Selecting text in user message is ignored
    When I select text within a user message (not an assistant response)
    Then no floating comment icon should appear
    And the console should NOT log "[DC]:EVENT:selection.captured"

  Scenario: Streaming response text is not annotatable
    Given an assistant response is currently streaming (being generated)
    When I attempt to select text in the streaming message
    Then no floating comment icon should appear
    And the console should NOT log "[DC]:EVENT:selection.captured"

  Scenario: Selection spanning multiple paragraphs
    When I select text that spans across two paragraphs in an assistant message
    Then the floating comment icon should appear
    And the captured text should include content from both paragraphs
    And the resulting highlight should span both paragraphs visually

  Scenario: Selection within bold or formatted text
    When I select text that includes bold, italic, or inline code formatting
    Then the floating comment icon should appear
    And the captured text should be the plain text content (formatting stripped)
    And the highlight should render correctly over the formatted text

  Scenario: Clicking elsewhere dismisses the floating icon
    Given a floating comment icon is visible after a text selection
    When I click on an area outside the selected text
    Then the floating comment icon should disappear
    And the text selection should be cleared

  Scenario: Highlight hover intensifies the visual
    Given an annotation highlight exists on the page
    When I hover the mouse cursor over the highlighted text
    Then the highlight opacity should increase (visually brighter/darker)
    And the corresponding annotation card in the sidebar should receive emphasis

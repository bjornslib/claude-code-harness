@feature F1-EXTENSION-INFRASTRUCTURE
@method browser-required
@weight 0.15

Feature: Extension Infrastructure & Loading
  The Digital Curator Chrome extension must load cleanly on claude.ai,
  inject its content script, register the side panel, and present an
  empty state without interfering with Claude.ai's native functionality.

  Background:
    Given the Digital Curator extension is installed in Chrome
    And Chrome is navigated to "https://claude.ai"
    And the page has fully loaded

  # -------------------------------------------------------------------
  # Scoring Guide (0.0 - 1.0):
  #   1.0: All assertions pass, zero console errors, side panel renders
  #   0.8: Extension loads with minor warnings but no functional impact
  #   0.5: Extension loads but side panel fails or content script partial
  #   0.2: Extension fails to load or produces console errors
  #   0.0: Extension not installable or crashes Chrome tab
  # -------------------------------------------------------------------

  @critical
  Scenario: Content script injects on claude.ai
    Then the global flag "__DIGITAL_CURATOR_LOADED__" should be "true"
    And the console should contain a log matching "[DC] Content script loaded"
    And the console should contain zero errors matching "[DC]" or "Digital Curator"

  @critical
  Scenario: Extension does not interfere with Claude.ai
    When I type "hello" into Claude's chat input
    Then Claude's chat input should contain "hello"
    And Claude's send button should be clickable
    And no Claude.ai UI elements should be obscured or displaced

  @critical
  Scenario: Side panel opens with empty state
    When I click the Digital Curator extension icon in the Chrome toolbar
    Then the side panel should open on the right side
    And the side panel should display "Active Annotations" as the header
    And the side panel should display an empty state with text containing "No comments yet"
    And the side panel should display guidance text containing "Select text"

  Scenario: Extension popup shows toggle
    When I click the Digital Curator extension icon
    Then a popup should appear with an on/off toggle
    And the toggle should be in the "on" position by default

  Scenario: Build produces valid extension
    Given the extension source code exists
    When I run "npm run ci"
    Then the command should exit with code 0
    And the "dist/" directory should contain a "manifest.json"
    And the manifest version should be 3
    And the manifest should declare "sidePanel" in permissions
    And the manifest should declare "https://claude.ai/*" in host_permissions

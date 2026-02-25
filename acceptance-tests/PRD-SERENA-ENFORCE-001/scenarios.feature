@prd-SERENA-ENFORCE-001
Feature: Serena MCP Usage Enforcement Hooks

  Background:
    Given a Claude Code project at CLAUDE_PROJECT_DIR
    And Serena is configured with .serena/project.yml present

  @AC-1
  Scenario: PreToolUse blocks Read on Python source code
    When the agent calls Read with file_path ending in ".py"
    And the file is under a source code directory (not .claude/, .taskmaster/, docs/)
    Then the hook returns {"decision": "block"}
    And the reason mentions "Serena" and "find_symbol"

    # Scoring guide:
    # 1.0 — Hook blocks .py reads with clear Serena redirect message
    # 0.5 — Hook blocks but message is generic (no Serena tool suggestion)
    # 0.0 — Hook approves .py reads when Serena is active

  @AC-1
  Scenario: PreToolUse approves Read on markdown files
    When the agent calls Read with file_path ending in ".md"
    Then the hook returns {"decision": "approve"}

    # Scoring guide:
    # 1.0 — Non-code files always approved without delay
    # 0.0 — Non-code files blocked or delayed

  @AC-2
  Scenario: PreToolUse blocks Grep on source code directories
    When the agent calls Grep with path pointing to a source directory
    And files in that directory are source code (.py, .ts, .tsx)
    Then the hook returns {"decision": "block"}
    And the reason mentions "search_for_pattern" as alternative

    # Scoring guide:
    # 1.0 — Grep on source dirs blocked with Serena alternative
    # 0.5 — Grep blocked but no alternative suggested
    # 0.0 — Grep on source dirs not intercepted

  @AC-3
  Scenario: Fast path for non-code files
    When the agent calls Read with file_path ending in ".json", ".yaml", ".md", ".txt"
    Then the hook approves in under 5ms
    And no Serena check is performed

    # Scoring guide:
    # 1.0 — Extension-based fast path, measurably fast (<5ms)
    # 0.5 — Correct approval but checks Serena status unnecessarily
    # 0.0 — Significant overhead on non-code files

  @AC-4
  Scenario: Graceful degradation without Serena
    Given .serena/project.yml does NOT exist
    When the agent calls Read with file_path ending in ".py"
    Then the hook returns {"decision": "approve"}
    And no error or warning is emitted

    # Scoring guide:
    # 1.0 — Silent approval when Serena not configured
    # 0.5 — Approval but with warning messages
    # 0.0 — Blocks or errors when Serena not present

  @AC-5
  Scenario: Bypass via environment variable
    Given SERENA_ENFORCE_SKIP=1 is set in the environment
    When the agent calls Read with file_path ending in ".py"
    Then the hook returns {"decision": "approve"}
    And bypass is logged for debugging

    # Scoring guide:
    # 1.0 — Env var bypass works, documented in hook output
    # 0.5 — Bypass works but no indication it was bypassed
    # 0.0 — Bypass mechanism not implemented

  @AC-5
  Scenario: Bypass via signal file
    Given .claude/.serena-enforce-skip file exists
    When the agent calls Read with file_path ending in ".py"
    Then the hook returns {"decision": "approve"}

    # Scoring guide:
    # 1.0 — Signal file bypass works
    # 0.0 — Signal file not checked

  @AC-6
  Scenario: PostToolUse async advisory
    Given the PostToolUse hook is configured with async: true
    When the agent completes a Read on a non-code file
    And Serena is active
    Then the hook returns a systemMessage reminding about Serena
    And the message is delivered on the next conversation turn
    And no blocking or delay occurs

    # Scoring guide:
    # 1.0 — Async advisory works, non-blocking, helpful message
    # 0.5 — Advisory works but is synchronous (adds latency)
    # 0.0 — No advisory layer implemented

  @AC-7
  Scenario: Glob tool not affected
    When the agent calls Glob with pattern "**/*.py"
    Then the hook does NOT fire (not in matcher)
    And Glob executes normally

    # Scoring guide:
    # 1.0 — Glob is not in the matcher, unaffected
    # 0.0 — Glob is intercepted by the hook

  @AC-8
  Scenario: Settings.json properly configured
    Then .claude/settings.json contains a PreToolUse entry
    And the matcher is "Read|Grep"
    And the hook command points to serena-enforce-pretool.py
    And .claude/settings.json contains a PostToolUse entry for serena-enforce-posttool.py
    And the PostToolUse entry has async: true

    # Scoring guide:
    # 1.0 — Both entries present with correct matchers and async flag
    # 0.5 — PreToolUse present but PostToolUse missing or not async
    # 0.0 — Neither hook registered in settings.json

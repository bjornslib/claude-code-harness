# Blind Acceptance Tests: TMUX-SPAWN-BUG
# Fix tmux orchestrator spawn pattern
#
# Bead: claude-harness-setup-2h4n
# These tests are BLIND — the S3 operator does not see this file.

Feature: SPAWN-1 — exec zsh added to spawn sequence
  Weight: 0.40

  Scenario: SKILL.md includes exec zsh in spawn sequence
    Given .claude/skills/system3-orchestrator/SKILL.md
    When I read the SPAWN WORKFLOW section (Option B: Manual tmux Commands)
    Then "exec zsh" appears AFTER "cd to worktree" and BEFORE env var exports
    And there is a sleep after exec zsh (at least 1 second)
    And a comment explains WHY exec zsh is needed (tmux defaults to bash)

    # Scoring Guide:
    #   1.0 — exec zsh present, correctly ordered, sleep after, comment explaining why
    #   0.7 — exec zsh present and correctly ordered, but no sleep or no comment
    #   0.3 — exec zsh mentioned but in wrong position (e.g., after env vars)
    #   0.0 — No exec zsh in spawn sequence

    # Evidence to check:
    #   - .claude/skills/system3-orchestrator/SKILL.md: SPAWN WORKFLOW section
    #   - Order: cd → exec zsh → sleep → unset CLAUDECODE → env vars → ccorch
    #   - Comment about bash vs zsh

    # Red flags:
    #   - "exec bash" instead of "exec zsh"
    #   - exec zsh AFTER ccorch (too late)
    #   - No sleep between exec zsh and next command (zsh hasn't initialized)


Feature: SPAWN-2 — unset CLAUDECODE before ccorch
  Weight: 0.25

  Scenario: SKILL.md includes unset CLAUDECODE
    Given .claude/skills/system3-orchestrator/SKILL.md
    When I read the SPAWN WORKFLOW section
    Then "unset CLAUDECODE" appears BEFORE ccorch launch
    And it appears AFTER exec zsh
    And a comment explains it prevents nested session error

    # Scoring Guide:
    #   1.0 — unset CLAUDECODE present, correct order, comment explains why
    #   0.7 — unset CLAUDECODE present and correct order, no comment
    #   0.3 — CLAUDECODE mentioned but not actually unset
    #   0.0 — No unset CLAUDECODE

    # Evidence to check:
    #   - Exact text: tmux send-keys -t "orch-[name]" "unset CLAUDECODE"
    #   - Position: after exec zsh, before ccorch

    # Red flags:
    #   - "export CLAUDECODE=" instead of "unset CLAUDECODE"
    #   - unset AFTER ccorch (too late)


Feature: SPAWN-3 — Wisdom injection via file reference
  Weight: 0.20

  Scenario: SKILL.md uses file reference instead of tmux paste
    Given .claude/skills/system3-orchestrator/SKILL.md
    When I read the wisdom injection step
    Then the pattern uses a file reference like "Read the file at /tmp/wisdom-{name}.md"
    And does NOT paste markdown content directly via tmux send-keys
    And the wisdom file is created BEFORE the tmux spawn

    # Scoring Guide:
    #   1.0 — File reference pattern used, file creation step documented, no direct paste
    #   0.7 — File reference used but file creation step missing
    #   0.3 — Mixed approach (some paste, some file reference)
    #   0.0 — Still using tmux paste-buffer for wisdom injection

    # Evidence to check:
    #   - SPAWN WORKFLOW: look for "cat > /tmp/wisdom" or "Write wisdom file"
    #   - tmux send-keys with "Read the file at" or "Read /tmp/wisdom"
    #   - NO tmux send-keys with "$(cat /tmp/wisdom...)" pattern

    # Red flags:
    #   - tmux send-keys with multi-line heredoc content
    #   - $(cat ...) substitution in tmux send-keys (markdown will break)


Feature: SPAWN-4 — Complete 10-step sequence documented
  Weight: 0.15

  Scenario: All 10 steps present in correct order
    Given .claude/skills/system3-orchestrator/SKILL.md
    When I read the full SPAWN WORKFLOW section
    Then the following steps appear in order:
      | Step | Command/Action |
      | 1 | tmux new-session -d -s orch-{name} |
      | 2 | cd to worktree |
      | 3 | exec zsh |
      | 4 | sleep (wait for zsh) |
      | 5 | unset CLAUDECODE |
      | 6 | export env vars (SESSION_DIR, SESSION_ID, TASK_LIST_ID, AGENT_TEAMS) |
      | 7 | ccorch |
      | 8 | sleep (wait for Claude Code init) |
      | 9 | /output-style orchestrator |
      | 10 | wisdom injection via file reference |

    # Scoring Guide:
    #   1.0 — All 10 steps present in correct order
    #   0.8 — 8-9 steps present, correct order
    #   0.6 — 6-7 steps present, correct order
    #   0.4 — Steps present but wrong order (e.g., env vars before exec zsh)
    #   0.2 — Only partial sequence (fewer than 6 steps)
    #   0.0 — Spawn sequence not updated at all

    # Evidence to check:
    #   - Count distinct steps in the Option B manual tmux section
    #   - Verify ordering matches the 10-step sequence above
    #   - Each step uses separate send-keys + Enter (Pattern 1 compliance)

    # Red flags:
    #   - Steps combined into single send-keys call
    #   - Missing sleeps between exec zsh and next command
    #   - Enter on same line as command text (Pattern 1 violation)

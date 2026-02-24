@prd-PREFILTER-001 @epic-1 @code-analysis
Feature: PRD-PREFILTER-001 Epic 1 — CLI Pipeline Integration

  Background:
    Given the implementation repo is at "/Users/theb/Documents/Windsurf/DSPY_PreEmploymentDirectory_PoC"
    And the target files are "newsletter-agents/cli.py" and "newsletter-agents/prefilter.py"

  # ========================================================================
  # F1: Trusted Source Bypass (_split_by_trust)
  # Weight: 0.25
  # ========================================================================

  @feature-F1 @weight-0.25
  Scenario: Trusted source bypass correctly identifies NAPBS, SHRM, FCRA.com
    Given cli.py defines a trusted source list or constant
    When an article has source_url containing "napbs.com"
    Then the article is classified as trusted and bypasses filtering
    When an article has source_url containing "shrm.org"
    Then the article is classified as trusted and bypasses filtering
    When an article has source_url containing "fcra.com"
    Then the article is classified as trusted and bypasses filtering
    When an article has source_url containing "randomnews.com"
    Then the article is classified as unvetted and goes through filtering

    # Confidence scoring guide:
    # 1.0 — _split_by_trust() or equivalent function exists, correctly handles all 3
    #        trusted domains (napbs.com, shrm.org, fcra.com), uses substring matching
    #        on source_url field, returns two separate lists (trusted, unvetted),
    #        and has unit tests covering each trusted source
    # 0.5 — Function exists but only handles some trusted sources, or uses exact match
    #        instead of substring, or lacks unit tests
    # 0.0 — No trusted source bypass implemented, or trusted sources are hardcoded
    #        inline without a clear function/constant

    # Evidence to check:
    # - cli.py: Look for TRUSTED_SOURCES constant or _split_by_trust() function
    # - cli.py: Verify all 3 domains present: napbs.com, shrm.org, fcra.com
    # - cli.py: Check that source_url field is used (not title or other field)
    # - tests/test_prefilter_integration.py: Look for test_split_by_trust_* tests

    # Red flags:
    # - Trusted sources list is empty or only has 1-2 domains
    # - Matching uses exact URL equality instead of substring/contains
    # - No separation between trusted and unvetted — all go through same path
    # - Tests mock the trust function entirely (hollow tests)

  # ========================================================================
  # F2: Pre-filter Pipeline Wiring
  # Weight: 0.30
  # ========================================================================

  @feature-F2 @weight-0.30
  Scenario: Pre-filter is wired between ingest_from_feeds() and store loop
    Given cli.py has an ingest() command or function
    When ingest_from_feeds() returns a list of articles
    Then the articles are split into trusted and unvetted streams
    And prefilter.filter_relevant_only() is called on the unvetted stream
    And the threshold parameter is set to 0.6
    And the filtered results are passed to the store.insert() loop

    # Confidence scoring guide:
    # 1.0 — In cli.py ingest() command: articles fetched via ingest_from_feeds(),
    #        then split by trust, then filter_relevant_only(unvetted, threshold=0.6)
    #        called, then recombined trusted+filtered passed to store loop.
    #        Import of prefilter module present. Integration point is in cli.py,
    #        NOT inside ingestion.py (per PRD anti-pattern guidance)
    # 0.5 — Filter is wired but threshold is wrong, or filter is inside
    #        ingestion.py instead of cli.py, or trusted bypass is missing
    # 0.0 — No prefilter wiring at all — articles go directly from
    #        ingest_from_feeds() to store.insert() unchanged

    # Evidence to check:
    # - cli.py: import statement for prefilter module
    # - cli.py: ingest() function body — look for filter_relevant_only() call
    # - cli.py: threshold=0.6 in the filter call
    # - cli.py: verify filter is BETWEEN fetch and store, not inside ingestion.py
    # - prefilter.py: should NOT be modified (PRD says no changes needed)

    # Red flags:
    # - prefilter imported but never called in ingest()
    # - Filter placed inside ingestion.py (violates PRD architecture decision)
    # - Threshold missing or hardcoded to different value
    # - store.insert() loop receives unfiltered articles variable
    # - prefilter.py has modifications (PRD says module already complete)

  # ========================================================================
  # F3: Pre-filter Statistics Display
  # Weight: 0.15
  # ========================================================================

  @feature-F3 @weight-0.15
  Scenario: CLI displays pre-filter statistics panel
    Given the pre-filter has been applied to a batch of articles
    When the ingest command runs
    Then a statistics panel is displayed showing:
      | Field              | Expected Format           |
      | passed count       | integer, green colored    |
      | filtered count     | integer, red colored      |
      | pass_rate          | percentage (e.g., 45.2%)  |
      | avg_score          | float (e.g., 0.72)        |
      | trusted_bypassed   | integer, cyan colored     |

    # Confidence scoring guide:
    # 1.0 — Rich Panel rendered with all 5 statistics: passed (green),
    #        filtered (red), pass_rate (percentage), avg_score (float),
    #        trusted count (cyan). Uses prefilter.get_prefilter_stats() or
    #        prefilter.batch_filter() to compute stats. Panel has a title.
    # 0.5 — Some stats displayed but missing 1-2 fields, or plain text
    #        output without Rich formatting, or trusted count missing
    # 0.0 — No statistics displayed at all — filter runs silently

    # Evidence to check:
    # - cli.py: Panel() or console.print() call with pre-filter stats
    # - cli.py: get_prefilter_stats() or batch_filter() called for stats data
    # - cli.py: trusted count included in the output
    # - Look for Rich markup: [green], [red], [cyan] color annotations

    # Red flags:
    # - Stats computed but never printed
    # - Only pass/fail counts, missing rate and score
    # - Trusted bypass count not shown separately
    # - Print statement instead of Rich Panel (inconsistent with existing CLI style)

  # ========================================================================
  # F4: --no-prefilter Escape Hatch
  # Weight: 0.10
  # ========================================================================

  @feature-F4 @weight-0.10
  Scenario: --no-prefilter CLI flag bypasses all filtering
    Given the ingest command has a --no-prefilter option
    When ingest is called with --no-prefilter flag
    Then no articles are filtered — all go directly to store
    And no pre-filter statistics panel is displayed
    And trusted source bypass is also skipped (not needed)

    # Confidence scoring guide:
    # 1.0 — Click/Typer option --no-prefilter (boolean flag) added to ingest().
    #        When set, the entire pre-filter block (split, filter, stats) is
    #        skipped. All articles from ingest_from_feeds() go directly to
    #        store loop unchanged. Flag is documented in --help.
    # 0.5 — Flag exists but only partially skips (e.g., skips filter but
    #        still splits by trust), or flag name is different
    # 0.0 — No escape hatch flag implemented

    # Evidence to check:
    # - cli.py: @click.option or typer.Option for --no-prefilter
    # - cli.py: conditional block checking the flag before filter logic
    # - cli.py: when flag is True, articles pass through unmodified

    # Red flags:
    # - Flag added but not wired to skip the filter block
    # - Flag defaults to True (filter off by default — wrong direction)
    # - Flag skips filter but still computes/displays stats (confusing UX)

  # ========================================================================
  # F5: Integration Tests and Zero Breakage
  # Weight: 0.10
  # ========================================================================

  @feature-F5 @weight-0.10
  Scenario: New integration tests exist and existing tests still pass
    Given the test suite at newsletter-agents/tests/
    When pytest is run on the full test suite
    Then all existing tests pass with zero failures
    And new test file test_prefilter_integration.py exists
    And new tests cover _split_by_trust and apply_prefilter wrapper

    # Confidence scoring guide:
    # 1.0 — test_prefilter_integration.py exists with tests for:
    #        _split_by_trust (trusted identification, unvetted separation),
    #        apply_prefilter or equivalent wrapper function,
    #        prefilter stats computation, --no-prefilter flag behavior.
    #        Existing test suite runs clean (zero new failures).
    # 0.5 — Some tests exist but coverage is incomplete (e.g., only
    #        _split_by_trust tested, not the full pipeline), or 1-2
    #        existing tests broken by the changes
    # 0.0 — No new tests created, or existing tests broken

    # Evidence to check:
    # - tests/test_prefilter_integration.py: file exists
    # - tests/test_prefilter_integration.py: test functions for trust split
    # - tests/test_prefilter_integration.py: test for filter reduction
    # - tests/test_prefilter_integration.py: test for --no-prefilter bypass
    # - Run: pytest newsletter-agents/tests/ — check for failures

    # Red flags:
    # - Test file created but empty or only has imports
    # - Tests mock everything (filter, split, stats) — hollow tests
    # - Existing test_ingestion.py or test_cli.py now failing
    # - No assertion on article count reduction after filtering

  # ========================================================================
  # F6: Recombine Trusted + Filtered Streams
  # Weight: 0.10
  # ========================================================================

  @feature-F6 @weight-0.10
  Scenario: Trusted and filtered articles are recombined for storage
    Given some articles are from trusted sources
    And some articles pass the pre-filter
    When both streams are processed
    Then the final list passed to store contains trusted + filtered articles
    And no articles are duplicated
    And the order preserves trusted articles first

    # Confidence scoring guide:
    # 1.0 — After trust split and filter, code explicitly recombines:
    #        `articles = trusted + filtered` (or equivalent). The recombined
    #        list is what feeds the store.insert() loop. No duplication
    #        possible (trusted and unvetted are mutually exclusive sets).
    # 0.5 — Recombination happens but through a less clear mechanism
    #        (e.g., filtering modifies list in-place, trusted appended later)
    # 0.0 — Only filtered articles reach the store, trusted articles
    #        are lost — or only trusted articles stored, filtered dropped

    # Evidence to check:
    # - cli.py: explicit recombination line (trusted + filtered)
    # - cli.py: the recombined variable feeds the store loop
    # - cli.py: verify no path where trusted articles are dropped
    # - cli.py: verify no path where articles appear in both lists

    # Red flags:
    # - trusted list computed but never used after split
    # - Store loop uses the unfiltered original articles variable
    # - Trusted articles filtered again after recombination
    # - No clear variable tracking which list feeds the store

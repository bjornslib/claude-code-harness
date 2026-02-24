@journey @prd-PREFILTER-001 @J1 @code-analysis @smoke
Feature: J1 — Pre-filter reduces ingestion noise by 70-90%

  Background:
    Given the implementation repo is at "/Users/theb/Documents/Windsurf/DSPY_PreEmploymentDirectory_PoC"

  Scenario J1: Ingesting feeds with pre-filter produces cleaner dataset than without
    # Goal G1 + G2 combined: wire pre-filter with trusted bypass
    # This journey crosses: CLI layer → Pre-filter module → Store layer

    # CLI layer
    Given cli.py imports the prefilter module
    And cli.py ingest() command has the pre-filter wired in

    # Pre-filter module layer
    When a batch of 20 mixed articles is prepared:
      | source_url             | title                               | expected_outcome |
      | napbs.com/article1     | NAPBS Background Check Standards    | trusted_bypass   |
      | shrm.org/news/2026     | SHRM Employment Screening Update    | trusted_bypass   |
      | fcra.com/compliance    | FCRA Compliance Requirements        | trusted_bypass   |
      | randomsite.com/sports  | Lakers Win Championship             | filtered_out     |
      | newssite.com/recipes   | Best Chocolate Cake Recipe          | filtered_out     |
      | hrnews.com/screening   | New Background Check Regulations    | passes_filter    |
      | legalsite.com/fcra     | FCRA Amendment Discussion           | passes_filter    |

    Then _split_by_trust() separates 3 trusted articles
    And filter_relevant_only(unvetted, threshold=0.6) filters irrelevant articles
    And the recombined list contains trusted + relevant articles only

    # Store layer
    And the store.insert() loop receives fewer articles than the original batch
    And no trusted source articles are missing from the final list

    # Confidence scoring guide:
    # 1.0 — Full pipeline: split → filter → recombine → store with correct counts.
    #        Trusted articles always pass. Irrelevant articles (sports, recipes) filtered.
    #        Relevant articles (HR, legal, screening) pass the keyword filter.
    # 0.5 — Pipeline wired but some articles misclassified (e.g., trusted filtered,
    #        or irrelevant passes through)
    # 0.0 — Pipeline not wired, or all articles pass through unfiltered

    # Evidence to check:
    # - cli.py: complete flow from ingest_from_feeds → split → filter → recombine → store
    # - prefilter.py: RELEVANCE_KEYWORDS includes screening/background check terms
    # - prefilter.py: IRRELEVANCE_KEYWORDS includes sports/recipes/entertainment
    # - tests/: at least one test with mixed articles verifying count reduction

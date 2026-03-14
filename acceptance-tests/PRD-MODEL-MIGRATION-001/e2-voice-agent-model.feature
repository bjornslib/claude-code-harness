Feature: E2 - Migrate Voice Agent to openai/gpt-oss-20b
  As the guardian, I validate that the voice agent config and tests
  use the correct Groq model ID.

  # Weight: 0.25

  # Scoring Guide:
  # 1.0 = Config + all test references updated, provider unchanged
  # 0.7 = Config updated but some test references missed
  # 0.4 = Config updated but tests still reference old model
  # 0.0 = Config not changed or wrong model ID used

  Scenario: AC1 - voice_agent config.py uses gpt-oss-20b
    Given the file "agencheck-communication-agent/livekit_prototype/cli_poc/voice_agent/config.py"
    Then line ~28 should contain 'openai/gpt-oss-20b' as the default for llm_model
    And it should NOT contain "meta-llama/llama-4-maverick-17b-128e-instruct" anywhere
    And the llm_provider should still be "groq" (unchanged)

  Scenario: AC2 - conftest.py test fixtures updated
    Given the file "agencheck-communication-agent/livekit_prototype/cli_poc/voice_agent/tests/conftest.py"
    Then it should NOT contain "meta-llama/llama-4-maverick-17b-128e-instruct" anywhere
    And any model references should use "openai/gpt-oss-20b"

  Scenario: AC3 - Provider configuration unchanged
    Given the file "agencheck-communication-agent/livekit_prototype/cli_poc/voice_agent/config.py"
    Then the GROQ_API_KEY reference should be preserved
    And the provider should still default to "groq"
    And no new provider configuration should be added

  Scenario: AC4 - No other files reference old model
    Given a search across "agencheck-communication-agent/livekit_prototype/cli_poc/voice_agent/"
    Then no file should contain "llama-4-maverick" or "llama-4-maverick-17b-128e-instruct"

Feature: E3 - Migrate Form Filler to openai/gpt-oss-20b
  As the guardian, I validate that the live_form_filler agent
  uses the correct model (fixing the 120b typo).

  # Weight: 0.25

  # Scoring Guide:
  # 1.0 = Model changed, comment accurate, provider unchanged
  # 0.7 = Model changed but comment still stale
  # 0.4 = Model changed but provider config also modified (unintended)
  # 0.0 = Model not changed or wrong model ID

  Scenario: AC1 - agent.py uses gpt-oss-20b (not 120b)
    Given the file "agencheck-support-agent/live_form_filler/agent.py"
    Then line ~20 should contain 'openai/gpt-oss-20b' in the PatchedGroqModel call
    And it should NOT contain 'openai/gpt-oss-120b' anywhere

  Scenario: AC2 - Comment on line ~26 is accurate
    Given the file "agencheck-support-agent/live_form_filler/agent.py"
    Then the comment near the Agent() initialization should say "gpt-oss-20b"
    And it should NOT say "gpt-oss-120b"

  Scenario: AC3 - Groq provider configuration unchanged
    Given the file "agencheck-support-agent/live_form_filler/agent.py"
    Then the OpenAIProvider should still use base_url='https://api.groq.com/openai/v1'
    And it should still use os.getenv('GROQ_API_KEY')
    And no new imports or provider changes should be added

  Scenario: AC4 - Both agents now use same model
    Given the voice_agent config at "voice_agent/config.py"
    And the form_filler agent at "live_form_filler/agent.py"
    Then both should reference "openai/gpt-oss-20b" (consistency check)

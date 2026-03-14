Feature: E1 - Add NEXTJS_BASE_URL, Rewrite Email Templates, Fix Variable Naming
  As the guardian, I validate that the email dispatch system is correctly updated
  with new environment configuration, rewritten templates, and atomic variable rename.

  # Weight: 0.50 (highest risk — atomic rename across 8 files)

  # Scoring Guide:
  # 1.0 = All criteria met, atomic rename complete, no KeyError risk
  # 0.7 = Most criteria met, minor gaps (e.g., docstring not updated)
  # 0.4 = Partial implementation, some files missed in rename
  # 0.0 = Not implemented or rename inconsistent (KeyError at runtime)

  Scenario: AC1 - NEXTJS_BASE_URL environment variable added
    Given the file "agencheck-support-agent/.env"
    Then it should contain "NEXTJS_BASE_URL=http://localhost:5002"

  Scenario: AC2 - channel_dispatch.py builds verification URLs
    Given the file "agencheck-support-agent/prefect_flows/flows/tasks/channel_dispatch.py"
    Then it should import "os" at module level
    And it should define "_NEXTJS_BASE_URL" from os.environ with default "http://localhost:5002"
    And the function "_dispatch_email_verification" should build "check_verification_url" using _NEXTJS_BASE_URL and task_id
    And the function "_dispatch_email_verification" should build "schedule_callback_url"
    And the variables dict should include "check_verification_url" and "schedule_callback_url"

  Scenario: AC3 - Email templates rewritten with three CTAs
    Given the email templates in "prefect_flows/templates/work_history/"
    Then "email_first_contact.txt" should contain "{check_verification_url}"
    And "email_first_contact.txt" should contain "{callback_number}"
    And "email_first_contact.txt" should contain "{schedule_callback_url}"
    And "email_reminder_1.txt" should contain all three CTAs
    And "email_reminder_2.txt" should contain all three CTAs
    And "email_reminder_2.txt" should contain "{days_elapsed}"

  Scenario: AC4 - Variable rename applied atomically across ALL files
    # CRITICAL: Both old names exist mapping to different values
    # contact_name (employer HR) -> verifier_name
    # verifier_name (AgenCheck Team) -> agent_name
    Given the following files are checked for variable consistency:
      | File | Old Key | New Key | Value Meaning |
      | channel_dispatch.py | contact_name | verifier_name | HR person default "HR Department" |
      | channel_dispatch.py | verifier_name | agent_name | Agent default "AgenCheck Team" |
      | verification_orchestrator.py line ~248 | contact_name | verifier_name | contact_name variable |
      | verification_orchestrator.py line ~252 | verifier_name | agent_name | "AgenCheck Team" literal |
      | stream_consumer.py line ~126 | verifier_name | agent_name | fields.get("verifier_name") |
      | template_service.py docstring | contact_name | verifier_name | example dict |
      | template_service.py docstring | verifier_name | agent_name | example dict |
    Then NO file should contain "contact_name" as a template variable key
    And NO template should use "{contact_name}" placeholder
    And all templates should use "{verifier_name}" for the employer HR person
    And all templates should use "{agent_name}" for the AgenCheck agent

  Scenario: AC5 - voice_voicemail.txt updated with renamed variables
    Given the file "prefect_flows/templates/work_history/voice_voicemail.txt"
    Then it should use "{verifier_name}" (not "{contact_name}")
    And it should use "{agent_name}" (not "{verifier_name}" for agent)
    And it should NOT contain "{check_verification_url}" (audio only, no form URL)

  Scenario: AC6 - days_elapsed bug fixed
    Given the file "agencheck-support-agent/prefect_flows/flows/tasks/channel_dispatch.py"
    Then the variables dict should include "days_elapsed" with context.get fallback
    And "email_reminder_2.txt" should render without KeyError when days_elapsed is provided

  Scenario: AC7 - template_service.py docstring updated
    Given the file "agencheck-support-agent/services/template_service.py"
    Then the docstring example should show "verifier_name" (not "contact_name")
    And the docstring example should show "agent_name" (not "verifier_name" for agent)

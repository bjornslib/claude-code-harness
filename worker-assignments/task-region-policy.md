## WORKER ASSIGNMENT: Task 2 - Region-Based Voicemail Policy

**Beads ID**: agencheck-mz11
**Agent Type**: backend-solutions-engineer

<GOALS>
1. Implement region detection from phone number prefix in verification_agents.py
2. Add VoicemailPolicy enum (NEVER, APAC_ONLY, WITH_CONSENT)
3. Modify detected_voicemail to apply policy based on region
4. US (+1) = always hang up, APAC (+61 AU, +65 SG) = can leave message (if policy allows)
</GOALS>

<ACCEPTANCE_CRITERIA>
- Given: Call to US number (+1), When: Voicemail detected, Then: Always hang up, never leave message
- Given: Call to AU number (+61), When: Voicemail detected + policy=APAC_ONLY, Then: Can leave callback message
- Given: Call to SG number (+65), When: Voicemail detected + policy=APAC_ONLY, Then: Can leave callback message
- Given: Call to EU/other number, When: Voicemail detected, Then: Hang up by default (safe approach)
- Region detected correctly from phone number prefix
</ACCEPTANCE_CRITERIA>

<ADDITIONAL_CONTEXT>
**Solution Design**: documentation/scratch-pads/voicemail-detection-solution-design.md
- See "Region-Specific Policy" section (lines 236-275)
- See "Policy Matrix" table for region → action mapping

**Key Files**:
- agencheck-communication-agent/livekit_prototype/cli_poc/voice_agent/verification_agents.py (modify detected_voicemail)

**Pattern from Solution Design**:
```python
class VoicemailPolicy(str, Enum):
    NEVER = "never"           # Always hang up, never leave message
    APAC_ONLY = "apac_only"   # Leave message for non-US numbers
    WITH_CONSENT = "with_consent"  # Only if explicit consent exists

def get_region_from_phone(phone_number: str) -> str:
    # US: +1, AU: +61, SG: +65, UK: +44
    # Returns: "US", "AU", "SG", "EU", "APAC", "OTHER"

DEFAULT_VOICEMAIL_POLICY = VoicemailPolicy.NEVER
```

**Task 1 Complete**: detected_voicemail tool exists in NavigationAgent, currently always hangs up
</ADDITIONAL_CONTEXT>

<SUCCESS_CRITERIA>
- Add VoicemailPolicy enum and get_region_from_phone function
- Modify detected_voicemail to check policy and region before deciding action
- Default policy = NEVER (safe)
- Log region detection decisions
- Commit changes with message: "feat(agencheck-mz11): add region-based voicemail policy"
</SUCCESS_CRITERIA>

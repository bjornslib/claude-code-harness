## WORKER ASSIGNMENT: Task 3 - APAC Voicemail Message TTS

**Beads ID**: agencheck-swyo
**Agent Type**: backend-solutions-engineer

<GOALS>
1. Implement TTS voicemail message in detected_voicemail when APAC region permits
2. Use `self.session.say()` for direct TTS output (not LLM-generated)
3. Wait for the message to complete before hanging up
4. Add callback number configuration
</GOALS>

<ACCEPTANCE_CRITERIA>
- Given: Voicemail detected + APAC region + APAC_ONLY policy, When: detected_voicemail executes, Then: TTS message plays before hangup
- Given: Voicemail detected + US region, When: detected_voicemail executes, Then: No message played, immediate hangup
- Message matches template: "Hi, this is Aura from AgenCheck calling regarding an employment verification request. Please call us back at [callback_number]. Thank you."
- Message is brief (~10 seconds), professional tone
- Call hangs up AFTER message finishes playing
</ACCEPTANCE_CRITERIA>

<ADDITIONAL_CONTEXT>
**Solution Design**: documentation/scratch-pads/voicemail-detection-solution-design.md (lines 280-299)

**Key Files**:
- agencheck-communication-agent/livekit_prototype/cli_poc/voice_agent/verification_agents.py (modify detected_voicemail)
- agencheck-communication-agent/livekit_prototype/cli_poc/voice_agent/config.py (add callback_number config)

**TTS Pattern from codebase**:
```python
# Direct TTS without LLM - use session.say()
await self.session.say(
    "Hi, this is Aura from AgenCheck calling regarding an employment verification request. Please call us back. Thank you.",
    allow_interruptions=False  # Don't allow caller to interrupt voicemail
)
# Wait for audio to finish playing
await asyncio.sleep(0.5)  # Small buffer after TTS completion
```

**Task 2 Complete**: VoicemailPolicy, get_region_from_phone(), can_leave_voicemail() already implemented. Look for TODO comment in detected_voicemail about TTS implementation.

**Configuration**:
Add to config.py:
```python
voicemail_callback_number: str = field(default_factory=lambda: os.getenv("VOICEMAIL_CALLBACK_NUMBER", "+61123456789"))
```
</ADDITIONAL_CONTEXT>

<SUCCESS_CRITERIA>
- Implement TTS voicemail message in detected_voicemail
- Add callback number configuration
- Ensure message plays completely before hangup
- Log voicemail message sent
- Commit changes with message: "feat(agencheck-swyo): add APAC voicemail TTS message"
</SUCCESS_CRITERIA>

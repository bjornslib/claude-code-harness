## WORKER ASSIGNMENT: Task 1 - Core Voicemail Detection Tool

**Beads ID**: agencheck-ep1b
**Agent Type**: backend-solutions-engineer

<OVERARCHING_GUIDELINES>
- Follow CLAUDE.md strictly at every step
- Use Serena MCP for code navigation (find_symbol, search_for_pattern)
- Consult context7 for LiveKit patterns if needed
- Commit after completion
</OVERARCHING_GUIDELINES>

<GOALS>
1. Add `detected_voicemail` tool to NavigationAgent in verification_agents.py
2. Add `<voicemail_detection>` prompt section to verification_prompts.py
3. Add `voicemail` as a new UnableToVerifyReason in interpret_call_outcome.py
</GOALS>

<ACCEPTANCE_CRITERIA>
- Given: Voice agent reaches voicemail, When: LLM recognizes voicemail pattern, Then: detected_voicemail tool is called
- Given: detected_voicemail called, When: Tool executes, Then: Call is hung up and outcome recorded
- Given: Voicemail detected, When: interpret_call_outcome runs, Then: Returns unable_to_verify with reason="voicemail"
- The prompt section includes clear indicators of voicemail vs IVR/hold/human
</ACCEPTANCE_CRITERIA>

<ADDITIONAL_CONTEXT>
**Solution Design**: documentation/scratch-pads/voicemail-detection-solution-design.md (MUST READ FIRST)
**Detailed PRD**: .taskmaster/docs/epic-1.2-voicemail-detection-prd.md

**Key Files**:
- agencheck-communication-agent/livekit_prototype/cli_poc/voice_agent/verification_agents.py
- agencheck-communication-agent/livekit_prototype/cli_poc/voice_agent/verification_prompts.py
- agencheck-communication-agent/livekit_prototype/cli_poc/voice_agent/interpret_call_outcome.py

**Pattern Reference**: The hangup_call() function already exists in verification_agents.py - use similar pattern for detected_voicemail
**Existing**: voicemail_max_retries is already defined in outcome schema - voicemail is a NEW distinct reason

**Tool Signature** (from solution design):
```python
async def detected_voicemail(
    self,
    greeting_type: Literal["personal", "business", "generic"],
) -> None:
```
</ADDITIONAL_CONTEXT>

<SUCCESS_CRITERIA>
- Read solution design first
- Implement detected_voicemail tool
- Add voicemail_detection prompt section
- Add voicemail outcome reason
- Run tests if available
- Commit changes with message: "feat(agencheck-ep1b): add detected_voicemail tool for voicemail detection"
- Report completion status
</SUCCESS_CRITERIA>

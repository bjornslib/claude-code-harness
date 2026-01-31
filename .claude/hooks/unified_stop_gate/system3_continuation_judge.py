"""System 3 continuation judge checker using Haiku API for session evaluation.

This checker uses Claude Haiku 4.5 to analyze the last 5 conversation turns
and determine if a System 3 meta-orchestrator session should be allowed to stop.

The judge evaluates:
- Completion promise verification (cs-verify)
- Post-session reflection (Hindsight retention)
- Validation evidence (validation-agent usage)
- Cleanup (tmux sessions, message bus)
- Meaningful work completion
- Continuation items or genuine completeness
"""

from dataclasses import dataclass
import json
import os
import sys
from typing import Optional, List, Dict, Any

from .config import CheckResult, EnvironmentConfig, Priority
from .checkers import SessionInfo


def _extract_json_object(text: str) -> str:
    """Extract the outermost JSON object from text that may contain extra content.

    Handles cases where Haiku returns JSON followed by explanatory text:
        {"should_continue": true, ...}

        Note: The session has properly...

    Returns just the JSON substring between the first '{' and its matching '}'.
    Raises ValueError if no valid JSON object structure is found.
    """
    start = text.find('{')
    if start == -1:
        raise ValueError("No '{' found in response text")

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\' and in_string:
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    raise ValueError(f"Unbalanced braces in response (depth={depth} at end)")


# System prompt for the Haiku judge
SYSTEM3_JUDGE_SYSTEM_PROMPT = """You are a session completion evaluator for a System 3 meta-orchestrator.

Your job: Analyze the last few turns of a System 3 session, the current work state, and ALL task primitives to determine if the session should be allowed to stop.

## Core Principle
The ONLY valid exit for a System 3 session is to have sincerely exhausted all options to continue productive work independently and to have presented option questions to the user via AskUserQuestion.

## What You Receive
1. WORK STATE: Promises, beads, and ALL task primitives (unfinished AND completed)
2. CONVERSATION: The last few turns of the session transcript

Step 4 has already enforced that no pending/in_progress tasks remain. You are evaluating whether the SESSION ITSELF is properly complete.

## Three-Layer Assessment

### Layer 1: Protocol Compliance
Before stopping, System 3 MUST have completed:
1. **Completion Promises**: All session promises verified with proof (cs-verify), or no promises created
2. **Post-Session Reflection**: Learnings stored to Hindsight (mcp__hindsight__retain)
3. **Validation Evidence**: Business outcomes validated via validation-agent (not direct bd close)
4. **Cleanup**: Orchestrator tmux sessions killed, message bus unregistered

### Layer 2: Work Availability
Check the WORK STATE for remaining actionable work:
- Unmet promises → System 3 MUST continue
- Ready beads (especially P0-P2) → System 3 SHOULD continue
- Open business epics → System 3 SHOULD continue
- If work is available, System 3 should continue unless it genuinely needs user input to decide direction

### Layer 3: Session Exit Validation
The conversation MUST show that System 3 presented option questions to the user:
- Did System 3 use AskUserQuestion to present 2-4 concrete next-step options?
- Is System 3 waiting for the user's response?
- If no option questions were presented, the session is NOT properly complete

## Evaluating Completed Tasks
If completed tasks exist, assess whether they represent MEANINGFUL work:
- Did the completed work advance session goals?
- Were tasks substantive (not just "investigate" or "check status")?
- Is the completed work sufficient given the available beads/promises?

## Evaluating Unfinished Tasks (Safety Net)
If somehow unfinished tasks slipped through Step 4, ALWAYS BLOCK:
- Pending/in_progress tasks mean the session has uncommitted work
- Remind System 3 to consider all viable options to continue productive work independently

## Response Format
RESPOND with JSON only:
{"should_continue": boolean, "reason": "brief explanation", "suggestion": "what to do next if continuing"}

should_continue=true means BLOCK the stop (session has more to do)
should_continue=false means ALLOW the stop (session properly completed)

Default to ALLOW (should_continue=false) when:
- The conversation shows the user explicitly asked to stop
- All protocol steps are clearly completed AND work state confirms exhaustion
- System 3 has presented option questions to the user and is awaiting response

Default to BLOCK (should_continue=true) when:
- Active orchestrators are mentioned but not cleaned up
- Completion promises exist but weren't verified
- No post-session reflection was performed
- Work was started but not validated
- Work state shows available high-priority work but System 3 is stopping
- Unfinished tasks exist (remind to continue productive work independently)
- No AskUserQuestion was presented despite work being exhausted"""


class System3ContinuationJudgeChecker:
    """P3.5: System 3 session continuation evaluator using Haiku API.

    This checker uses a Haiku 4.5 API call to analyze the last 5 conversation
    turns and determine if a System 3 session has properly completed its work
    before stopping.

    Only active for System 3 sessions (session ID starts with 'system3-').
    Fails open on any errors to avoid blocking valid stops.
    """

    def __init__(self, config: EnvironmentConfig, session: SessionInfo):
        """Initialize the checker.

        Args:
            config: Environment configuration (provides is_system3 check).
            session: Session info with transcript path.
        """
        self.config = config
        self.session = session

    def check(self) -> CheckResult:
        """Check if System 3 session should be allowed to stop.

        Returns:
            CheckResult with:
            - passed=True if not System3, no transcript, judge approves, or error (fail-open)
            - passed=False if judge blocks stop (session has more work to do)
        """
        # Guard: Only run for System 3 sessions
        if not self.config.is_system3:
            return CheckResult(
                priority=Priority.P3_5_SYSTEM3_JUDGE,
                passed=True,
                message="Not a System 3 session - judge check skipped",
                blocking=True,
            )

        # Guard: Check if transcript exists, with fallback to session_id search
        transcript_path = self.session.transcript_path
        if not transcript_path or not os.path.exists(transcript_path):
            # Fallback: try to find transcript using session_id
            try:
                import glob
                session_id = self.session.session_id
                if session_id:
                    # Search for matching transcript in ~/.claude/projects/*/{session_id}.jsonl
                    search_pattern = os.path.expanduser(f"~/.claude/projects/*/{session_id}.jsonl")
                    matches = glob.glob(search_pattern)
                    if matches:
                        transcript_path = matches[0]  # Use first match
                        print(f"[System3Judge] Found transcript via session_id: {transcript_path}", file=sys.stderr)
            except Exception as e:
                print(f"[System3Judge] Fallback transcript search failed: {e}", file=sys.stderr)

        # Final check: if still no transcript, skip judge
        if not transcript_path or not os.path.exists(transcript_path):
            return CheckResult(
                priority=Priority.P3_5_SYSTEM3_JUDGE,
                passed=True,
                message="No transcript available, skipping judge",
                blocking=True,
            )

        # Update session with found transcript path
        self.session.transcript_path = transcript_path

        # Guard: Check for API key
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            return CheckResult(
                priority=Priority.P3_5_SYSTEM3_JUDGE,
                passed=True,
                message="No API key, skipping judge",
                blocking=True,
            )

        # Main evaluation wrapped in try/except for fail-open behavior
        try:
            # Extract last 5 conversation turns
            turns = self._extract_last_turns(self.session.transcript_path, num_turns=5)

            if not turns:
                return CheckResult(
                    priority=Priority.P3_5_SYSTEM3_JUDGE,
                    passed=True,
                    message="No conversation turns found in transcript",
                    blocking=True,
                )

            # Build evaluation prompt
            user_prompt = self._build_evaluation_prompt(turns)

            # Call Haiku API
            judgment = self._call_haiku_judge(api_key, user_prompt)

            # Parse response
            should_continue = judgment.get('should_continue', False)
            reason = judgment.get('reason', 'No reason provided')
            suggestion = judgment.get('suggestion', '')

            # Return result based on judgment
            if should_continue:
                # BLOCK - session should continue
                message = f"System 3 Judge: {reason}"
                if suggestion:
                    message += f"\n\nSuggestion: {suggestion}"
                return CheckResult(
                    priority=Priority.P3_5_SYSTEM3_JUDGE,
                    passed=False,
                    message=message,
                    blocking=True,
                )
            else:
                # ALLOW - session can stop
                return CheckResult(
                    priority=Priority.P3_5_SYSTEM3_JUDGE,
                    passed=True,
                    message=f"System 3 Judge approves stop: {reason}",
                    blocking=True,
                )

        except Exception as e:
            # Fail-open on any error
            error_msg = str(e)[:200]  # Truncate long errors
            print(f"[System3Judge] Error during evaluation: {error_msg}", file=sys.stderr)
            return CheckResult(
                priority=Priority.P3_5_SYSTEM3_JUDGE,
                passed=True,
                message=f"Judge error (fail-open): {error_msg}",
                blocking=True,
            )

    def _extract_last_turns(self, transcript_path: str, num_turns: int = 5) -> List[Dict[str, Any]]:
        """Extract the last N user/assistant turns from a JSONL transcript.

        Args:
            transcript_path: Path to the JSONL transcript file.
            num_turns: Number of turns to extract (default: 5).

        Returns:
            List of turn dictionaries with 'role' and 'content_summary' keys.

        Raises:
            Exception: On file read errors or JSON parsing errors.
        """
        turns = []

        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # Skip malformed lines

                    entry_type = entry.get('type')
                    if entry_type not in ('user', 'assistant'):
                        continue

                    # Extract content based on role
                    role = entry_type
                    content_summary = self._extract_content_summary(entry, role)

                    if content_summary:
                        turns.append({
                            'role': role,
                            'content_summary': content_summary
                        })

            # Return last N turns
            return turns[-num_turns:] if len(turns) > num_turns else turns

        except Exception as e:
            print(f"[System3Judge] Error reading transcript: {e}", file=sys.stderr)
            raise

    def _extract_content_summary(self, entry: Dict[str, Any], role: str) -> str:
        """Extract and summarize content from a transcript entry.

        Args:
            entry: The transcript entry dictionary.
            role: The role ('user' or 'assistant').

        Returns:
            Summarized content string (max ~600 chars).
        """
        message = entry.get('message', {})
        content = message.get('content', '')

        parts = []

        if role == 'user':
            # User content can be string or list
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        parts.append(block.get('text', ''))
                    elif isinstance(block, str):
                        parts.append(block)

        elif role == 'assistant':
            # Assistant content is typically a list of content blocks
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get('type')
                        if block_type == 'text':
                            parts.append(block.get('text', ''))
                        elif block_type == 'tool_use':
                            tool_name = block.get('name', 'unknown')
                            # Summarize tool input
                            tool_input = block.get('input', {})
                            input_summary = self._summarize_tool_input(tool_input)
                            parts.append(f"[Tool: {tool_name}({input_summary})]")
            elif isinstance(content, str):
                parts.append(content)

        # Join and truncate to ~600 chars
        full_content = ' '.join(parts)
        max_len = 600
        if len(full_content) > max_len:
            return full_content[:max_len] + '...'
        return full_content

    def _summarize_tool_input(self, tool_input: Dict[str, Any]) -> str:
        """Summarize tool input for display.

        Args:
            tool_input: Dictionary of tool input parameters.

        Returns:
            Brief summary string (max ~50 chars).
        """
        if not tool_input:
            return ''

        # Try to find key parameters
        key_params = []
        for key in ['file_path', 'pattern', 'command', 'skill', 'prompt', 'message']:
            if key in tool_input:
                value = str(tool_input[key])
                if len(value) > 40:
                    value = value[:40] + '...'
                key_params.append(f"{key}={value}")
                if len(key_params) >= 2:
                    break

        if key_params:
            return ', '.join(key_params)

        # Fallback: show first key
        first_key = next(iter(tool_input.keys()), None)
        if first_key:
            value = str(tool_input[first_key])
            if len(value) > 40:
                value = value[:40] + '...'
            return f"{first_key}={value}"

        return 'no params'

    def _build_evaluation_prompt(self, turns: List[Dict[str, Any]]) -> str:
        """Build the evaluation prompt from conversation turns and work state.

        Structure: Work state FIRST (decision-relevant data), then conversation.
        The judge should see the full picture before reading the transcript.

        Args:
            turns: List of turn dictionaries with 'role' and 'content_summary'.

        Returns:
            Formatted prompt string for the Haiku judge.
        """
        parts = []
        for turn in turns:
            role = turn.get('role', 'unknown').upper()
            content = turn.get('content_summary', '')
            parts.append(f"[{role}]: {content}")

        conversation = "\n\n".join(parts)

        # Work state from Step 4 (includes ALL task states)
        work_state = os.environ.get('WORK_STATE_SUMMARY', '').strip()

        # Build prompt with work state FIRST for prominence
        prompt_parts = ["Evaluate this System 3 session for completion readiness.\n"]

        if work_state:
            prompt_parts.append(f"## WORK STATE AND TASK PRIMITIVES\n\n{work_state}\n")

        prompt_parts.append(
            "## KEY QUESTION\n"
            "Has System 3 sincerely exhausted all options to continue productive work "
            "independently, AND presented option questions to the user via AskUserQuestion?\n"
        )

        prompt_parts.append(f"## CONVERSATION (last turns)\n\n{conversation}")

        return "\n".join(prompt_parts)

    def _call_haiku_judge(self, api_key: str, user_prompt: str) -> Dict[str, Any]:
        """Call Haiku API to evaluate session continuation.

        Args:
            api_key: Anthropic API key.
            user_prompt: The evaluation prompt with conversation context.

        Returns:
            Dictionary with 'should_continue', 'reason', and 'suggestion' keys.

        Raises:
            Exception: On API errors, timeout, or response parsing errors.
        """
        try:
            # Import Anthropic SDK (lazy import to avoid dependency issues)
            from anthropic import Anthropic
        except ImportError as e:
            raise Exception(f"Anthropic SDK not available: {e}")

        try:
            client = Anthropic(api_key=api_key)

            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                system=SYSTEM3_JUDGE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                timeout=30.0,  # 30 second timeout
            )

            # Extract text content
            text_content = ''
            for block in response.content:
                if hasattr(block, 'text'):
                    text_content += block.text

            if not text_content:
                raise Exception("No text content in Haiku response")

            # Strip markdown code fences if present
            clean_text = text_content.strip()
            if clean_text.startswith('```'):
                # Remove opening fence (```json or ```)
                first_newline = clean_text.index('\n')
                clean_text = clean_text[first_newline + 1:]
            if clean_text.endswith('```'):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

            # Extract just the JSON object (handles trailing text from Haiku)
            try:
                json_str = _extract_json_object(clean_text)
            except ValueError as e:
                raise Exception(f"Could not extract JSON from Haiku response: {e}")

            # Parse JSON response
            judgment = json.loads(json_str)

            # Validate required fields
            if 'should_continue' not in judgment:
                raise Exception("Missing 'should_continue' in judgment response")

            # Ensure all expected fields exist (with defaults)
            result = {
                'should_continue': bool(judgment.get('should_continue', False)),
                'reason': judgment.get('reason', 'No reason provided'),
                'suggestion': judgment.get('suggestion', ''),
            }

            return result

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Haiku JSON response: {e}")
        except Exception as e:
            # Re-raise with context
            raise Exception(f"Haiku API call failed: {e}")

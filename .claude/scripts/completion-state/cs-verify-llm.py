#!/usr/bin/env python3
"""Programmatic validation gate using Claude Agent SDK.

Gate 3 in triple-gate validation:
  Gate 1: Session self-reports completion (cs-promise)
  Gate 2: s3-validator teammate independently verifies (validation protocol)
  Gate 3: This script - Claude Agent SDK agent with file/code access

Usage:
    cs-verify-llm.py --summary "Promise summary" \
                      --criteria '[{"id":"AC-1","description":"...","status":"met","evidence":"..."}]' \
                      --proof "Optional summary"

Output (stdout): JSON verdict with reasoning, confidence, and cost
Logs (stderr): Agent SDK execution details and cost
"""
import argparse
import json
import sys
import os


def load_validator_evidence(promise_id):
    """Load validation responses from Gate 2 validators.

    Reads validation response files from
    .claude/completion-state/validations/{promise-id}/ directory.

    Returns:
        dict: Mapping of AC-ID -> validator evidence string
    """
    if not promise_id:
        return {}

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    validations_dir = os.path.join(
        project_dir, ".claude", "completion-state", "validations", promise_id
    )

    if not os.path.isdir(validations_dir):
        return {}

    evidence = {}
    for filename in os.listdir(validations_dir):
        if not filename.endswith("-validation.json"):
            continue

        filepath = os.path.join(validations_dir, filename)
        try:
            with open(filepath) as f:
                response = json.load(f)

            ac_id = response.get("_metadata", {}).get("ac_id", "")
            if not ac_id:
                # Derive from filename: {ac-id}-validation.json
                ac_id = filename.replace("-validation.json", "")

            verdict = response.get("verdict", "UNKNOWN")
            reasoning = response.get("reasoning", "")
            confidence = response.get("confidence", "N/A")

            # Build per-criterion evidence summary
            criteria_details = []
            for cr in response.get("criteria_results", []):
                cr_id = cr.get("criterion_id", "?")
                cr_status = cr.get("status", "?")
                cr_evidence = cr.get("evidence", cr.get("reason", "No details"))
                criteria_details.append(f"  [{cr_status}] {cr_id}: {cr_evidence}")

            evidence_text = (
                f"Verdict: {verdict} (confidence: {confidence})\n"
                f"Reasoning: {reasoning}"
            )
            if criteria_details:
                evidence_text += "\nCriteria:\n" + "\n".join(criteria_details)

            evidence[ac_id] = evidence_text

        except (json.JSONDecodeError, OSError):
            continue

    return evidence


def build_evaluation_prompt(summary, criteria, proof, validator_evidence=None):
    """Build the user message for the Agent SDK evaluator."""
    validator_evidence = validator_evidence or {}

    criteria_parts = []
    for c in criteria:
        ac_id = c.get('id', 'N/A')
        part = (
            f"- {ac_id}: {c.get('description', 'N/A')}\n"
            f"  Status: {c.get('status', 'unknown')}\n"
            f"  Evidence: {c.get('evidence', 'None provided')}"
        )

        # Include Gate 2 validator assessment if available
        val_ev = validator_evidence.get(ac_id)
        if val_ev:
            part += f"\n  Validator Assessment (Gate 2):\n    {val_ev.replace(chr(10), chr(10) + '    ')}"

        criteria_parts.append(part)

    criteria_text = "\n".join(criteria_parts)

    return f"""## Completion Verification Request

### Promise Summary
{summary}

### Acceptance Criteria and Evidence
{criteria_text}

### Additional Proof
{proof if proof else "None provided"}

## Your Task
1. Use your tools to INDEPENDENTLY verify each claim in the evidence
2. After investigation, output your verdict as a JSON code block (```json)

CRITICAL: You MUST end with a JSON code block containing your verdict."""


SYSTEM_PROMPT = """You are a verification judge for an AI agent orchestration system.

Your job is to independently verify whether completion evidence genuinely satisfies acceptance criteria.
You have access to the project codebase and can read files, search code, and run commands.

VERIFICATION PROCESS:
1. Read the acceptance criteria and claimed evidence
2. Use your tools to INDEPENDENTLY verify each claim:
   - If evidence says "tests pass" → run the tests or check test files exist
   - If evidence says "file X was created" → read file X and check it matches the description
   - If evidence says "function Y was implemented" → grep for the function and read its implementation
   - If evidence references specific code patterns → verify they exist in the codebase
3. Assess whether the evidence genuinely satisfies each criterion
4. AFTER your investigation, output your verdict as a JSON code block

CRITICAL: You MUST end your response with a JSON code block in this exact format:
```json
{
    "verdict": "PASS" or "FAIL",
    "reasoning": "Brief explanation of your verification findings",
    "confidence": 0.0-1.0,
    "criteria_checked": [
        {"id": "AC-1", "verified": true/false, "finding": "What you found"}
    ]
}
```

Be strict but fair. Look for concrete, verifiable evidence in the codebase.
If you cannot verify a claim (e.g., file doesn't exist), mark it as unverified.
FAIL if any critical criterion cannot be verified."""


def warn_result(reason):
    """Return a WARN verdict for graceful degradation."""
    print(json.dumps({
        "verdict": "WARN",
        "reasoning": reason,
        "fallback": True
    }))


def main():
    parser = argparse.ArgumentParser(
        description="Programmatic validation gate using Claude Agent SDK"
    )
    parser.add_argument("--summary", required=True, help="Promise summary text")
    parser.add_argument("--criteria", required=True, help="JSON array of acceptance criteria")
    parser.add_argument("--proof", default="", help="Optional proof summary")
    parser.add_argument("--promise-id", default="", help="Promise ID for loading Gate 2 validator evidence")
    args = parser.parse_args()

    # Parse criteria JSON
    try:
        criteria = json.loads(args.criteria)
    except json.JSONDecodeError as e:
        warn_result(f"Invalid criteria JSON: {e}")
        return

    # Check for claude_agent_sdk package
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage
        import anyio
    except ImportError as e:
        warn_result(f"claude_agent_sdk package not available: {e}")
        return

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        warn_result("ANTHROPIC_API_KEY environment variable not set")
        return

    # Get project directory
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    # Load Gate 2 validator evidence if promise-id provided
    promise_id = getattr(args, 'promise_id', '') or ''
    validator_evidence = load_validator_evidence(promise_id)

    # Build prompt
    user_message = build_evaluation_prompt(args.summary, criteria, args.proof, validator_evidence)

    # Unset CLAUDECODE to allow Agent SDK to spawn subprocess
    # (Agent SDK verification runs in isolated context, not nested session)
    claudecode_backup = os.environ.pop("CLAUDECODE", None)

    # Run Agent SDK verification
    async def run_verification():
        options = ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            allowed_tools=["Read", "Grep", "Glob", "Bash"],
            disallowed_tools=["Write", "Edit", "MultiEdit", "NotebookEdit"],
            permission_mode="acceptEdits",
            model="claude-sonnet-4-5-20250929",
            max_turns=25,  # Increased - agent needs turns for investigation + JSON output
            max_budget_usd=0.75,  # Increased budget for thorough verification
            cwd=project_dir,
        )

        final_text = ""
        total_cost = 0.0
        num_turns = 0

        try:
            async for message in query(prompt=user_message, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            # Always keep the latest text block
                            # (the final one should be the JSON response)
                            final_text = block.text
                elif isinstance(message, ResultMessage):
                    total_cost = message.total_cost_usd or 0.0
                    num_turns = message.num_turns or 0
                    # Don't break - let the async generator complete naturally

        except GeneratorExit:
            # Expected when generator closes
            pass
        except Exception as e:
            print(f"Agent SDK error: {type(e).__name__}: {e}", file=sys.stderr)
            return None, 0.0, 0

        return final_text, total_cost, num_turns

    try:
        # Suppress async cleanup exceptions from Agent SDK (known issue)
        import warnings
        warnings.filterwarnings("ignore", category=RuntimeWarning)

        response_text, cost, turns = anyio.run(run_verification)

        # Restore CLAUDECODE environment variable if it was set
        if claudecode_backup is not None:
            os.environ["CLAUDECODE"] = claudecode_backup

        if response_text is None or not response_text.strip():
            warn_result("Agent SDK execution failed - empty response")
            return

        # Extract JSON from markdown code block if present
        if "```json" in response_text:
            # Find the JSON code block
            start_marker = "```json"
            end_marker = "```"
            start = response_text.find(start_marker)
            if start != -1:
                start += len(start_marker)
                end = response_text.find(end_marker, start)
                if end != -1:
                    response_text = response_text[start:end].strip()
        elif response_text.startswith("```"):
            # Handle generic code block at start
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        # Parse agent response as JSON
        result = json.loads(response_text)

        # Ensure required fields
        if "verdict" not in result:
            result["verdict"] = "WARN"
            result["reasoning"] = result.get("reasoning", "Agent response missing verdict field")

        # Add cost and turn tracking
        result["cost_estimate_usd"] = round(cost, 6)
        result["num_turns"] = turns

        # Log cost to stderr
        print(
            f"Agent SDK Gate: {turns} turns, ${cost:.4f}",
            file=sys.stderr
        )

        # Output result to stdout
        print(json.dumps(result))

    except json.JSONDecodeError as e:
        warn_result(f"Failed to parse agent response as JSON: {e}")
    except (KeyError, IndexError) as e:
        warn_result(f"Unexpected response structure: {e}")
    except Exception as e:
        warn_result(f"Unexpected error: {type(e).__name__}: {e}")
    finally:
        # Always restore CLAUDECODE environment variable
        if claudecode_backup is not None:
            os.environ["CLAUDECODE"] = claudecode_backup


if __name__ == "__main__":
    main()

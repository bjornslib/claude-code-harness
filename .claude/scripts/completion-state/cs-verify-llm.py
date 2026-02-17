#!/usr/bin/env python3
"""Programmatic validation gate using Anthropic Claude Sonnet 4.5.

Gate 3 in triple-gate validation:
  Gate 1: Session self-reports completion (cs-promise)
  Gate 2: s3-validator teammate independently verifies (validation protocol)
  Gate 3: This script - Sonnet 4.5 as programmatic judge

Usage:
    cs-verify-llm.py --summary "Promise summary" \
                      --criteria '[{"id":"AC-1","description":"...","status":"met","evidence":"..."}]' \
                      --proof "Optional summary"

Output (stdout): JSON verdict with reasoning, confidence, and token usage
Logs (stderr): Token usage and cost estimate
"""
import argparse
import json
import sys
import os


def build_evaluation_prompt(summary, criteria, proof):
    """Build the user message for the LLM evaluator."""
    criteria_text = "\n".join(
        f"- {c.get('id', 'N/A')}: {c.get('description', 'N/A')}\n"
        f"  Status: {c.get('status', 'unknown')}\n"
        f"  Evidence: {c.get('evidence', 'None provided')}"
        for c in criteria
    )

    return f"""## Completion Verification Request

### Promise Summary
{summary}

### Acceptance Criteria and Evidence
{criteria_text}

### Additional Proof
{proof if proof else "None provided"}

Evaluate whether the evidence genuinely satisfies ALL acceptance criteria.
Respond with JSON only."""


SYSTEM_PROMPT = (
    "You are a completion verifier for an AI agent orchestration system. "
    "Evaluate whether the provided evidence genuinely satisfies each acceptance criterion. "
    "Be strict but fair. Look for concrete evidence, not vague claims. "
    "If evidence is specific and verifiable, give credit. If evidence is vague or missing, fail it. "
    'Respond with JSON only: {"verdict": "PASS" or "FAIL", "reasoning": "brief explanation", "confidence": 0.0-1.0}'
)

# Sonnet 4.5 pricing (per million tokens)
INPUT_COST_PER_M = 3.0
OUTPUT_COST_PER_M = 15.0


def warn_result(reason):
    """Return a WARN verdict for graceful degradation."""
    print(json.dumps({
        "verdict": "WARN",
        "reasoning": reason,
        "fallback": True
    }))


def main():
    parser = argparse.ArgumentParser(
        description="Programmatic validation gate using Anthropic Claude Sonnet 4.5"
    )
    parser.add_argument("--summary", required=True, help="Promise summary text")
    parser.add_argument("--criteria", required=True, help="JSON array of acceptance criteria")
    parser.add_argument("--proof", default="", help="Optional proof summary")
    args = parser.parse_args()

    # Parse criteria JSON
    try:
        criteria = json.loads(args.criteria)
    except json.JSONDecodeError as e:
        warn_result(f"Invalid criteria JSON: {e}")
        return

    # Check for anthropic package
    try:
        import anthropic
    except ImportError:
        warn_result("anthropic package not installed (pip install anthropic)")
        return

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        warn_result("ANTHROPIC_API_KEY environment variable not set")
        return

    # Build prompt
    user_message = build_evaluation_prompt(args.summary, criteria, args.proof)

    # Call Anthropic API
    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )

        # Extract response text
        response_text = response.content[0].text.strip()

        # Handle markdown code blocks in response
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (``` markers)
            response_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        # Parse LLM response as JSON
        result = json.loads(response_text)

        # Ensure required fields
        if "verdict" not in result:
            result["verdict"] = "WARN"
            result["reasoning"] = result.get("reasoning", "LLM response missing verdict field")

        # Add token usage
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = (input_tokens * INPUT_COST_PER_M / 1_000_000) + \
               (output_tokens * OUTPUT_COST_PER_M / 1_000_000)

        result["tokens_used"] = {
            "input": input_tokens,
            "output": output_tokens
        }
        result["cost_estimate_usd"] = round(cost, 6)

        # Log cost to stderr
        print(
            f"LLM Gate: {input_tokens} input + {output_tokens} output tokens "
            f"(${cost:.4f})",
            file=sys.stderr
        )

        # Output result to stdout
        print(json.dumps(result))

    except anthropic.APIConnectionError:
        warn_result("API connection failed - check network")
    except anthropic.APITimeoutError:
        warn_result("API request timed out (30s limit)")
    except anthropic.AuthenticationError:
        warn_result("Invalid ANTHROPIC_API_KEY")
    except anthropic.RateLimitError:
        warn_result("API rate limit exceeded - try again later")
    except json.JSONDecodeError as e:
        warn_result(f"Failed to parse LLM response as JSON: {e}")
    except (KeyError, IndexError) as e:
        warn_result(f"Unexpected response structure: {e}")
    except Exception as e:
        warn_result(f"Unexpected error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()

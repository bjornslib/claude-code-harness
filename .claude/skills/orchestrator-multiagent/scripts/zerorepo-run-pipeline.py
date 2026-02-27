#!/usr/bin/env python3
"""
ZeroRepo Pipeline Runner

Reliable runner for ZeroRepo operations (init, generate, update) with proper timeout handling.

Root Cause of Previous Timeout Issues:
- litellm.completion() in zerorepo/llm/gateway.py:244 doesn't pass explicit timeout parameter
- It relies on reading LITELLM_REQUEST_TIMEOUT from environment
- Environment variable may not propagate correctly in all execution contexts
- This script sets timeout BEFORE any imports AND monkey-patches litellm as a fallback

Usage:
    zerorepo-run-pipeline.py --operation generate --prd path/to/prd.md --baseline baseline.json
    zerorepo-run-pipeline.py --operation init --project-path .
    zerorepo-run-pipeline.py --operation update --project-path .
"""

import os
import sys
import argparse
import json
import hashlib
from pathlib import Path
from typing import Optional

# CRITICAL: Set timeout BEFORE any imports
# This ensures the environment variable is available when litellm loads
DEFAULT_TIMEOUT = 1200
timeout_from_env = os.environ.get("LITELLM_REQUEST_TIMEOUT")
if not timeout_from_env:
    os.environ["LITELLM_REQUEST_TIMEOUT"] = str(DEFAULT_TIMEOUT)
    print(f"[zerorepo-runner] Setting LITELLM_REQUEST_TIMEOUT={DEFAULT_TIMEOUT}")


def count_baseline_nodes(baseline_path: Path) -> int:
    """Count nodes in baseline JSON for diagnostic output."""
    try:
        with open(baseline_path, 'r') as f:
            baseline = json.load(f)
        return len(baseline.get("nodes", []))
    except Exception as e:
        print(f"[WARNING] Failed to count baseline nodes: {e}")
        return 0


def estimate_prompt_size(prd_path: Path) -> int:
    """Estimate prompt size (rough token count) from PRD file."""
    try:
        with open(prd_path, 'r') as f:
            content = f.read()
        # Rough approximation: 1 token ≈ 4 characters
        return len(content) // 4
    except Exception as e:
        print(f"[WARNING] Failed to estimate prompt size: {e}")
        return 0


def backup_baseline(baseline_path: Path) -> None:
    """Backup existing baseline to baseline.prev.json."""
    if baseline_path.exists():
        backup_path = baseline_path.parent / "baseline.prev.json"
        import shutil
        shutil.copy2(baseline_path, backup_path)
        print(f"[zerorepo-runner] Backed up baseline to: {backup_path}")
    else:
        print("[zerorepo-runner] No existing baseline to backup.")


def run_init(project_path: Path, exclude_patterns: str) -> int:
    """Run zerorepo init operation."""
    print("\n=== ZeroRepo Init ===", flush=True)
    print(f"Project path: {project_path}", flush=True)
    print(f"Exclude patterns: {exclude_patterns}", flush=True)

    # Import after environment setup
    from cobuilder.repomap.cli.app import app

    # Set up sys.argv for typer CLI
    sys.argv = [
        "zerorepo",
        "init",
        str(project_path),
        "--project-path", str(project_path),
        "--exclude", exclude_patterns
    ]

    try:
        app()
        print("\n[zerorepo-runner] Init completed successfully.")
        baseline_path = project_path / ".zerorepo" / "baseline.json"
        if baseline_path.exists():
            node_count = count_baseline_nodes(baseline_path)
            print(f"[zerorepo-runner] Baseline generated: {node_count} nodes")
            print(f"[zerorepo-runner] Output: {baseline_path}")
        return 0
    except Exception as e:
        print(f"\n[ERROR] Init failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_attractor_export(output_dir: Path, prd_ref: str = "") -> int:
    """Generate pipeline.dot from RPGGraph output and validate it.

    Loads the RPGGraph from output_dir/04-rpg.json, converts it to an
    Attractor-compatible DOT pipeline using AttractorExporter, writes the
    result to output_dir/pipeline.dot, and validates via the attractor CLI.

    Args:
        output_dir: Directory containing 04-rpg.json (pipeline output dir).
        prd_ref: Optional PRD reference string embedded in the .dot graph.

    Returns:
        0 on success, 1 on failure.
    """
    import subprocess

    rpg_json_path = output_dir / "04-rpg.json"
    dot_output_path = output_dir / "pipeline.dot"

    print("\n=== Attractor DOT Export ===", flush=True)
    print(f"Loading RPGGraph from: {rpg_json_path}", flush=True)

    if not rpg_json_path.exists():
        print(f"[ERROR] RPGGraph JSON not found: {rpg_json_path}", flush=True)
        print("  Hint: run generate first, or check the output directory.", flush=True)
        return 1

    try:
        from cobuilder.repomap.models.graph import RPGGraph
        content = rpg_json_path.read_text(encoding="utf-8")
        rpg = RPGGraph.model_validate(json.loads(content))
        print(
            f"[zerorepo-runner] Loaded RPGGraph: {rpg.node_count} nodes, "
            f"{rpg.edge_count} edges",
            flush=True,
        )
    except Exception as e:
        print(f"[ERROR] Failed to load RPGGraph: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return 1

    try:
        from cobuilder.repomap.graph_construction.attractor_exporter import AttractorExporter
        exporter = AttractorExporter(prd_ref=prd_ref or "PRD-UNKNOWN")
        dot_content = exporter.export(rpg)
        dot_output_path.write_text(dot_content, encoding="utf-8")
        print(
            f"[zerorepo-runner] Written pipeline DOT: {dot_output_path} "
            f"({len(dot_content)} bytes)",
            flush=True,
        )
    except Exception as e:
        print(f"[ERROR] AttractorExporter failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return 1

    # --- Validate the generated .dot file using the attractor CLI ---
    # Resolve attractor cli.py relative to this script's location.
    # Layout: .claude/skills/orchestrator-multiagent/scripts/zerorepo-run-pipeline.py
    #         .claude/scripts/attractor/cli.py
    this_script = Path(__file__).resolve()
    claude_dir = this_script.parent.parent.parent.parent  # .claude/
    attractor_cli = claude_dir / "scripts" / "attractor" / "cli.py"

    if not attractor_cli.exists():
        print(
            f"[WARNING] Attractor CLI not found at {attractor_cli}; skipping validation.",
            flush=True,
        )
        print(f"[zerorepo-runner] pipeline.dot written (unvalidated): {dot_output_path}", flush=True)
        return 0

    print(f"\n[zerorepo-runner] Validating {dot_output_path} ...", flush=True)
    try:
        result = subprocess.run(
            [sys.executable, str(attractor_cli), "validate", str(dot_output_path)],
            capture_output=False,  # stream to stdout/stderr directly
            text=True,
        )
        if result.returncode == 0:
            print(
                "\n[zerorepo-runner] Attractor validation PASSED.",
                flush=True,
            )
        else:
            print(
                f"\n[zerorepo-runner] Attractor validation FAILED (exit {result.returncode}).",
                flush=True,
            )
            return 1
    except Exception as e:
        print(f"[ERROR] Failed to run attractor validate: {e}", flush=True)
        return 1

    return 0


def run_generate(
    prd_path: Path,
    baseline_path: Optional[Path],
    model: str,
    output_dir: Path,
    skip_enrichment: bool,
    timeout: int,
    fmt: str = "",
) -> int:
    """Run zerorepo generate operation."""
    print("\n=== ZeroRepo Generate ===", flush=True)

    # Verify inputs
    if not prd_path.exists():
        print(f"[ERROR] PRD file not found: {prd_path}", flush=True)
        return 1

    if baseline_path and not baseline_path.exists():
        print(f"[ERROR] Baseline file not found: {baseline_path}", flush=True)
        return 1

    # Diagnostic output
    print(f"PRD file: {prd_path}", flush=True)
    prompt_size = estimate_prompt_size(prd_path)
    print(f"Estimated prompt size: ~{prompt_size:,} tokens", flush=True)

    if baseline_path:
        print(f"Baseline: {baseline_path}", flush=True)
        node_count = count_baseline_nodes(baseline_path)
        print(f"Baseline node count: {node_count:,} nodes", flush=True)
    else:
        print("Baseline: None (no delta report will be generated)", flush=True)

    print(f"Model: {model}", flush=True)
    print(f"Output directory: {output_dir}", flush=True)
    print(f"Skip enrichment: {skip_enrichment}", flush=True)
    print(f"Timeout: {timeout}s", flush=True)

    # Belt-and-suspenders timeout setup
    os.environ["LITELLM_REQUEST_TIMEOUT"] = str(timeout)
    print(f"\n[zerorepo-runner] LITELLM_REQUEST_TIMEOUT set to {timeout}s", flush=True)

    # Import litellm and monkey-patch timeout as fallback
    try:
        import litellm
        litellm.request_timeout = timeout
        print(f"[zerorepo-runner] Also set litellm.request_timeout={timeout} (fallback)", flush=True)
    except ImportError:
        print("[WARNING] Could not import litellm for direct timeout patching", flush=True)
    except Exception as e:
        print(f"[WARNING] Failed to patch litellm.request_timeout: {e}", flush=True)

    # Import after all environment setup
    from cobuilder.repomap.cli.app import app

    # Build sys.argv
    sys.argv = [
        "zerorepo",
        "-v",  # Enable verbose/DEBUG logging for progress visibility
        "generate",
        str(prd_path),
        "--model", model,
        "--output", str(output_dir)
    ]

    if baseline_path:
        sys.argv.extend(["--baseline", str(baseline_path)])

    if skip_enrichment:
        sys.argv.append("--skip-enrichment")

    print(f"\n[zerorepo-runner] Running pipeline (5 stages, ~2-3 minutes)...", flush=True)
    print(f"[zerorepo-runner] Command: {' '.join(sys.argv)}", flush=True)
    print("", flush=True)  # Extra newline before pipeline output starts

    try:
        app()
        print("\n[zerorepo-runner] Generate completed successfully.", flush=True)
        delta_report = output_dir / "05-delta-report.md"
        if delta_report.exists():
            print(f"[zerorepo-runner] Delta report: {delta_report}", flush=True)

        # Post-generate attractor export (when --format attractor-pipeline)
        if fmt == "attractor-pipeline":
            prd_ref = prd_path.stem.upper() if prd_path else ""
            rc = run_attractor_export(output_dir=output_dir, prd_ref=prd_ref)
            if rc != 0:
                return rc

        return 0
    except Exception as e:
        error_msg = str(e)
        print(f"\n[ERROR] Generate failed: {error_msg}", flush=True)

        # Check for timeout specifically
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            print("\n[TIMEOUT DIAGNOSIS]", flush=True)
            print(f"- LITELLM_REQUEST_TIMEOUT was set to: {timeout}s", flush=True)
            print(f"- Baseline size: {node_count if baseline_path else 0} nodes", flush=True)
            print(f"- Estimated prompt: ~{prompt_size:,} tokens", flush=True)
            print("\nSuggestions:", flush=True)
            print("1. Increase --timeout (try 1800 or 2400)", flush=True)
            print("2. Use a faster model (claude-3-5-sonnet-20241022)", flush=True)
            print("3. Split the PRD into smaller specifications", flush=True)
            print("4. Check API rate limits", flush=True)

        import traceback
        traceback.print_exc()
        return 1


def run_update(project_path: Path, exclude_patterns: str) -> int:
    """Run zerorepo update operation (backup + re-init)."""
    print("\n=== ZeroRepo Update ===", flush=True)
    print(f"Project path: {project_path}", flush=True)
    print(f"Exclude patterns: {exclude_patterns}", flush=True)

    baseline_path = project_path / ".zerorepo" / "baseline.json"

    # Backup existing baseline
    backup_baseline(baseline_path)

    # Re-run init
    return run_init(project_path, exclude_patterns)


def main():
    parser = argparse.ArgumentParser(
        description="ZeroRepo Pipeline Runner - Reliable execution with proper timeout handling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize baseline
  %(prog)s --operation init --project-path .

  # Generate delta report
  %(prog)s --operation generate --prd prd.md --baseline baseline.json

  # Generate delta report AND export as Attractor pipeline DOT
  %(prog)s --operation generate --prd prd.md --baseline baseline.json --format attractor-pipeline

  # Update baseline (backup + re-init)
  %(prog)s --operation update --project-path .
        """
    )

    parser.add_argument(
        "--operation",
        choices=["init", "generate", "update"],
        default="generate",
        help="Operation to perform (default: generate)"
    )

    parser.add_argument(
        "--prd",
        type=Path,
        help="Path to PRD file (required for generate)"
    )

    parser.add_argument(
        "--baseline",
        type=Path,
        help="Path to baseline JSON (optional for generate)"
    )

    parser.add_argument(
        "--model",
        default="claude-sonnet-4-5-20250929",
        help="LLM model for analysis (default: claude-sonnet-4-5-20250929)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".zerorepo/output"),
        help="Output directory (default: .zerorepo/output)"
    )

    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        default=False,
        help="Skip enrichment stage (default: run enrichment)"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"LLM request timeout in seconds (default: {DEFAULT_TIMEOUT})"
    )

    parser.add_argument(
        "--format",
        dest="fmt",
        default="",
        choices=["attractor-pipeline"],
        help=(
            "Post-generate output format. "
            "'attractor-pipeline': after generate, load 04-rpg.json, "
            "convert to Attractor DOT, write pipeline.dot, and validate."
        )
    )

    parser.add_argument(
        "--project-path",
        type=Path,
        default=Path("."),
        help="Project root path (for init/update, default: .)"
    )

    parser.add_argument(
        "--exclude",
        default="node_modules,__pycache__,.git,trees,venv,.zerorepo",
        help="Comma-separated exclude patterns for init/update"
    )

    args = parser.parse_args()

    # Validate operation-specific arguments
    if args.operation == "generate":
        if not args.prd:
            parser.error("--prd is required for generate operation")
        return run_generate(
            prd_path=args.prd,
            baseline_path=args.baseline,
            model=args.model,
            output_dir=args.output,
            skip_enrichment=args.skip_enrichment,
            timeout=args.timeout,
            fmt=args.fmt,
        )

    elif args.operation == "init":
        return run_init(
            project_path=args.project_path,
            exclude_patterns=args.exclude
        )

    elif args.operation == "update":
        return run_update(
            project_path=args.project_path,
            exclude_patterns=args.exclude
        )

    else:
        parser.error(f"Unknown operation: {args.operation}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

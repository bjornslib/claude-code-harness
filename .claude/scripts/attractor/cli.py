#!/usr/bin/env python3
"""Attractor CLI — Main entry point for pipeline management tools.

Dispatches subcommands for parsing, validating, querying status,
transitioning states, checkpointing, generating, annotating, and
initializing completion promises for Attractor DOT pipelines.

Usage:
    python3 cli.py parse <file.dot> [--output json]
    python3 cli.py validate <file.dot> [--output json] [--strict]
    python3 cli.py status <file.dot> [--json] [--filter=<status>] [--summary]
    python3 cli.py transition <file.dot> <node_id> <new_status> [--dry-run]
    python3 cli.py checkpoint save <file.dot> [--output=<path>]
    python3 cli.py checkpoint restore <checkpoint.json> [--output=<file.dot>]
    python3 cli.py generate --prd <PRD-REF> [--output pipeline.dot]
    python3 cli.py annotate <file.dot> [--output annotated.dot]
    python3 cli.py init-promise <file.dot> [--json]
    python3 cli.py --help
"""

import os
import sys

# Ensure the script directory is on the path so module imports work
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def main() -> None:
    """Dispatch to the appropriate subcommand."""
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        print()
        print("Subcommands:")
        print("  parse         Parse a DOT file into structured data")
        print("  validate      Validate a DOT file against schema rules")
        print("  status        Display node status table")
        print("  transition    Advance a node's status")
        print("  checkpoint    Save/restore pipeline state")
        print("  generate      Generate pipeline.dot from beads task data")
        print("  annotate      Cross-reference pipeline.dot with beads")
        print("  init-promise  Generate cs-promise commands from pipeline.dot")
        print()
        print("Run 'cli.py <command> --help' for subcommand details.")
        sys.exit(0)

    command = sys.argv[1]
    # Remove the subcommand from argv so sub-modules see correct args
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    if command == "parse":
        from parser import main as parser_main
        parser_main()
    elif command == "validate":
        from validator import main as validator_main
        validator_main()
    elif command == "status":
        from status import main as status_main
        status_main()
    elif command == "transition":
        from transition import main as transition_main
        transition_main()
    elif command == "checkpoint":
        from checkpoint import main as checkpoint_main
        checkpoint_main()
    elif command == "generate":
        from generate import main as generate_main
        generate_main()
    elif command == "annotate":
        from annotate import main as annotate_main
        annotate_main()
    elif command in ("init-promise", "init_promise"):
        from init_promise import main as init_promise_main
        init_promise_main()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Run 'cli.py --help' for available commands.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

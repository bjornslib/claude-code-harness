#!/usr/bin/env python3
"""
Setup script for symlinking Claude Code harness into project directories.
"""

import os
import sys
from pathlib import Path
import argparse


def verify_harness(harness_path: Path) -> bool:
    """Verify that the path contains a valid claude-code-harness."""
    if not harness_path.exists():
        print(f"❌ Error: {harness_path} does not exist")
        return False

    claude_dir = harness_path / ".claude"
    if not claude_dir.exists():
        print(f"❌ Error: {harness_path}/.claude not found")
        return False

    # Check for key files
    required_files = [
        claude_dir / "CLAUDE.md",
        claude_dir / "skills",
        claude_dir / "settings.json",
    ]

    for required_file in required_files:
        if not required_file.exists():
            print(f"❌ Error: {required_file} not found")
            print(f"   {harness_path} doesn't appear to be a valid claude-code-harness")
            return False

    print(f"✓ Verified harness at {harness_path}")
    return True


def check_existing_symlink(target_path: Path) -> tuple[bool, str]:
    """Check if a symlink already exists and return its target."""
    if not target_path.exists() and not target_path.is_symlink():
        return False, ""

    if target_path.is_symlink():
        target = os.readlink(target_path)
        return True, target

    return False, ""


def create_symlink(source: Path, target: Path, force: bool = False) -> bool:
    """Create a symlink from target to source."""
    # Get absolute path
    source_abs = source.resolve()

    # Check if target already exists
    if target.exists() or target.is_symlink():
        is_symlink, current_target = check_existing_symlink(target)

        if is_symlink:
            print(f"⚠  {target.name} symlink already exists")
            print(f"   Current target: {current_target}")

            if not force:
                response = input(f"   Replace it? (y/n): ").strip().lower()
                if response != 'y':
                    print(f"   Skipping {target.name}")
                    return False

            # Remove existing symlink
            target.unlink()
            print(f"   Removed old symlink")
        else:
            print(f"❌ Error: {target} exists but is not a symlink")
            print(f"   Please backup and remove it first:")
            print(f"   mv {target} {target}.backup")
            return False

    # Create symlink
    try:
        os.symlink(source_abs, target)
        print(f"✓ Created symlink: {target.name} -> {source_abs}")
        return True
    except OSError as e:
        print(f"❌ Error creating symlink: {e}")
        return False


def verify_setup(project_dir: Path) -> bool:
    """Verify that the symlink setup is working correctly."""
    claude_link = project_dir / ".claude"

    print("\n📋 Verifying setup...")

    # Check .claude symlink
    if not claude_link.is_symlink():
        print("❌ .claude is not a symlink")
        return False

    if not claude_link.exists():
        print("❌ .claude symlink is broken")
        return False

    print(f"✓ .claude symlink is valid")

    # Check access to key files
    test_files = [
        claude_link / "settings.json",
        claude_link / "CLAUDE.md",
    ]

    for test_file in test_files:
        if test_file.exists():
            print(f"✓ Can access {test_file.name}")
        else:
            print(f"❌ Cannot access {test_file.name}")
            return False

    # Check script permissions
    scripts_dir = claude_link / "scripts" / "message-bus"
    if scripts_dir.exists():
        mb_init = scripts_dir / "mb-init"
        if mb_init.exists() and os.access(mb_init, os.X_OK):
            print(f"✓ Scripts are executable")
        else:
            print(f"⚠  Warning: Some scripts may not be executable")
            print(f"   Run: chmod +x {claude_link.resolve()}/scripts/**/*")

    return True


def print_next_steps(harness_path: Path, mcp_symlinked: bool):
    """Print next steps for the user."""
    print("\n" + "="*60)
    print("✓ Harness setup complete!")
    print("="*60)

    print("\n📚 Configuration:")
    print(f"   .claude -> {harness_path.resolve()}/.claude")
    if mcp_symlinked:
        print(f"   .mcp.json -> {harness_path.resolve()}/.mcp.json")

    print("\n🚀 Next steps:")
    print("   1. Launch Claude Code: claude")
    print("   2. Verify configuration: cat .claude/CLAUDE.md")
    print("   3. Start working:")
    print("      - System 3: ccsystem3")
    print("      - Orchestrator: launchorchestrator [epic-name]")
    print("      - Worker: launchcc (in tmux session)")

    print("\n🔄 To update the harness:")
    print(f"   cd {harness_path.resolve()} && git pull")

    print("\n📖 Documentation:")
    print(f"   - README: {harness_path.resolve()}/README.md")
    print("   - Architecture: .claude/CLAUDE.md")
    print("   - Task Master: .claude/TM_COMMANDS_GUIDE.md")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Setup Claude Code harness symlinks in a project directory"
    )
    parser.add_argument(
        "harness_path",
        type=Path,
        help="Path to the claude-code-harness repository"
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Also symlink .mcp.json (share MCP server configs)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing symlinks without prompting"
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Project directory (default: current directory)"
    )

    args = parser.parse_args()

    # Expand user path
    harness_path = args.harness_path.expanduser()
    project_dir = args.project_dir.expanduser()

    print(f"\n🔧 Setting up Claude Code harness...")
    print(f"   Harness: {harness_path}")
    print(f"   Project: {project_dir}\n")

    # Verify harness
    if not verify_harness(harness_path):
        sys.exit(1)

    # Change to project directory
    os.chdir(project_dir)

    # Create .claude symlink
    claude_source = harness_path / ".claude"
    claude_target = project_dir / ".claude"

    if not create_symlink(claude_source, claude_target, args.force):
        sys.exit(1)

    # Optionally create .mcp.json symlink
    mcp_symlinked = False
    if args.mcp:
        mcp_source = harness_path / ".mcp.json"
        mcp_target = project_dir / ".mcp.json"

        if mcp_source.exists():
            if create_symlink(mcp_source, mcp_target, args.force):
                mcp_symlinked = True
        else:
            print(f"⚠  Warning: {mcp_source} not found, skipping MCP symlink")

    # Verify setup
    if not verify_setup(project_dir):
        print("\n❌ Setup verification failed")
        sys.exit(1)

    # Print next steps
    print_next_steps(harness_path, mcp_symlinked)


if __name__ == "__main__":
    main()

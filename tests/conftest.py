import sys
import os

# Add .claude/hooks to sys.path so tests can import decision_guidance
# and unified_stop_gate modules without installing them as packages.
_hooks_dir = os.path.join(os.path.dirname(__file__), "..", ".claude", "hooks")
_hooks_dir = os.path.abspath(_hooks_dir)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

"""Demo test for validation-agent monitor mode."""
import subprocess
import json
from pathlib import Path

def test_task_list_monitor_detects_changes():
    """Verify task-list-monitor.py can detect task status changes."""
    script = Path.home() / ".claude" / "scripts" / "task-list-monitor.py"
    assert script.exists(), "task-list-monitor.py should exist"

    # Run status check
    result = subprocess.run(
        ["python", str(script), "--list-id", "shared-tasks", "--status", "--json"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Script failed: {result.stderr}"

    data = json.loads(result.stdout)
    assert "total" in data, "Status should include total count"
    assert "completed" in data, "Status should include completed count"

def test_task_list_monitor_changes_detection():
    """Verify --changes flag works."""
    script = Path.home() / ".claude" / "scripts" / "task-list-monitor.py"

    result = subprocess.run(
        ["python", str(script), "--list-id", "shared-tasks", "--changes", "--json"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Script failed: {result.stderr}"

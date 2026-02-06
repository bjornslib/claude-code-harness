#!/usr/bin/env python3
"""
Task List Monitor for Validation Agent

Monitors ~/.claude/tasks/{TASK_LIST_ID}/ for status changes.
Designed to be called periodically by validation-test-agent --monitor mode.

Usage:
    # Get current status snapshot
    python task-list-monitor.py --list-id shared-tasks --status

    # Check for changes since last poll (returns JSON of changes)
    python task-list-monitor.py --list-id shared-tasks --changes

    # Get tasks ready for validation (newly completed)
    python task-list-monitor.py --list-id shared-tasks --ready-for-validation

    # Watch mode (continuous monitoring)
    python task-list-monitor.py --list-id shared-tasks --watch --interval 10
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class TaskStatus:
    id: str
    status: str
    subject: str
    blocks: list
    blocked_by: list


@dataclass
class StatusChange:
    task_id: str
    previous_status: str
    new_status: str
    subject: str
    ready_for_validation: bool


class TaskListMonitor:
    """Monitors a Claude Code task list for changes."""

    def __init__(self, list_id: str):
        self.list_id = list_id
        self.task_dir = Path.home() / ".claude" / "tasks" / list_id
        self.state_file = Path("/tmp") / f".task-monitor-{list_id}.json"

    def get_tasks(self) -> list[TaskStatus]:
        """Load all tasks from the task directory."""
        tasks = []
        if not self.task_dir.exists():
            return tasks

        for task_file in sorted(self.task_dir.glob("*.json"), key=lambda f: int(f.stem)):
            try:
                with open(task_file) as f:
                    data = json.load(f)
                    tasks.append(TaskStatus(
                        id=data.get("id", task_file.stem),
                        status=data.get("status", "unknown"),
                        subject=data.get("subject", ""),
                        blocks=data.get("blocks", []),
                        blocked_by=data.get("blockedBy", []),
                    ))
            except (json.JSONDecodeError, IOError):
                continue
        return tasks

    def get_checksum(self) -> str:
        """Get MD5 checksum of all task files for quick change detection."""
        if not self.task_dir.exists():
            return ""

        content = b""
        for task_file in sorted(self.task_dir.glob("*.json")):
            content += task_file.read_bytes()
        return hashlib.md5(content).hexdigest()

    def get_status_summary(self) -> dict:
        """Get a summary of task statuses."""
        tasks = self.get_tasks()
        summary = {
            "total": len(tasks),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "blocked": 0,
        }
        for task in tasks:
            if task.status in summary:
                summary[task.status] += 1
            if task.blocked_by:
                summary["blocked"] += 1
        return summary

    def save_state(self, tasks: list[TaskStatus], checksum: str):
        """Save current state to file."""
        state = {
            "checksum": checksum,
            "timestamp": time.time(),
            "tasks": {t.id: asdict(t) for t in tasks}
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def load_state(self) -> Optional[dict]:
        """Load previous state from file."""
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def detect_changes(self) -> list[StatusChange]:
        """Detect status changes since last poll."""
        current_tasks = self.get_tasks()
        current_checksum = self.get_checksum()
        prev_state = self.load_state()

        changes = []

        if prev_state is None:
            # First run - save state, no changes to report
            self.save_state(current_tasks, current_checksum)
            return changes

        if prev_state.get("checksum") == current_checksum:
            # No changes
            return changes

        prev_tasks = prev_state.get("tasks", {})

        for task in current_tasks:
            prev_task = prev_tasks.get(task.id)
            if prev_task and prev_task.get("status") != task.status:
                changes.append(StatusChange(
                    task_id=task.id,
                    previous_status=prev_task.get("status"),
                    new_status=task.status,
                    subject=task.subject,
                    ready_for_validation=(task.status == "completed"),
                ))

        # Save new state
        self.save_state(current_tasks, current_checksum)
        return changes

    def get_ready_for_validation(self) -> list[TaskStatus]:
        """Get tasks that are completed and ready for validation."""
        return [t for t in self.get_tasks() if t.status == "completed"]

    def get_in_progress(self) -> list[TaskStatus]:
        """Get tasks currently in progress."""
        return [t for t in self.get_tasks() if t.status == "in_progress"]


def main():
    parser = argparse.ArgumentParser(description="Monitor Claude Code task list")
    parser.add_argument("--list-id", required=True, help="Task list ID (CLAUDE_CODE_TASK_LIST_ID)")
    parser.add_argument("--status", action="store_true", help="Show status summary")
    parser.add_argument("--changes", action="store_true", help="Detect changes since last poll")
    parser.add_argument("--ready-for-validation", action="store_true", help="List completed tasks")
    parser.add_argument("--in-progress", action="store_true", help="List in-progress tasks")
    parser.add_argument("--watch", action="store_true", help="Continuous monitoring mode")
    parser.add_argument("--interval", type=int, default=10, help="Poll interval in seconds (for --watch)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    monitor = TaskListMonitor(args.list_id)

    if not monitor.task_dir.exists():
        print(f"Error: Task directory not found: {monitor.task_dir}", file=sys.stderr)
        sys.exit(1)

    if args.status:
        summary = monitor.get_status_summary()
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"Task List: {args.list_id}")
            print(f"  Total:       {summary['total']}")
            print(f"  Pending:     {summary['pending']}")
            print(f"  In Progress: {summary['in_progress']}")
            print(f"  Completed:   {summary['completed']}")
            print(f"  Blocked:     {summary['blocked']}")

    elif args.changes:
        changes = monitor.detect_changes()
        if args.json:
            print(json.dumps([asdict(c) for c in changes], indent=2))
        else:
            if not changes:
                print("No changes detected")
            else:
                for change in changes:
                    marker = "✅" if change.ready_for_validation else "→"
                    print(f"{marker} Task #{change.task_id}: {change.previous_status} → {change.new_status}")
                    print(f"   {change.subject}")

    elif args.ready_for_validation:
        tasks = monitor.get_ready_for_validation()
        if args.json:
            print(json.dumps([asdict(t) for t in tasks], indent=2))
        else:
            if not tasks:
                print("No tasks ready for validation")
            else:
                print("Tasks ready for validation:")
                for t in tasks:
                    print(f"  #{t.id}: {t.subject}")

    elif args.in_progress:
        tasks = monitor.get_in_progress()
        if args.json:
            print(json.dumps([asdict(t) for t in tasks], indent=2))
        else:
            if not tasks:
                print("No tasks in progress")
            else:
                print("Tasks in progress:")
                for t in tasks:
                    print(f"  #{t.id}: {t.subject}")

    elif args.watch:
        print(f"Watching {monitor.task_dir} every {args.interval}s...")
        print("Press Ctrl+C to stop")

        # Initialize state
        monitor.detect_changes()

        try:
            while True:
                time.sleep(args.interval)
                changes = monitor.detect_changes()
                if changes:
                    timestamp = time.strftime("%H:%M:%S")
                    for change in changes:
                        marker = "✅" if change.ready_for_validation else "→"
                        print(f"[{timestamp}] {marker} Task #{change.task_id}: {change.previous_status} → {change.new_status}")
                        if change.ready_for_validation:
                            print(f"           READY FOR VALIDATION: {change.subject}")
        except KeyboardInterrupt:
            print("\nStopped")

    else:
        # Default: show all tasks
        tasks = monitor.get_tasks()
        if args.json:
            print(json.dumps([asdict(t) for t in tasks], indent=2))
        else:
            for t in tasks:
                blocked = " [BLOCKED]" if t.blocked_by else ""
                print(f"#{t.id} [{t.status}]{blocked} {t.subject}")


if __name__ == "__main__":
    main()

"""Tests for cobuilder.pipeline.taskmaster_bridge."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cobuilder.pipeline.taskmaster_bridge import extract_task_ids_for_node, run_taskmaster_parse


def test_run_taskmaster_parse_success(tmp_path):
    tasks_json = tmp_path / ".taskmaster" / "tasks" / "tasks.json"
    tasks_json.parent.mkdir(parents=True)
    tasks_json.write_text('{"tasks": [{"id": 1, "title": "Implement auth"}]}')

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = run_taskmaster_parse("test.md", str(tmp_path))

    assert result == {"tasks": [{"id": 1, "title": "Implement auth"}]}


def test_run_taskmaster_parse_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
        result = run_taskmaster_parse("test.md", "/tmp")
    assert result == {}


def test_run_taskmaster_parse_nonzero_returncode(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Some error")
        result = run_taskmaster_parse("test.md", str(tmp_path))
    assert result == {}


def test_run_taskmaster_parse_npx_not_found():
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        result = run_taskmaster_parse("test.md", "/tmp")
    assert result == {}


def test_run_taskmaster_parse_missing_tasks_json(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = run_taskmaster_parse("test.md", str(tmp_path))
    # tasks.json doesn't exist
    assert result == {}


def test_run_taskmaster_parse_invalid_json(tmp_path):
    tasks_json = tmp_path / ".taskmaster" / "tasks" / "tasks.json"
    tasks_json.parent.mkdir(parents=True)
    tasks_json.write_text("not valid json {{")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = run_taskmaster_parse("test.md", str(tmp_path))
    assert result == {}


def test_extract_task_ids_title_match():
    tasks = {"tasks": [{"id": 5, "title": "Add auth endpoint", "subtasks": []}]}
    matches = extract_task_ids_for_node(tasks, "implement auth endpoint")
    assert len(matches) == 1
    assert matches[0]["id"] == 5


def test_extract_task_ids_no_match():
    tasks = {"tasks": [{"id": 1, "title": "Deploy database", "subtasks": []}]}
    matches = extract_task_ids_for_node(tasks, "implement auth endpoint")
    assert matches == []


def test_extract_task_ids_empty_tasks():
    assert extract_task_ids_for_node({}, "some title") == []
    assert extract_task_ids_for_node(None, "some title") == []


def test_extract_task_ids_empty_node_title():
    tasks = {"tasks": [{"id": 1, "title": "Auth", "subtasks": []}]}
    assert extract_task_ids_for_node(tasks, "") == []


def test_extract_task_ids_with_subtasks():
    tasks = {
        "tasks": [
            {
                "id": 3,
                "title": "Implement auth module",
                "subtasks": [{"id": "3.1"}, {"id": "3.2"}],
            }
        ]
    }
    matches = extract_task_ids_for_node(tasks, "auth module implementation")
    assert len(matches) == 1
    assert matches[0]["subtasks"] == ["3.1", "3.2"]


def test_extract_task_ids_multiple_matches():
    tasks = {
        "tasks": [
            {"id": 1, "title": "Add auth login endpoint", "subtasks": []},
            {"id": 2, "title": "Auth token refresh endpoint", "subtasks": []},
            {"id": 3, "title": "Deploy database schema", "subtasks": []},
        ]
    }
    matches = extract_task_ids_for_node(tasks, "auth endpoint")
    ids = [m["id"] for m in matches]
    assert 1 in ids
    assert 2 in ids
    assert 3 not in ids

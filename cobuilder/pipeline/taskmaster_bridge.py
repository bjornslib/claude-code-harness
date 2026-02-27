"""TaskMaster bridge — calls task-master-ai CLI via subprocess."""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def run_taskmaster_parse(enriched_sd_path: str, project_root: str) -> dict:
    """Call task-master-ai parse-prd via subprocess.

    Returns parsed tasks dict from .taskmaster/tasks/tasks.json.
    Returns {} on timeout or failure (logged, not raised).
    """
    try:
        result = subprocess.run(
            ["npx", "task-master-ai", "parse-prd",
             "--input", enriched_sd_path,
             "--project-root", project_root],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            logger.warning("task-master-ai failed (rc=%d): %s", result.returncode, result.stderr[:500])
            return {}
    except subprocess.TimeoutExpired:
        logger.warning("task-master-ai timed out after 120s")
        return {}
    except FileNotFoundError:
        logger.warning("npx not found — skipping TaskMaster parse")
        return {}

    tasks_path = Path(project_root) / ".taskmaster" / "tasks" / "tasks.json"
    if not tasks_path.exists():
        logger.warning("tasks.json not found at %s", tasks_path)
        return {}

    try:
        return json.loads(tasks_path.read_text())
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse tasks.json: %s", e)
        return {}


def extract_task_ids_for_node(tasks: dict, node_title: str) -> list[dict]:
    """Find TaskMaster tasks matching a pipeline node by title similarity.

    Returns list of {id, title, subtasks: []} dicts.
    """
    if not tasks or not node_title:
        return []

    node_words = set(node_title.lower().split())
    matches = []

    task_list = tasks.get("tasks", []) if isinstance(tasks, dict) else []
    for task in task_list:
        task_title = task.get("title", "")
        task_words = set(task_title.lower().split())

        if not node_words or not task_words:
            continue

        overlap = len(node_words & task_words) / max(len(node_words), len(task_words))
        if overlap >= 0.4:  # 40% word overlap threshold
            matches.append({
                "id": task.get("id"),
                "title": task_title,
                "subtasks": [s.get("id") for s in task.get("subtasks", [])],
            })

    return matches

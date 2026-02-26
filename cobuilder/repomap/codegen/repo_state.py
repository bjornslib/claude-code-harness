"""Repository state management during code generation.

Provides syntax validation, dirty-file tracking, and file revert
capabilities so that the code generation pipeline can detect and
recover from invalid intermediate states.
"""

from __future__ import annotations

import ast
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Standard Python gitignore patterns
_GITIGNORE_CONTENT = """\
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Distribution / packaging
dist/
build/
*.egg-info/
*.egg

# Virtual environments
.venv/
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Testing / coverage
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/

# OS
.DS_Store
Thumbs.db

# Environment variables
.env
.env.local
"""


class RepositoryStateManager:
    """Track and validate file state during code generation.

    Maintains a backup directory so that files can be reverted to the
    last known good version if a generation step produces invalid code.

    Args:
        workspace_dir: Root directory of the generated repository.
    """

    def __init__(self, workspace_dir: Path) -> None:
        self._workspace_dir = workspace_dir
        self._backup_dir = workspace_dir / ".zerorepo_backups"
        self._dirty_files: set[Path] = set()

    # ------------------------------------------------------------------
    # Dirty file tracking
    # ------------------------------------------------------------------

    def mark_dirty(self, filepath: Path) -> None:
        """Mark *filepath* as modified.

        Before recording the path a backup of the file is created (if
        the file exists) so that :meth:`revert_file` can restore it.

        Args:
            filepath: Path to the modified file.
        """
        if filepath.exists():
            self._create_backup(filepath)
        self._dirty_files.add(filepath)

    def track_dirty_files(self) -> list[Path]:
        """Return the list of files that have been marked dirty.

        Returns:
            Sorted list of dirty file paths.
        """
        return sorted(self._dirty_files)

    # ------------------------------------------------------------------
    # Syntax validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_syntax(filepath: Path) -> bool:
        """Check whether *filepath* contains valid Python.

        Args:
            filepath: Path to a ``.py`` file.

        Returns:
            ``True`` if the file parses without errors, ``False``
            otherwise.
        """
        try:
            source = filepath.read_text(encoding="utf-8")
            ast.parse(source, filename=str(filepath))
            return True
        except (SyntaxError, ValueError):
            return False
        except OSError:
            return False

    def validate_all_syntax(self) -> dict[Path, bool]:
        """Validate syntax for every Python file in the workspace.

        Returns:
            Mapping of file path to validation result.
        """
        results: dict[Path, bool] = {}
        for py_file in self._workspace_dir.rglob("*.py"):
            # Skip backup directory
            if self._backup_dir.name in py_file.parts:
                continue
            results[py_file] = self.validate_syntax(py_file)
        return results

    # ------------------------------------------------------------------
    # Backup and revert
    # ------------------------------------------------------------------

    def _create_backup(self, filepath: Path) -> None:
        """Create a backup copy of *filepath*.

        Backups are stored under ``.zerorepo_backups/`` mirroring the
        relative directory structure.
        """
        try:
            relative = filepath.relative_to(self._workspace_dir)
        except ValueError:
            relative = Path(filepath.name)

        backup_path = self._backup_dir / relative
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(filepath), str(backup_path))
        logger.debug("Backed up %s -> %s", filepath, backup_path)

    def revert_file(self, filepath: Path) -> bool:
        """Revert *filepath* to its last backed-up version.

        Args:
            filepath: Path to the file to revert.

        Returns:
            ``True`` if the revert succeeded, ``False`` if no backup
            exists.
        """
        try:
            relative = filepath.relative_to(self._workspace_dir)
        except ValueError:
            relative = Path(filepath.name)

        backup_path = self._backup_dir / relative
        if not backup_path.exists():
            logger.warning("No backup found for %s", filepath)
            return False

        shutil.copy2(str(backup_path), str(filepath))
        self._dirty_files.discard(filepath)
        logger.info("Reverted %s from backup", filepath)
        return True

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_gitignore() -> str:
        """Return standard Python ``.gitignore`` content.

        Returns:
            Multiline string suitable for writing to ``.gitignore``.
        """
        return _GITIGNORE_CONTENT

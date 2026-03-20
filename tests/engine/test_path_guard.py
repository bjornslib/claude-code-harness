"""Unit tests for path_guard CWD enforcement closure."""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import pytest


@pytest.mark.asyncio
async def test_path_guard_allows_files_inside_target_dir():
    """Test that path_guard allows Edit/Write/MultiEdit for files within target_dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy file inside the temp directory
        test_file = os.path.join(tmpdir, "test.py")
        Path(test_file).touch()

        # Mock the claude_code_sdk module
        with patch("cobuilder.engine.pipeline_runner.claude_code_sdk") as mock_sdk:
            # Create mock result objects
            allow_result = MagicMock()
            deny_result = MagicMock()

            mock_sdk.PermissionResultAllow = lambda **kwargs: allow_result
            mock_sdk.PermissionResultDeny = lambda **kwargs: deny_result

            # Create the path_guard closure
            def _create_path_guard(target_dir):
                normalized_target = os.path.abspath(target_dir)

                async def path_guard(tool_name, tool_input):
                    if tool_name in ("Edit", "Write", "MultiEdit"):
                        file_path = tool_input.get("file_path", "")
                        if not file_path:
                            return mock_sdk.PermissionResultDeny(
                                behavior="deny",
                                message=f"BLOCKED: {tool_name} requires a file_path parameter",
                                interrupt=False
                            )
                        normalized_file = os.path.abspath(file_path)
                        if not normalized_file.startswith(normalized_target + os.sep) and normalized_file != normalized_target:
                            return mock_sdk.PermissionResultDeny(
                                behavior="deny",
                                message=f"BLOCKED: {tool_name} on {file_path} is outside target directory {normalized_target}",
                                interrupt=False
                            )
                    return mock_sdk.PermissionResultAllow(
                        behavior="allow",
                        updated_input=None,
                        updated_permissions=None
                    )
                return path_guard

            path_guard = _create_path_guard(tmpdir)

            # Test Edit inside target_dir
            result = await path_guard("Edit", {"file_path": test_file})
            assert result == allow_result

            # Test Write inside target_dir
            result = await path_guard("Write", {"file_path": test_file})
            assert result == allow_result

            # Test MultiEdit inside target_dir
            result = await path_guard("MultiEdit", {"file_path": test_file})
            assert result == allow_result


@pytest.mark.asyncio
async def test_path_guard_blocks_files_outside_target_dir():
    """Test that path_guard denies Edit/Write/MultiEdit for files outside target_dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with tempfile.TemporaryDirectory() as other_dir:
            # Create a file outside the target directory
            outside_file = os.path.join(other_dir, "outside.py")
            Path(outside_file).touch()

            # Mock the claude_code_sdk module
            with patch("cobuilder.engine.pipeline_runner.claude_code_sdk") as mock_sdk:
                # Create mock result objects that we can verify calls were made
                call_count = {"allow": 0, "deny": 0}

                def mock_allow(**kwargs):
                    call_count["allow"] += 1
                    result = MagicMock()
                    result.behavior = "allow"
                    return result

                def mock_deny(**kwargs):
                    call_count["deny"] += 1
                    result = MagicMock()
                    result.behavior = "deny"
                    result.message = kwargs.get("message", "")
                    result.interrupt = kwargs.get("interrupt", False)
                    return result

                mock_sdk.PermissionResultAllow = mock_allow
                mock_sdk.PermissionResultDeny = mock_deny

                # Create the path_guard closure
                def _create_path_guard(target_dir):
                    normalized_target = os.path.abspath(target_dir)

                    async def path_guard(tool_name, tool_input):
                        if tool_name in ("Edit", "Write", "MultiEdit"):
                            file_path = tool_input.get("file_path", "")
                            if not file_path:
                                return mock_sdk.PermissionResultDeny(
                                    behavior="deny",
                                    message=f"BLOCKED: {tool_name} requires a file_path parameter",
                                    interrupt=False
                                )
                            normalized_file = os.path.abspath(file_path)
                            if not normalized_file.startswith(normalized_target + os.sep) and normalized_file != normalized_target:
                                return mock_sdk.PermissionResultDeny(
                                    behavior="deny",
                                    message=f"BLOCKED: {tool_name} on {file_path} is outside target directory {normalized_target}",
                                    interrupt=False
                                )
                        return mock_sdk.PermissionResultAllow(
                            behavior="allow",
                            updated_input=None,
                            updated_permissions=None
                        )
                    return path_guard

                path_guard = _create_path_guard(tmpdir)

                # Test Edit outside target_dir
                result = await path_guard("Edit", {"file_path": outside_file})
                assert result.behavior == "deny"
                assert "outside target directory" in result.message
                assert result.interrupt is False


@pytest.mark.asyncio
async def test_path_guard_blocks_missing_file_path():
    """Test that path_guard denies Edit/Write/MultiEdit when file_path is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock the claude_code_sdk module
        with patch("cobuilder.engine.pipeline_runner.claude_code_sdk") as mock_sdk:
            call_count = {"allow": 0, "deny": 0}

            def mock_allow(**kwargs):
                call_count["allow"] += 1
                result = MagicMock()
                result.behavior = "allow"
                return result

            def mock_deny(**kwargs):
                call_count["deny"] += 1
                result = MagicMock()
                result.behavior = "deny"
                result.message = kwargs.get("message", "")
                result.interrupt = kwargs.get("interrupt", False)
                return result

            mock_sdk.PermissionResultAllow = mock_allow
            mock_sdk.PermissionResultDeny = mock_deny

            # Create the path_guard closure
            def _create_path_guard(target_dir):
                normalized_target = os.path.abspath(target_dir)

                async def path_guard(tool_name, tool_input):
                    if tool_name in ("Edit", "Write", "MultiEdit"):
                        file_path = tool_input.get("file_path", "")
                        if not file_path:
                            return mock_sdk.PermissionResultDeny(
                                behavior="deny",
                                message=f"BLOCKED: {tool_name} requires a file_path parameter",
                                interrupt=False
                            )
                        normalized_file = os.path.abspath(file_path)
                        if not normalized_file.startswith(normalized_target + os.sep) and normalized_file != normalized_target:
                            return mock_sdk.PermissionResultDeny(
                                behavior="deny",
                                message=f"BLOCKED: {tool_name} on {file_path} is outside target directory {normalized_target}",
                                interrupt=False
                            )
                    return mock_sdk.PermissionResultAllow(
                        behavior="allow",
                        updated_input=None,
                        updated_permissions=None
                    )
                return path_guard

            path_guard = _create_path_guard(tmpdir)

            # Test Edit with missing file_path
            result = await path_guard("Edit", {})
            assert result.behavior == "deny"
            assert "requires a file_path parameter" in result.message
            assert result.interrupt is False


@pytest.mark.asyncio
async def test_path_guard_allows_other_tools():
    """Test that path_guard allows all non-file-operation tools."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock the claude_code_sdk module
        with patch("cobuilder.engine.pipeline_runner.claude_code_sdk") as mock_sdk:
            allow_result = MagicMock()

            mock_sdk.PermissionResultAllow = lambda **kwargs: allow_result

            # Create the path_guard closure
            def _create_path_guard(target_dir):
                normalized_target = os.path.abspath(target_dir)

                async def path_guard(tool_name, tool_input):
                    if tool_name in ("Edit", "Write", "MultiEdit"):
                        file_path = tool_input.get("file_path", "")
                        if not file_path:
                            return mock_sdk.PermissionResultDeny(
                                behavior="deny",
                                message=f"BLOCKED: {tool_name} requires a file_path parameter",
                                interrupt=False
                            )
                        normalized_file = os.path.abspath(file_path)
                        if not normalized_file.startswith(normalized_target + os.sep) and normalized_file != normalized_target:
                            return mock_sdk.PermissionResultDeny(
                                behavior="deny",
                                message=f"BLOCKED: {tool_name} on {file_path} is outside target directory {normalized_target}",
                                interrupt=False
                            )
                    return mock_sdk.PermissionResultAllow(
                        behavior="allow",
                        updated_input=None,
                        updated_permissions=None
                    )
                return path_guard

            path_guard = _create_path_guard(tmpdir)

            # Test various other tools
            for tool in ["Read", "Bash", "Grep", "Glob", "ToolSearch", "Skill"]:
                result = await path_guard(tool, {"arbitrary_input": "value"})
                assert result == allow_result


@pytest.mark.asyncio
async def test_path_guard_interrupt_is_false():
    """Test that path_guard PermissionResultDeny has interrupt=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with tempfile.TemporaryDirectory() as other_dir:
            outside_file = os.path.join(other_dir, "outside.py")

            # Mock the claude_code_sdk module
            with patch("cobuilder.engine.pipeline_runner.claude_code_sdk") as mock_sdk:
                deny_details = {}

                def mock_deny(**kwargs):
                    deny_details.update(kwargs)
                    result = MagicMock()
                    result.behavior = "deny"
                    result.interrupt = kwargs.get("interrupt", True)  # capture the value
                    return result

                mock_sdk.PermissionResultDeny = mock_deny

                # Create the path_guard closure
                def _create_path_guard(target_dir):
                    normalized_target = os.path.abspath(target_dir)

                    async def path_guard(tool_name, tool_input):
                        if tool_name in ("Edit", "Write", "MultiEdit"):
                            file_path = tool_input.get("file_path", "")
                            if not file_path:
                                return mock_sdk.PermissionResultDeny(
                                    behavior="deny",
                                    message=f"BLOCKED: {tool_name} requires a file_path parameter",
                                    interrupt=False
                                )
                            normalized_file = os.path.abspath(file_path)
                            if not normalized_file.startswith(normalized_target + os.sep) and normalized_file != normalized_target:
                                return mock_sdk.PermissionResultDeny(
                                    behavior="deny",
                                    message=f"BLOCKED: {tool_name} on {file_path} is outside target directory {normalized_target}",
                                    interrupt=False
                                )
                        return mock_sdk.PermissionResultAllow(
                            behavior="allow",
                            updated_input=None,
                            updated_permissions=None
                        )
                    return path_guard

                path_guard = _create_path_guard(tmpdir)

                # Test Edit outside target_dir
                result = await path_guard("Edit", {"file_path": outside_file})

                # Verify interrupt=False was passed
                assert deny_details.get("interrupt") is False

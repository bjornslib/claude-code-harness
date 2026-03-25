# Changelog

All notable changes to the Claude Code Harness Setup project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial public release preparation
- MIT License for open source publication
- Comprehensive documentation architecture
- Multi-agent orchestration framework with 3-level hierarchy
- MCP server integration for extended capabilities
- Skills library with progressive disclosure
- Hooks system for lifecycle automation
- GitHub Actions CI workflow
- pytest-cov coverage enforcement (90% threshold)
- Pre-commit hooks configuration with secret detection
- Dependabot configuration for dependency updates

### Security

- Scrubbed all plaintext API keys from configuration
- Added environment variable references for sensitive credentials
- Created `.mcp.json.example` template for safe configuration

## [1.0.0] - 2026-03-14

### Added

- Initial release of Claude Code Harness Setup
- Core configuration framework for multi-agent AI orchestration
- Output styles for CoBuilder and Orchestrator modes
- Skills library with 20+ specialized skills
- MCP server integration (11 servers configured)
- Hooks for session lifecycle automation
- Documentation standards with doc-gardener linter
- Native Agent Teams support via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`
- Task Master integration for task decomposition
- Beads integration for persistent issue tracking

[Unreleased]: https://github.com/faie-group/claude-harness-setup/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/faie-group/claude-harness-setup/releases/tag/v1.0.0
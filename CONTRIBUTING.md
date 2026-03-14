# Contributing to Claude Harness Setup

Thank you for your interest in contributing to this Claude Code harness configuration framework!

## Development Setup

### Prerequisites

- Python 3.10+
- Node.js 18+ (for MCP server dependencies)
- Claude Code CLI (`claude`)
- Git

### Getting Started

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd claude-harness-setup
   ```

2. **Install Python dependencies**
   ```bash
   pip install -e .
   # or with development dependencies
   pip install -e ".[dev]"
   ```

3. **Copy environment template**
   ```bash
   cp cobuilder/engine/.env.example cobuilder/engine/.env
   # Edit .env with your API keys
   ```

4. **Run tests**
   ```bash
   pytest tests/ -v
   ```

## Project Structure

```
claude-harness-setup/
├── .claude/           # Claude Code configuration
│   ├── skills/        # Explicitly invoked agent skills
│   ├── output-styles/ # Auto-loaded agent behaviors
│   ├── hooks/         # Lifecycle event handlers
│   └── scripts/       # CLI utilities
├── .cobuilder/        # CoBuilder templates and state
├── cobuilder/         # Main Python package
│   ├── engine/        # Pipeline execution engine
│   ├── templates/     # Template system
│   └── sidecar/       # Stream summarizer
├── tests/             # Test suite
└── docs/              # Documentation
```

## Development Workflow

### Branch Naming

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring

### Commit Messages

Follow conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Maintenance

### Testing

All new code should have corresponding tests:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/engine/test_runner.py -v

# Run with coverage
pytest tests/ --cov=cobuilder --cov-report=html
```

### Code Quality

- Follow PEP 8 for Python code
- Use type hints for all function signatures
- Write docstrings for public APIs
- Run `ruff check .` before committing

## Adding New Skills

Skills are stored in `.claude/skills/` and must follow the skill template pattern:

1. Create directory: `.claude/skills/your-skill/`
2. Add `SKILL.md` with frontmatter:
   ```yaml
   ---
   title: "Your Skill Name"
   status: active
   type: skill
   last_verified: 2026-03-14
   grade: authoritative
   ---
   ```
3. Document usage patterns and when to invoke

## Adding New Templates

Templates are Jinja2 DOT files in `.cobuilder/templates/`:

1. Create template directory: `.cobuilder/templates/your-template/`
2. Add `template.dot.j2` (Jinja2-templated DOT graph)
3. Add `manifest.yaml` with parameters and constraints
4. Add tests in `tests/templates/`

## MCP Server Integration

MCP servers are configured in `.mcp.json`. To add a new server:

1. Add server configuration to `.mcp.json`
2. Create skill wrapper in `.claude/skills/mcp-skills/<server-name>/`
3. Document in the skill's `SKILL.md`

## Security

- **Never commit secrets** - Use `.env` files (ignored by git)
- **API keys** - Store in environment variables
- **Review .gitignore** - Ensure sensitive files are excluded

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with tests
3. Run all tests and linting
4. Submit PR with description of changes
5. Address review feedback

## Questions?

Open an issue for:
- Bug reports
- Feature requests
- Documentation improvements
- Questions about usage

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
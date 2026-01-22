#!/bin/bash

# Setup script for Claude Code Groq-Enhanced Statusline
# This script helps configure and test the statusline

echo "🚀 Claude Code Groq-Enhanced Statusline Setup"
echo "============================================"
echo ""

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "❌ jq is not installed. Please install it first:"
    echo "   brew install jq  (on macOS)"
    echo "   apt-get install jq  (on Ubuntu/Debian)"
    exit 1
fi

# Check for GROQ_API_KEY
if [[ -z "$GROQ_API_KEY" ]]; then
    echo "⚠️  GROQ_API_KEY is not set."
    echo ""
    echo "To use Groq AI analysis, you need to:"
    echo "1. Get a free API key from https://console.groq.com"
    echo "2. Add to your shell config (~/.zshrc or ~/.bashrc):"
    echo "   export GROQ_API_KEY='your-api-key-here'"
    echo ""
    echo "The statusline will still work without it, using fallback analysis."
    echo ""
    read -p "Continue without Groq API? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ GROQ_API_KEY is set"
fi

# Get the directory where this script is located (project's .claude directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Make scripts executable
chmod +x "$SCRIPT_DIR/statusline-python.sh" 2>/dev/null
chmod +x "$SCRIPT_DIR/statusline_analyzer.py" 2>/dev/null

echo "✅ Scripts made executable"

# Create Claude settings if it doesn't exist
SETTINGS_FILE="$HOME/.claude/settings.json"
if [[ ! -f "$SETTINGS_FILE" ]]; then
    echo "📝 Creating Claude settings file..."
    cat > "$SETTINGS_FILE" << EOF
{
  "statusLine": {
    "type": "command",
    "command": "$SCRIPT_DIR/statusline-python.sh",
    "padding": 0
  }
}
EOF
    echo "✅ Settings file created"
else
    echo "⚠️  Settings file already exists at $SETTINGS_FILE"
    echo "   Current statusline configuration:"
    jq '.statusLine' "$SETTINGS_FILE" 2>/dev/null || echo "   No statusline configured"
    echo ""
    read -p "Update statusline to use groq-enhanced version? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Backup existing settings
        cp "$SETTINGS_FILE" "${SETTINGS_FILE}.backup"
        # Update statusline configuration
        jq --arg cmd "$SCRIPT_DIR/statusline-python.sh" '.statusLine = {"type": "command", "command": $cmd, "padding": 0}' "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp" && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
        echo "✅ Settings updated (backup saved as settings.json.backup)"
    fi
fi

echo ""
echo "📊 Statusline Configuration:"
echo "============================"
echo "Using: statusline-python.sh"
echo "Features:"
echo "  • AI-powered context analysis with Groq"
echo "  • Automatic GROQ_API_KEY loading from .env files"
echo "  • Real-time conversation tracking"
echo "  • 30-second response caching"
echo ""

# Test the statusline
echo "🧪 Testing statusline..."
echo "------------------------"

# Use real session data if available, otherwise create minimal test input
if [[ -n "$SESSION_ID" ]] && [[ -n "$MODEL_NAME" ]]; then
    # Use actual Claude Code environment variables if available
    TEST_INPUT=$(cat << EOF
{
  "session_id": "$SESSION_ID",
  "model": {
    "display_name": "$MODEL_NAME"
  },
  "workspace": {
    "current_dir": "$(pwd)"
  }
}
EOF
)
else
    # Minimal test without mock data
    TEST_INPUT=$(cat << EOF
{
  "workspace": {
    "current_dir": "$(pwd)"
  }
}
EOF
)
fi

echo "Test output:"
echo "$TEST_INPUT" | "$SCRIPT_DIR/statusline-python.sh"
echo ""
echo ""

echo "✅ Setup complete!"
echo ""
echo "📌 Next steps:"
echo "1. Restart Claude Code for changes to take effect"
echo "2. The statusline will appear at the bottom of your Claude Code interface"
echo "3. It updates automatically as you chat"
echo ""

if [[ -z "$GROQ_API_KEY" ]]; then
    echo "💡 To enable AI-powered analysis:"
    echo "   1. Get a free Groq API key from https://console.groq.com"
    echo "   2. Add to your shell: export GROQ_API_KEY='your-key'"
    echo "   3. The statusline will automatically use Groq when available"
fi

echo ""
echo "🔧 To switch between statusline versions, update ~/.claude/settings.json"
echo "   or run this setup script again."
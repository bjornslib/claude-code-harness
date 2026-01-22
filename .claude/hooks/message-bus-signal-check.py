#!/usr/bin/env python3
"""
PostToolUse hook - checks for message bus signals.

This hook fires after every tool execution. It checks for a signal file
indicating that the background monitor received a message. If found,
it reads the message and injects it into the CC context.

Fast path: Signal file check is < 1ms. Only processes if signal exists.

Hook type: PostToolUse
"""

import json
import os
import sys
from pathlib import Path


def get_instance_id() -> str:
    """Get instance ID from environment or derive from context."""
    # Try explicit session ID first
    instance_id = os.environ.get("CLAUDE_SESSION_ID")
    if instance_id:
        return instance_id

    # Try to derive from tmux
    tmux_pane = os.environ.get("TMUX_PANE")
    if tmux_pane:
        return tmux_pane.replace("%", "pane-")

    # Default fallback
    return "default"


def main():
    try:
        # Read hook input (not used for signal check, but required)
        try:
            hook_input = json.load(sys.stdin)
        except (json.JSONDecodeError, EOFError):
            hook_input = {}

        # Get paths
        instance_id = get_instance_id()
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        signal_dir = Path(project_dir) / ".claude" / "message-bus" / "signals"
        signal_file = signal_dir / f"{instance_id}.signal"
        msg_file = signal_dir / f"{instance_id}.msg"

        # Fast path: no signal = no-op (< 1ms filesystem check)
        if not signal_file.exists():
            print(json.dumps({"continue": True}))
            return

        # Signal exists - read the message content
        message_content = ""
        message_type = "unknown"
        from_instance = "unknown"

        if msg_file.exists():
            try:
                raw = msg_file.read_text().strip()
                parts = raw.split("|", 2)
                if len(parts) >= 3:
                    from_instance = parts[0]
                    message_type = parts[1]
                    payload = parts[2]

                    # Try to parse payload as JSON for nice formatting
                    try:
                        parsed_payload = json.loads(payload)
                        subject = parsed_payload.get("subject", "No subject")
                        body = parsed_payload.get("body", payload)
                        context = parsed_payload.get("context", {})

                        message_content = f"""
## 📨 Incoming Message

**From**: `{from_instance}`
**Type**: `{message_type}`
**Subject**: {subject}

{body}
"""
                        if context:
                            message_content += f"""
**Context**:
```json
{json.dumps(context, indent=2)}
```
"""
                    except json.JSONDecodeError:
                        # Payload is not JSON, display raw
                        message_content = f"""
## 📨 Incoming Message

**From**: `{from_instance}`
**Type**: `{message_type}`

```
{payload}
```
"""
                elif len(parts) == 2:
                    from_instance = parts[0]
                    message_content = f"""
## 📨 Message from `{from_instance}`

{parts[1]}
"""
                else:
                    message_content = f"""
## 📨 Message Received

```
{raw}
```
"""
            except Exception as e:
                message_content = f"""
## 📨 Message Signal Detected

Error reading message content: {e}
"""
        else:
            message_content = """
## 📨 Message Signal Detected

Signal file exists but no message content found.
Check messages manually with: `/check-messages`
"""

        # Clear signal files (consume the message)
        try:
            signal_file.unlink(missing_ok=True)
        except Exception:
            pass

        try:
            msg_file.unlink(missing_ok=True)
        except Exception:
            pass

        # Determine priority hint based on message type
        priority_hint = ""
        if message_type == "urgent":
            priority_hint = "\n\n⚠️ **URGENT**: This message requires immediate attention."
        elif message_type == "guidance":
            priority_hint = "\n\n💡 **Guidance from System 3**: Consider adjusting your approach based on this input."
        elif message_type == "query":
            priority_hint = "\n\n❓ **Query**: A response may be expected."

        # Inject message into CC context
        print(json.dumps({
            "continue": True,
            "systemMessage": f"""
{message_content}
{priority_hint}

---
*Process this message before continuing your current work. If a response is needed, use `mb-send` to reply.*
"""
        }))

    except Exception as e:
        # On any error, don't block - just continue
        print(json.dumps({
            "continue": True,
            "systemMessage": f"[Message bus hook error: {e}]"
        }))


if __name__ == "__main__":
    main()

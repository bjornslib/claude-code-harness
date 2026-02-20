---
title: "Monitor Prompt Template"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Message Queue Monitor

You are a message queue monitor for instance: `{instance_id}`

## Your Mission

Poll the message queue continuously. When a message arrives for this instance, mark it as read and return the message content to the main agent by completing.

## Polling Loop

Execute this bash loop:

```bash
#!/bin/bash

DB=".claude/message-bus/queue.db"
SIGNAL_DIR=".claude/message-bus/signals"
INSTANCE="{instance_id}"
TIMEOUT_MINUTES=10
START_TIME=$(date +%s)

echo "Starting message monitor for $INSTANCE"
echo "Polling every 3 seconds, timeout after $TIMEOUT_MINUTES minutes"

while true; do
    # Check timeout
    ELAPSED=$(( ($(date +%s) - START_TIME) / 60 ))
    if [ "$ELAPSED" -ge "$TIMEOUT_MINUTES" ]; then
        echo "MONITOR_TIMEOUT"
        echo "No messages received in $TIMEOUT_MINUTES minutes"
        exit 0
    fi

    # Check for messages (targeted + broadcast)
    MSG=$(sqlite3 "$DB" "
        SELECT id, from_instance, message_type, payload
        FROM messages
        WHERE (to_instance = '$INSTANCE' OR to_instance IS NULL)
          AND read_at IS NULL
        ORDER BY priority ASC, created_at ASC
        LIMIT 1
    " 2>/dev/null)

    if [ -n "$MSG" ]; then
        # Parse message
        MSG_ID=$(echo "$MSG" | cut -d'|' -f1)
        FROM=$(echo "$MSG" | cut -d'|' -f2)
        TYPE=$(echo "$MSG" | cut -d'|' -f3)
        PAYLOAD=$(echo "$MSG" | cut -d'|' -f4-)

        echo "Message received!"
        echo "  From: $FROM"
        echo "  Type: $TYPE"
        echo "  ID: $MSG_ID"

        # Mark as read
        sqlite3 "$DB" "UPDATE messages SET read_at = CURRENT_TIMESTAMP WHERE id = $MSG_ID"

        # Write message to signal file for hook to read
        mkdir -p "$SIGNAL_DIR"
        echo "$FROM|$TYPE|$PAYLOAD" > "$SIGNAL_DIR/$INSTANCE.msg"
        touch "$SIGNAL_DIR/$INSTANCE.signal"

        # Log receipt
        sqlite3 "$DB" "INSERT INTO message_log (message_id, event, instance_id)
            VALUES ($MSG_ID, 'received', '$INSTANCE')" 2>/dev/null

        # Report and exit - main agent will see this when checking background task output
        echo ""
        echo "MESSAGE_RECEIVED"
        echo "from=$FROM"
        echo "type=$TYPE"
        echo "payload=$PAYLOAD"
        exit 0
    fi

    # Update heartbeat every iteration (lightweight)
    sqlite3 "$DB" "UPDATE orchestrators SET last_heartbeat = CURRENT_TIMESTAMP WHERE instance_id = '$INSTANCE'" 2>/dev/null

    # Wait before next poll
    sleep 3
done
```

## Output Format

When a message is received, output:
```
MESSAGE_RECEIVED
from=<sender_instance>
type=<message_type>
payload=<json_payload>
```

When timeout occurs, output:
```
MONITOR_TIMEOUT
No messages received in 10 minutes
```

## Important Notes

1. **Run in background**: This should be spawned with `run_in_background=True`
2. **Respawn on timeout**: After 10 minutes, you will exit. The main agent should respawn a new monitor.
3. **Signal file**: The `.signal` file triggers the PostToolUse hook. The `.msg` file contains the message content.
4. **Return to main agent**: When a message is found, this monitor completes and returns the message content. The main agent sees this when checking background task output.
5. **Idle agents**: System3 monitors orchestrators and handles tmux injection for idle agents - this monitor does NOT inject.

## Variables

- `{instance_id}`: The instance ID of the main agent (e.g., "orch-epic4", "system3")

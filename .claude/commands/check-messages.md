---
title: "Check Messages"
status: active
type: command
last_verified: 2026-02-19
grade: reference
---

# Check Message Bus

Check for incoming messages from the inter-instance message bus.

## What This Does

1. Queries the SQLite message queue for messages addressed to this instance
2. Also checks for broadcast messages (addressed to all)
3. Marks retrieved messages as read
4. Clears any pending signal files

## Execute

```bash
# Get instance ID (use session ID or default)
INSTANCE="${CLAUDE_SESSION_ID:-default}"

# Check for messages
.claude/scripts/message-bus/mb-recv --instance="$INSTANCE"
```

## After Receiving Messages

If you receive messages, process them appropriately:

- **guidance**: Adjust your approach based on System 3's input
- **urgent**: Handle immediately before continuing other work
- **query**: Send a response using `mb-send`
- **completion**: Acknowledge if needed

## Responding to Messages

```bash
# Send a response
.claude/scripts/message-bus/mb-send "<sender>" "response" '{
    "subject": "Acknowledged",
    "body": "Message received and processed",
    "context": {"original_type": "<original_type>"}
}'
```

## Troubleshooting

If no messages but you expected some:
```bash
# Check message bus status
.claude/scripts/message-bus/mb-status

# Peek without marking as read
.claude/scripts/message-bus/mb-recv --peek
```

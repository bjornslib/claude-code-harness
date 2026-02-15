# User Input Queue — Fallback Communication Channel

Fallback mechanism for S3 Communicator-to-User communication when Google Chat MCP (Epic 2) is unavailable.

## How It Works

1. **Communicator writes a question**: Creates `pending-{timestamp}.md` in this directory
2. **User reads and responds**: Creates `response-{timestamp}.md` with their answer
3. **Communicator polls**: On each heartbeat cycle (every 600s), checks for new response files
4. **Relay to Operator**: Communicator sends the response to System 3 Operator via SendMessage

## File Naming Convention

| File Pattern | Created By | Purpose |
|-------------|-----------|---------|
| `pending-{ISO-timestamp}.md` | S3 Communicator | Question awaiting user response |
| `response-{ISO-timestamp}.md` | User (manually) | User's answer to a pending question |

Timestamp format: `YYYY-MM-DDTHHMMSS` (e.g., `pending-2026-02-15T143000.md`)

## Pending Question Format

See `EXAMPLE-pending.md` for the full template. Required sections:
- **From**: Always `s3-communicator`
- **Timestamp**: ISO-8601 with timezone
- **Question ID**: Matches the filename
- **Question**: The question text
- **Options**: 2-4 labeled choices (A, B, C, D)
- **Context**: Background information for the user
- **How to Respond**: Instructions for creating the response file

## Response Format

See `EXAMPLE-response.md` for the full template. Required sections:
- **From**: Always `User`
- **Timestamp**: When the user responded
- **Question ID**: Must match the pending question's ID
- **Answer**: The user's choice and any elaboration
- **Additional Context**: Optional extra information

## Lifecycle

```
Communicator creates pending-*.md
    → User sees file, creates response-*.md
    → Next heartbeat: Communicator finds response
    → Communicator relays to Operator via SendMessage
    → Both files can be archived or deleted
```

## Notes

- This is the FALLBACK channel. When Google Chat MCP (Epic 2) is available, questions go through Google Chat instead.
- Files in this directory are NOT committed to git (add to .gitignore if needed).
- The Communicator only polls on active heartbeat cycles (8 AM - 10 PM by default).

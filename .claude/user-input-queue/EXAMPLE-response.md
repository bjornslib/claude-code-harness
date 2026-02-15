# Response

**From**: User
**Timestamp**: 2026-02-15T14:45:00+11:00
**Question ID**: pending-2026-02-15T143000

## Answer

C — Both approaches. Use JWT for API access from agents and session cookies for the web UI.

## Additional Context

Make sure JWT tokens have a 24-hour expiry. Use httpOnly cookies for sessions.

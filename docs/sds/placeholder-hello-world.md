---
title: "Hello World Guardian Test SD"
description: "Minimal SD for testing guardian pipeline dispatch"
version: "1.0.0"
last-updated: 2026-03-21
status: active
type: sd
---

# SD: Hello World Guardian Test

## Task
Write the text "Hello from Guardian Pipeline!" to `/tmp/guardian-hello-world.txt`.

## Implementation
Use a simple shell command: `echo 'Hello from Guardian Pipeline!' > /tmp/guardian-hello-world.txt`

## Acceptance Criteria
- File `/tmp/guardian-hello-world.txt` exists
- File contains exactly "Hello from Guardian Pipeline!"

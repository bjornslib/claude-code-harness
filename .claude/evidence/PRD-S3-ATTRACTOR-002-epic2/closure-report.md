---
title: "Epic 2 Closure Report — Channel Bridge + GChat Adapter"
prd: PRD-S3-ATTRACTOR-002
epic: "Epic 2: Channel Bridge + GChat Adapter"
date: 2026-02-24
status: impl_complete
agent: worker-epic2
---

# Epic 2 Closure Report: Channel Bridge + GChat Adapter

## Files Created

| File | Size | Status |
|------|------|--------|
| `.claude/scripts/attractor/gchat_adapter.py` | ~8 KB | ✓ Created |
| `.claude/scripts/attractor/channel_bridge.py` | ~9 KB | ✓ Created |
| `.claude/scripts/attractor/tests/__init__.py` | 0 bytes | ✓ Created |
| `.claude/scripts/attractor/tests/conftest.py` | ~300 bytes | ✓ Created |
| `.claude/scripts/attractor/tests/test_gchat_adapter.py` | ~11 KB | ✓ Created |
| `.claude/scripts/attractor/tests/test_channel_bridge.py` | ~14 KB | ✓ Created |

## Test Results

```
============================= 108 passed in 0.32s ==============================

GChatAdapter:
  TestParseInbound       11 tests — all PASSED
  TestVerifyWebhook      10 tests — all PASSED
  TestFormatCard         13 tests — all PASSED
  TestSendOutbound        9 tests — all PASSED
  TestHelpers            10 tests — all PASSED

ChannelBridge:
  TestRegistry            7 tests — all PASSED
  TestHandleInbound      14 tests — all PASSED
  TestBroadcastSignal    12 tests — all PASSED
  TestSendToChannel       3 tests — all PASSED
  TestTranslateInbound   13 tests — all PASSED
  TestFormatSignalAsOutbound  8 tests — all PASSED
```

## Architecture

### GChatAdapter (`gchat_adapter.py`)

Implements the `channel_adapter.ChannelAdapter` ABC:

| Method | Behavior |
|--------|----------|
| `parse_inbound(raw_payload)` | Parses Google Chat MESSAGE/ADDED_TO_SPACE events. Strips bot @mention prefixes. Extracts space name, thread ID, sender. |
| `send_outbound(message, recipient)` | POSTs to webhook URL via `httpx.AsyncClient`. Supports `cardsV2` (rich cards) and plain text. Appends `messageReplyOption` for thread replies. |
| `verify_webhook(request)` | Bearer token (Authorization header) or body token comparison via `hmac.compare_digest` (timing-safe). No-op if token not configured. |
| `format_card(pipeline_status)` | Formats `RunnerPlan`-compatible dict as Google Chat Card v2 with header, status, actions, blocked nodes, and completed node count. |

### ChannelBridge (`channel_bridge.py`)

Routes between external channels (GChat) and the internal pipeline runner:

| Method | Behavior |
|--------|----------|
| `register_channel(name, adapter, recipient)` | Add a channel adapter to the registry. |
| `handle_inbound(channel, raw_payload)` | verify → parse → translate → forward to runner via `send_signal("INBOUND_COMMAND")` |
| `broadcast_signal(signal, payload, pipeline_status)` | Format runner signal as OutboundMessage, send to ALL channels concurrently via `asyncio.gather`. |
| `send_to_channel(channel, message, recipient)` | Send to a specific channel (one-to-one). |

#### Command Mapping (inbound text → runner message_type)

| User Text | message_type |
|-----------|-------------|
| `approve [node_id]` | `approval` |
| `reject [node_id] [reason]` | `override` |
| `stop` / `halt` / `shutdown` | `shutdown` |
| `status` / `help` / `pause` / `resume` | `guidance` |
| *(anything else)* | `guidance` |

#### Signal Formatting (runner signal → card included)

| Signal | Card Included |
|--------|---------------|
| `RUNNER_COMPLETE` | Yes (pipeline_status) |
| `RUNNER_STUCK` | Yes (pipeline_status) |
| `AWAITING_APPROVAL` | Yes (pipeline_status) |
| All others | No |

## Design Decisions

1. **`httpx` for async HTTP** — `GChatAdapter.send_outbound` uses `httpx.AsyncClient` as specified.
2. **`hmac.compare_digest` for token verification** — timing-safe comparison prevents timing attacks.
3. **`asyncio.gather` for broadcast** — all channels receive signals concurrently; individual failures are captured, not propagated.
4. **Thread affinity via `messageReplyOption`** — threaded replies use Google Chat's `REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD` parameter.
5. **Separate ABCs** — `channel_adapter.py` (external user comms) vs `adapters/base.py` (internal runner signaling) remain separate as designed.
6. **Card format: inner card only** — `format_card()` returns the inner `card` dict; callers wrap in `cardsV2[].card`. This matches the existing `CardBuilder` pattern in `formatter.py`.
7. **Runner forwarding via `send_signal("INBOUND_COMMAND")`** — uses the existing runner adapter interface without requiring new methods.

## Integration Points

- `GChatAdapter` → `channel_adapter.ChannelAdapter` (external user comms ABC)
- `ChannelBridge._runner_adapter` → `adapters.base.ChannelAdapter` (internal runner ABC)
- `ChannelBridge.broadcast_signal` → triggers `GChatAdapter.format_card()` for card-warranting signals
- `ChannelBridge.handle_inbound` → `runner_adapter.send_signal("INBOUND_COMMAND")` → runner picks up via `receive_message()`

## Next Steps

- Epic 3: Guard Rails expansion (evidence timestamping, spot-check sampling)
- Epic 4: FastAPI webhook server to receive GChat events (wraps GChatAdapter.parse_inbound)
- Epic 5: System 3 integration (`attractor run` CLI subcommand)

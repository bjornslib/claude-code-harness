# PRD-VCHAT-001: Chat & Voice Agent Experience Fixes

**Status**: Draft v1
**Date**: 2026-03-14
**Related**: PRD-G15-UNIFIED-LK-ENTRYPOINT, SD-G16-FORM-STATE-SYNC

---

## 1. Problem Statement

Four issues degrade the chat-mode employment verification experience:

| # | Issue | User Impact |
|---|-------|-------------|
| P1 | Agent doesn't know whether the person was employed — FORM FIELD SNAPSHOT text says "Yes" without naming the candidate or company | LLM overlooks employment confirmation; re-asks the employment gate question |
| P2 | Chat agent asks questions in wrong order and out of sync with form state | Verifier sees form fields in one order but agent asks about different fields; confusing UX |
| P3 | Listener (form filler) agent has no knowledge of the current date | Relative date expressions ("last month", "two years ago") cannot be resolved |
| P4 | Chat agent responds when verifier confirms employment gate, but stays silent for all other field updates | Inconsistent behaviour — agent should only speak when there's a discrepancy to discuss |

### Root Causes

- **P1**: `EMPLOYMENT_GATE` handler and snapshot text use generic phrasing ("the candidate was employed") without interpolating `candidate_name` or `company_name`.
- **P2**: Voice agent gets form state baked into its `instructions` at construction time (via `field_snapshot` parameter). Chat agent does NOT — the `mode == "voice"` gate on line 1219 of `verification_agents.py` excludes chat mode entirely. Chat agent only receives one-off `[SYSTEM:...]` injections on discrepancy events, giving it no persistent view of form state.
- **P3**: Neither the form filler agent's system prompt nor the listener service's user message include the current date.
- **P4**: The `EMPLOYMENT_GATE confirmed` handler calls `generate_reply()`, causing the agent to proactively say "Begin verifying individual fields starting with start date." No other field confirmation triggers a response (correct behaviour), creating an inconsistency.

---

## 2. Goals

1. Chat agent has persistent, up-to-date form state context on every LLM turn.
2. Chat agent only generates a reply when a discrepancy requires verifier attention.
3. Employment gate text explicitly names candidate and company.
4. Listener agent can resolve relative date expressions using current date.

### Non-Goals

- Changing the voice agent's existing form event handling (it works correctly).
- Changing the frontend event emission logic (it correctly fires only on discrepancy transitions).
- Adding new event types to the data channel protocol.

---

## 3. User Stories

**US-1** (Verifier): When I confirm employment and fill in fields that match, the chat agent stays silent and lets me work through the form at my own pace.

**US-2** (Verifier): When I enter a value that differs from the candidate's claim, the chat agent immediately notices the discrepancy, names the specific field, and asks me to confirm.

**US-3** (Verifier): When the chat agent mentions employment status, it clearly states the candidate's name and company — not just "the candidate."

**US-4** (System): The listener agent resolves "he left last month" to the correct absolute date using today's date.

---

## 4. Acceptance Criteria

### AC-1: Persistent Form State in Chat Mode
- When VerificationAgent is constructed with `mode="chat"` and a non-empty `field_snapshot`, the form state section MUST appear in the agent's instructions.
- The `mode == "voice"` gate in `verification_agents.py` line 1219 MUST be removed (or changed to include chat).

### AC-2: Agent Rebuild on Discrepancy
- When a `FORM_STATE_SNAPSHOT` event with `trigger="discrepancy"` is received in chat mode, the handler MUST:
  1. Store the updated snapshot in `session.userdata["field_snapshot"]`.
  2. Construct a new `VerificationAgent` with the updated `field_snapshot`, preserving `session.chat_ctx`.
  3. Call `session.update_agent()` to swap to the rebuilt agent.
  4. Call `session.generate_reply()` with a focused discrepancy instruction.

### AC-3: Silent Employment Gate Confirmation
- When `EMPLOYMENT_GATE` event with `value != "denied"` is received, the handler MUST NOT call `session.generate_reply()`.
- The employment gate status MUST still be stored in `session.userdata["employment_gate_status"]`.
- When `EMPLOYMENT_GATE` event with `value == "denied"`, `generate_reply()` MAY still be called (denial is an exceptional case requiring agent response).

### AC-4: Explicit Employment Text
- All system messages and snapshot text that reference employment confirmation MUST include `{candidate_name}` and `{company_name}`.
- Example: "Confirmed that **Jane Doe** was employed at **Acme Corp**" — not "the candidate was employed."

### AC-5: Current Date in Listener
- The form filler agent's user message MUST include the current date in a clearly labelled field.
- The form filler agent's system prompt MUST include instructions for using the current date to resolve relative expressions.

---

## 5. Epics

| Epic | Title | Scope |
|------|-------|-------|
| E1 | Chat Agent Form State Persistence | AC-1, AC-2: Remove mode gate, implement agent rebuild on snapshot |
| E2 | Silent Confirmations & Explicit Text | AC-3, AC-4: Remove employment gate reply, add candidate/company to text |
| E3 | Listener Date Awareness | AC-5: Add current date to listener agent context |

---

## 6. Out of Scope

- Changing the `ChatWelcomeAgent` → `VerificationAgent` handoff (it already works correctly).
- Modifying the frontend's `buildSnapshot()` or `FormEventEmitter` components.
- Adding new data channel event types.
- Voice mode changes (voice already has the correct pattern).

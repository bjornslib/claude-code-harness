---
title: "SD: BubbleLens Epic 2 - Chrome Extension Feed Capture"
description: "Technical design for Manifest V3 Chrome extension that captures YouTube homepage recommendations"
version: "1.0.0"
last-updated: 2026-03-26
status: draft
type: sd
grade: authoritative
---

# SD-BUBBLELENS-001-Epic2: Chrome Extension - Feed Capture

**Parent PRD**: PRD-BUBBLELENS-P1-001 (Epic 2)
**Epic**: Chrome Extension - Feed Capture
**Worker Type**: `frontend-dev-expert`

## Overview

A Manifest V3 Chrome extension that injects into YouTube pages, parses the homepage video recommendation grid, and sends structured feed data to the BubbleLens API. The extension handles DOM changes gracefully with fallback selectors, supports offline capture with sync, and requires BubbleLens authentication.

## Architecture

```
extension/
├── manifest.json               # Manifest V3 config
├── src/
│   ├── content/
│   │   ├── parser.ts           # DOM parsing logic (selectors, extraction)
│   │   └── content-script.ts   # Injected into youtube.com pages
│   ├── background/
│   │   └── service-worker.ts   # Background sync, message routing, alarm scheduling
│   ├── popup/
│   │   ├── popup.html          # Popup UI markup
│   │   ├── popup.ts            # Popup logic (capture trigger, status display)
│   │   └── popup.css           # Popup styling
│   ├── lib/
│   │   ├── api-client.ts       # BubbleLens API communication
│   │   ├── storage.ts          # chrome.storage wrapper for offline queue
│   │   ├── auth.ts             # Authentication state management
│   │   └── types.ts            # Shared TypeScript types
│   └── assets/
│       ├── icon-16.png
│       ├── icon-48.png
│       └── icon-128.png
├── tsconfig.json
├── webpack.config.js           # Build config for extension
└── package.json
```

## Component Design

### Manifest V3 Configuration

```json
{
  "manifest_version": 3,
  "name": "BubbleLens",
  "version": "1.0.0",
  "description": "See through your YouTube filter bubble",
  "permissions": ["storage", "alarms", "activeTab"],
  "host_permissions": ["https://www.youtube.com/*"],
  "background": {
    "service_worker": "background/service-worker.js",
    "type": "module"
  },
  "content_scripts": [{
    "matches": ["https://www.youtube.com/*"],
    "js": ["content/content-script.js"],
    "run_at": "document_idle"
  }],
  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": {
      "16": "assets/icon-16.png",
      "48": "assets/icon-48.png",
      "128": "assets/icon-128.png"
    }
  }
}
```

### DOM Parser (`parser.ts`)

The parser extracts video data from YouTube's homepage grid. YouTube uses Web Components with specific tag names.

**Primary selectors** (current YouTube DOM as of March 2026):
```typescript
interface VideoData {
  videoId: string;
  title: string;
  channelName: string;
  thumbnailUrl: string;
  position: number;
}

interface SelectorConfig {
  container: string;        // Parent element containing all video items
  item: string;             // Individual video card
  videoLink: string;        // <a> element with /watch?v= href
  title: string;            // Video title element
  channelName: string;      // Channel name element
  thumbnail: string;        // Thumbnail <img> element
}

const PRIMARY_SELECTORS: SelectorConfig = {
  container: 'ytd-rich-grid-renderer',
  item: 'ytd-rich-item-renderer',
  videoLink: 'a#video-title-link',
  title: '#video-title',
  channelName: '#channel-name a',
  thumbnail: 'ytd-thumbnail img',
};

const FALLBACK_SELECTORS: SelectorConfig = {
  container: '#contents',
  item: 'ytd-rich-item-renderer, ytd-video-renderer',
  videoLink: 'a[href*="/watch?v="]',
  title: 'a[href*="/watch?v="] #video-title, a[href*="/watch?v="] .title',
  channelName: '.ytd-channel-name a, #channel-name',
  thumbnail: 'img[src*="i.ytimg.com"]',
};
```

**Extraction logic**:
1. Wait for `ytd-rich-grid-renderer` to be present in DOM (MutationObserver, timeout 10s)
2. Query all `ytd-rich-item-renderer` elements
3. For each item, extract video ID from href (`/watch?v=VIDEO_ID`), title text, channel name text, thumbnail src
4. If primary selectors fail (0 results), retry with fallback selectors
5. Return array of `VideoData` sorted by DOM position

**Video ID extraction**:
```typescript
function extractVideoId(href: string): string | null {
  const match = href.match(/[?&]v=([a-zA-Z0-9_-]{11})/);
  return match ? match[1] : null;
}
```

### Content Script (`content-script.ts`)

- Injected at `document_idle` on youtube.com
- Listens for messages from popup/service-worker via `chrome.runtime.onMessage`
- Message types:
  - `CAPTURE_FEED`: Trigger feed capture, respond with `VideoData[]`
  - `PING`: Health check, respond with `{ status: 'ready' }`

### Service Worker (`service-worker.ts`)

- Routes messages between popup and content script
- Manages offline queue sync via `chrome.alarms`
- Handles auth token refresh

### Popup UI

- **Ready state**: "Capture Feed" button, last capture timestamp, video count from last capture
- **Capturing state**: Loading spinner, "Capturing..." text
- **Success state**: Green checkmark, "Captured X videos", timestamp, link to dashboard
- **Error state**: Red indicator, error message, "Retry" button
- **Not on YouTube state**: "Navigate to youtube.com to capture your feed"

### Offline Storage & Sync

```typescript
interface PendingCapture {
  id: string;
  feedData: VideoData[];
  capturedAt: string;
  feedType: 'homepage';
  retryCount: number;
}

// Store pending captures
async function queueCapture(capture: PendingCapture): Promise<void> {
  const pending = await chrome.storage.local.get('pendingCaptures');
  const queue: PendingCapture[] = pending.pendingCaptures || [];
  queue.push(capture);
  await chrome.storage.local.set({ pendingCaptures: queue });
}

// Sync pending captures (called on alarm and on connectivity restore)
async function syncPendingCaptures(): Promise<void> {
  const pending = await chrome.storage.local.get('pendingCaptures');
  const queue: PendingCapture[] = pending.pendingCaptures || [];
  const remaining: PendingCapture[] = [];

  for (const capture of queue) {
    try {
      await apiClient.submitFeed(capture);
    } catch {
      if (capture.retryCount < 5) {
        capture.retryCount++;
        remaining.push(capture);
      }
      // Drop after 5 retries
    }
  }

  await chrome.storage.local.set({ pendingCaptures: remaining });
}
```

### Anonymous Identity (`identity.ts`)

No authentication for the PoC. The extension generates a persistent anonymous browser UUID:

```typescript
// src/lib/identity.ts
async function getBrowserId(): Promise<string> {
  const stored = await chrome.storage.local.get('browserId');
  if (stored.browserId) return stored.browserId;

  const browserId = crypto.randomUUID();
  await chrome.storage.local.set({ browserId });
  return browserId;
}
```

- Generated on first extension install
- Persists across browser sessions via `chrome.storage.local`
- Included in every API request as `browserId` field in the JSON payload
- No PII collected, no auth tokens, no login required

## Data Model

No new database tables. Extension sends data conforming to the `POST /api/feeds` request schema defined in Epic 4.

**Request payload**:
```typescript
interface FeedCapturePayload {
  browserId: string; // Anonymous UUID generated on first install
  feedType: 'homepage' | 'up_next' | 'search';
  capturedAt: string; // ISO 8601
  videos: Array<{
    videoId: string;
    title: string;
    channelName: string;
    thumbnailUrl: string;
    position: number;
  }>;
}
```

## API Design

Extension is an API consumer only. It calls:
- `POST /api/feeds` (Epic 3) — submit captured feed with anonymous browserId

## Task Breakdown

| Task | Description | File Scope | Worker Type | Dependencies |
|------|-------------|-----------|-------------|-------------|
| T2.1 | Extension project setup | `extension/manifest.json`, `extension/package.json`, `extension/webpack.config.js`, `extension/tsconfig.json` | frontend-dev-expert | T1.1 |
| T2.2 | DOM parser with primary + fallback selectors | `extension/src/content/parser.ts` | frontend-dev-expert | T2.1 |
| T2.3 | Popup UI (capture button, status display) | `extension/src/popup/*` | frontend-dev-expert | T2.1 |
| T2.4 | Message passing (popup <-> content script <-> service worker) | `extension/src/content/content-script.ts`, `extension/src/background/service-worker.ts` | frontend-dev-expert | T2.2, T2.3 |
| T2.5 | Anonymous browser UUID generation + persistence | `extension/src/lib/identity.ts` | frontend-dev-expert | T2.1 |
| T2.6 | Offline capture storage | `extension/src/lib/storage.ts` | frontend-dev-expert | T2.4 |
| T2.7 | Sync mechanism with retry | `extension/src/background/service-worker.ts`, `extension/src/lib/api-client.ts` | frontend-dev-expert | T2.6 |
| T2.8 | Build + package for Chrome Web Store | `extension/webpack.config.js`, build scripts | frontend-dev-expert | T2.1-T2.7 |

## Testing Strategy

- **Unit tests**: DOM parser with mocked YouTube HTML fixtures (current + variant DOMs)
- **Unit tests**: Video ID extraction regex edge cases
- **Unit tests**: Offline queue management (add, sync, retry, drop)
- **Integration tests**: Message passing between components (content script <-> popup <-> service worker)
- **Manual test**: Load unpacked extension on real YouTube page, verify capture

## Implementation Status

| Task | Status | Last Updated |
|------|--------|-------------|
| T2.1 | Not Started | 2026-03-26 |
| T2.2 | Not Started | 2026-03-26 |
| T2.3 | Not Started | 2026-03-26 |
| T2.4 | Not Started | 2026-03-26 |
| T2.5 | Not Started | 2026-03-26 |
| T2.6 | Not Started | 2026-03-26 |
| T2.7 | Not Started | 2026-03-26 |
| T2.8 | Not Started | 2026-03-26 |

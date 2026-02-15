#!/usr/bin/env python3
"""
F3.5: Session Transcript Indexing Script for Hindsight.

Indexes past Claude Code session transcripts into Hindsight long-term memory,
enabling queries like "What did I do last Tuesday?" or "How did we solve the
auth bug?"

Design:
  - Reads JSONL transcript files from ~/.claude/projects/{project}/
  - Filters: only main session transcripts (agentName == ""), not workers
  - Chunks text into ~400 tokens (~1600 chars) with ~80 token overlap (~320 chars)
  - POSTs chunks to Hindsight retain API (async=true)
  - Tracks indexed sessions to avoid re-indexing (state file)
  - Python stdlib only (no pip dependencies)

Usage:
  # Index all un-indexed sessions for the current project
  python3 .claude/scripts/hindsight-transcript-indexer.py

  # Index a specific project
  python3 .claude/scripts/hindsight-transcript-indexer.py --project <project-slug>

  # Force re-index all sessions
  python3 .claude/scripts/hindsight-transcript-indexer.py --force

  # Dry run (show what would be indexed)
  python3 .claude/scripts/hindsight-transcript-indexer.py --dry-run

  # Limit to N most recent sessions
  python3 .claude/scripts/hindsight-transcript-indexer.py --limit 5

Implements F3.5 from PRD-S3-CLAWS-001 (Epic 3: Enhanced Hindsight Integration).
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# -- Configuration -----------------------------------------------------------

HINDSIGHT_BASE_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
SHARED_BANK = os.environ.get("HINDSIGHT_SHARED_BANK", "claude-harness-setup")
API_TIMEOUT = 15

# Token estimation: 1 token ~ 4 chars (per OpenClaw pattern)
CHUNK_SIZE_CHARS = 1600   # ~400 tokens
OVERLAP_CHARS = 320       # ~80 tokens

# Batch size for retain API calls (avoid huge payloads)
RETAIN_BATCH_SIZE = 10

# Claude Code projects directory
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


# -- Logging -----------------------------------------------------------------

def _log(state_dir: Path, message: str, *, verbose: bool = False) -> None:
    """Append a timestamped line to the debug log."""
    try:
        log_file = state_dir / "transcript-indexer.log"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass
    if verbose:
        print(f"  {message}", file=sys.stderr)


# -- Hindsight API -----------------------------------------------------------

def _check_health() -> bool:
    """Check if Hindsight is reachable and healthy."""
    try:
        req = Request(f"{HINDSIGHT_BASE_URL}/health")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("status") == "healthy"
    except Exception:
        return False


def _retain(bank_id: str, items: list[dict], state_dir: Path) -> bool:
    """POST items to Hindsight retain endpoint. Returns True on success."""
    url = f"{HINDSIGHT_BASE_URL}/v1/default/banks/{bank_id}/memories"
    payload = json.dumps({"items": items, "async": True}).encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=API_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            success = body.get("success", False)
            _log(state_dir, f"retain({bank_id}): {len(items)} items, success={success}")
            return success
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        _log(state_dir, f"retain({bank_id}) FAILED: {exc}")
        return False


# -- State tracking ----------------------------------------------------------

def _load_indexed_state(state_dir: Path) -> dict:
    """Load the set of already-indexed session files and their hashes."""
    state_file = state_dir / "indexed-sessions.json"
    if state_file.exists():
        try:
            with open(state_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"indexed": {}, "last_run": None}


def _save_indexed_state(state_dir: Path, state: dict) -> None:
    """Persist the indexed state."""
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "indexed-sessions.json"
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def _file_hash(filepath: Path) -> str:
    """Compute a quick hash of file size + mtime for change detection."""
    stat = filepath.stat()
    raw = f"{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# -- Transcript parsing ------------------------------------------------------

def _detect_project_slug() -> str:
    """Detect the project slug from CWD, matching Claude Code's convention."""
    cwd = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    # Claude Code uses path with / replaced by - and leading -
    slug = cwd.replace("/", "-")
    return slug


def _find_project_dir(project_slug: str | None) -> Path | None:
    """Find the project directory in ~/.claude/projects/."""
    if not CLAUDE_PROJECTS_DIR.exists():
        return None

    if project_slug:
        # Direct match
        candidate = CLAUDE_PROJECTS_DIR / project_slug
        if candidate.exists():
            return candidate
        # Try with leading dash
        candidate = CLAUDE_PROJECTS_DIR / f"-{project_slug}"
        if candidate.exists():
            return candidate
        # Partial match
        for d in CLAUDE_PROJECTS_DIR.iterdir():
            if d.is_dir() and project_slug in d.name:
                return d
        return None

    # Auto-detect from CWD
    slug = _detect_project_slug()
    for d in CLAUDE_PROJECTS_DIR.iterdir():
        if d.is_dir() and d.name == slug:
            return d
    return None


def _is_main_session(filepath: Path) -> bool:
    """Check if a JSONL transcript is a main session (not a worker).

    Main sessions have agentName='' on their first conversation message.
    Worker sessions have agentName='worker-xxx'.
    """
    try:
        with open(filepath) as f:
            for line in f:
                obj = json.loads(line)
                msg_type = obj.get("type", "")
                if msg_type in ("user", "assistant"):
                    agent_name = obj.get("agentName", "")
                    return agent_name == ""
    except (json.JSONDecodeError, OSError):
        pass
    return False


def _extract_transcript_text(filepath: Path) -> tuple[str, dict]:
    """Extract human-readable text from a JSONL transcript.

    Returns (full_text, metadata) where metadata includes session info.
    """
    messages: list[str] = []
    metadata: dict = {
        "session_id": "",
        "git_branch": "",
        "first_timestamp": "",
        "last_timestamp": "",
    }
    first_ts = None
    last_ts = None

    with open(filepath) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type", "")
            timestamp = obj.get("timestamp", "")

            # Track timestamps
            if timestamp:
                if first_ts is None:
                    first_ts = timestamp
                last_ts = timestamp

            # Capture metadata from first conversational message
            if msg_type in ("user", "assistant") and not metadata["session_id"]:
                metadata["session_id"] = obj.get("sessionId", filepath.stem)
                metadata["git_branch"] = obj.get("gitBranch", "")

            # Extract text content from user and assistant messages
            if msg_type not in ("user", "assistant"):
                continue

            msg = obj.get("message", {})
            content = msg.get("content", "")
            role = msg.get("role", msg_type)

            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                # Content blocks: extract text blocks
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                text = "\n".join(text_parts)

            # Skip empty, system-reminder-only, or hook messages
            text = text.strip()
            if not text:
                continue
            if text.startswith("<system-reminder>") and text.endswith("</system-reminder>"):
                continue
            if text.startswith("<local-command"):
                continue

            # Add role prefix for context
            prefix = "User" if role == "user" else "Assistant"
            messages.append(f"[{prefix}]: {text}")

    metadata["first_timestamp"] = first_ts or ""
    metadata["last_timestamp"] = last_ts or ""

    return "\n\n".join(messages), metadata


# -- Chunking ----------------------------------------------------------------

def _chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE_CHARS,
    overlap: int = OVERLAP_CHARS,
) -> list[str]:
    """Split text into overlapping chunks.

    Uses sentence boundaries when possible to avoid mid-sentence splits.
    Falls back to character boundary if no sentence break is found.

    The stride (advance per step) is chunk_size - overlap. Each chunk is
    approximately chunk_size chars, with overlap chars shared between
    consecutive chunks.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    stride = chunk_size - overlap
    if stride <= 0:
        stride = chunk_size // 2  # Safeguard

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # If not at the end of text, try to break at a sentence boundary
        if end < text_len:
            # Look for sentence endings within the last 20% of the chunk
            search_start = start + int(chunk_size * 0.8)
            best_break = -1
            for sep in ("\n\n", "\n", ". ", "? ", "! "):
                idx = text.rfind(sep, search_start, end)
                if idx > best_break:
                    best_break = idx + len(sep)

            if best_break > search_start:
                end = best_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # If we reached the end of text, we're done
        if end >= text_len:
            break

        # Advance by stride, but never less than 1
        start += max(stride, 1)

    return chunks


# -- Main indexing logic -----------------------------------------------------

def _build_memory_items(
    chunks: list[str],
    metadata: dict,
    filepath: Path,
) -> list[dict]:
    """Build Hindsight memory items from transcript chunks."""
    session_id = metadata.get("session_id", filepath.stem)
    branch = metadata.get("git_branch", "unknown")
    first_ts = metadata.get("first_timestamp", "")
    last_ts = metadata.get("last_timestamp", "")
    now_iso = datetime.now(timezone.utc).isoformat()

    items: list[dict] = []
    total_chunks = len(chunks)

    for i, chunk in enumerate(chunks):
        # Estimate token count
        est_tokens = len(chunk) // 4

        doc_id = f"transcript-{session_id}-chunk-{i:04d}"

        item = {
            "content": chunk,
            "context": "session-transcript",
            "document_id": doc_id,
            "timestamp": first_ts or now_iso,
            "metadata": {
                "source": "transcript-indexer",
                "session_id": session_id,
                "git_branch": branch,
                "chunk_index": str(i),
                "total_chunks": str(total_chunks),
                "est_tokens": str(est_tokens),
                "session_start": first_ts,
                "session_end": last_ts,
                "indexed_at": now_iso,
            },
        }
        items.append(item)

    return items


def index_session(
    filepath: Path,
    state_dir: Path,
    *,
    bank_id: str = SHARED_BANK,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Index a single session transcript. Returns stats dict."""
    stats = {"file": filepath.name, "chunks": 0, "retained": 0, "skipped": False}

    # Extract text
    text, metadata = _extract_transcript_text(filepath)
    if not text.strip():
        _log(state_dir, f"Skipped {filepath.name}: no meaningful text", verbose=verbose)
        stats["skipped"] = True
        return stats

    # Chunk
    chunks = _chunk_text(text)
    stats["chunks"] = len(chunks)
    stats["total_chars"] = len(text)
    stats["est_tokens"] = len(text) // 4
    stats["session_id"] = metadata.get("session_id", "")

    if verbose:
        print(
            f"  Session {filepath.stem[:12]}...: "
            f"{len(text)} chars (~{len(text)//4} tokens) -> {len(chunks)} chunks",
            file=sys.stderr,
        )

    if dry_run:
        return stats

    # Build memory items
    items = _build_memory_items(chunks, metadata, filepath)

    # Retain in batches
    retained = 0
    for batch_start in range(0, len(items), RETAIN_BATCH_SIZE):
        batch = items[batch_start : batch_start + RETAIN_BATCH_SIZE]
        if _retain(bank_id, batch, state_dir):
            retained += len(batch)
        else:
            _log(state_dir, f"Batch retain failed at offset {batch_start}")

    stats["retained"] = retained
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index Claude Code session transcripts into Hindsight",
    )
    parser.add_argument(
        "--project",
        help="Project slug (auto-detected from CWD if omitted)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-index all sessions (ignore previous indexing state)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be indexed without making API calls",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit to N most recent sessions (0 = all)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print progress to stderr",
    )
    parser.add_argument(
        "--bank",
        default=SHARED_BANK,
        help=f"Hindsight bank ID (default: {SHARED_BANK})",
    )
    args = parser.parse_args()

    # Use specified bank (or default)
    bank_id = args.bank

    # State directory
    project_dir = os.environ.get(
        "CLAUDE_PROJECT_DIR",
        os.getcwd(),
    )
    state_dir = Path(project_dir) / ".claude" / "state" / "transcript-indexer"

    # Find project directory
    proj_dir = _find_project_dir(args.project)
    if proj_dir is None:
        auto_slug = _detect_project_slug()
        print(
            f"ERROR: Could not find project directory. "
            f"Auto-detected slug: {auto_slug}",
            file=sys.stderr,
        )
        print(
            f"Available projects: {[d.name for d in CLAUDE_PROJECTS_DIR.iterdir() if d.is_dir()][:10]}",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.verbose:
        print(f"Project dir: {proj_dir}", file=sys.stderr)

    # Check Hindsight health (skip in dry-run)
    if not args.dry_run:
        if not _check_health():
            print(
                "ERROR: Hindsight is not reachable or not healthy at "
                f"{HINDSIGHT_BASE_URL}",
                file=sys.stderr,
            )
            sys.exit(1)
        if args.verbose:
            print("Hindsight: healthy", file=sys.stderr)

    # Load indexed state
    state = _load_indexed_state(state_dir)
    indexed = state.get("indexed", {})

    # Find JSONL transcript files
    transcript_files: list[Path] = sorted(
        proj_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,  # Most recent first
    )

    if args.verbose:
        print(f"Found {len(transcript_files)} transcript files", file=sys.stderr)

    # Filter: main sessions only
    main_sessions: list[Path] = []
    for tf in transcript_files:
        if _is_main_session(tf):
            main_sessions.append(tf)
        elif args.verbose:
            print(f"  Skipping worker session: {tf.name[:20]}...", file=sys.stderr)

    if args.verbose:
        print(f"Main sessions: {len(main_sessions)}", file=sys.stderr)

    # Apply limit
    if args.limit > 0:
        main_sessions = main_sessions[: args.limit]

    # Filter: not already indexed (unless --force)
    to_index: list[Path] = []
    for tf in main_sessions:
        fhash = _file_hash(tf)
        key = tf.name
        if not args.force and key in indexed and indexed[key] == fhash:
            if args.verbose:
                print(f"  Already indexed: {tf.name[:20]}...", file=sys.stderr)
            continue
        to_index.append(tf)

    if not to_index:
        print("Nothing to index. All sessions are up to date.")
        return

    print(f"Indexing {len(to_index)} session(s)...")

    # Index each session
    total_stats = {
        "sessions": 0,
        "chunks": 0,
        "retained": 0,
        "errors": 0,
    }

    for tf in to_index:
        try:
            stats = index_session(
                tf,
                state_dir,
                bank_id=bank_id,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )

            if stats.get("skipped"):
                continue

            total_stats["sessions"] += 1
            total_stats["chunks"] += stats.get("chunks", 0)
            total_stats["retained"] += stats.get("retained", 0)

            # Update state (even in dry-run, just don't persist)
            if not args.dry_run:
                indexed[tf.name] = _file_hash(tf)

        except Exception as exc:
            total_stats["errors"] += 1
            _log(state_dir, f"ERROR indexing {tf.name}: {exc}", verbose=args.verbose)

    # Save state
    if not args.dry_run:
        state["indexed"] = indexed
        _save_indexed_state(state_dir, state)

    # Summary
    mode = "[DRY RUN] " if args.dry_run else ""
    print(
        f"\n{mode}Indexing complete:\n"
        f"  Sessions indexed: {total_stats['sessions']}\n"
        f"  Chunks created:   {total_stats['chunks']}\n"
        f"  Chunks retained:  {total_stats['retained']}\n"
        f"  Errors:           {total_stats['errors']}"
    )

    # Output JSON summary for programmatic use
    summary = {
        "status": "success" if total_stats["errors"] == 0 else "partial",
        "mode": "dry_run" if args.dry_run else "live",
        "project": proj_dir.name,
        "bank": bank_id,
        **total_stats,
    }
    _log(state_dir, f"Run complete: {json.dumps(summary)}")


if __name__ == "__main__":
    main()

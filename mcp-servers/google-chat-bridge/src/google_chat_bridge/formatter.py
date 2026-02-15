"""Outbound message formatting for Google Chat.

Provides structured message templates, Google Chat Card v2 builders,
markdown conversion, and enhanced chunking with continuation markers
for System 3 notifications.

Message Types:
    - Progress updates (orchestrator status)
    - Task completion cards
    - Beads change notifications
    - Daily briefings (morning / end-of-day)
    - Blocked work alerts
    - Option questions (user input requests)

Google Chat Formatting Reference:
    - Bold: *text*
    - Italic: _text_
    - Strikethrough: ~text~
    - Monospace: `text`
    - Code block: ```text```
    - Links: <url|text>
    - Newlines: \\n
    - Max message length: 4096 characters
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_MESSAGE_LENGTH = 4096
# Reserve space for continuation marker like " [2/5]"
CONTINUATION_RESERVE = 10


class MessageType(str, Enum):
    """Types of outbound messages for template selection."""

    PROGRESS = "progress"
    TASK_STATUS = "task_status"
    BEADS_CHANGE = "beads_change"
    DAILY_BRIEFING = "daily_briefing"
    BLOCKED_ALERT = "blocked_alert"
    OPTION_QUESTION = "option_question"
    HEARTBEAT_FINDING = "heartbeat_finding"
    GENERIC = "generic"


class CardSection(BaseModel):
    """A section in a Google Chat Card v2."""

    header: str = ""
    widgets: list[dict[str, Any]] = Field(default_factory=list)


class CardBuilder:
    """Builder for Google Chat Cards v2 format.

    Google Chat Cards v2 provide rich formatting with headers, sections,
    decorated text, buttons, and dividers.

    Usage:
        card = (
            CardBuilder("Task Complete")
            .subtitle("beads-abc123")
            .section("Summary", [
                CardBuilder.text_widget("All tests passed"),
                CardBuilder.kv_widget("Duration", "2m 30s"),
            ])
            .section("Details", [
                CardBuilder.text_widget("```\\ntest output here\\n```"),
            ])
            .build()
        )
    """

    def __init__(self, title: str, card_id: str = "") -> None:
        self._title = title
        self._subtitle = ""
        self._image_url = ""
        self._card_id = card_id or f"card-{id(self)}"
        self._sections: list[CardSection] = []

    def subtitle(self, text: str) -> CardBuilder:
        """Set the card subtitle."""
        self._subtitle = text
        return self

    def image(self, url: str) -> CardBuilder:
        """Set the card header image URL."""
        self._image_url = url
        return self

    def section(
        self,
        header: str = "",
        widgets: list[dict[str, Any]] | None = None,
    ) -> CardBuilder:
        """Add a section to the card."""
        self._sections.append(
            CardSection(header=header, widgets=widgets or [])
        )
        return self

    def build(self) -> dict[str, Any]:
        """Build the Google Chat Cards v2 payload.

        Returns:
            Dict suitable for the `cardsV2` field of a Google Chat message.
        """
        header: dict[str, Any] = {"title": self._title}
        if self._subtitle:
            header["subtitle"] = self._subtitle
        if self._image_url:
            header["imageUrl"] = self._image_url
            header["imageType"] = "CIRCLE"

        sections = []
        for sec in self._sections:
            section: dict[str, Any] = {}
            if sec.header:
                section["header"] = sec.header
            if sec.widgets:
                section["widgets"] = sec.widgets
            sections.append(section)

        return {
            "cardsV2": [
                {
                    "cardId": self._card_id,
                    "card": {
                        "header": header,
                        "sections": sections,
                    },
                }
            ]
        }

    # -----------------------------------------------------------------------
    # Widget factory methods
    # -----------------------------------------------------------------------

    @staticmethod
    def text_widget(text: str) -> dict[str, Any]:
        """Create a text paragraph widget."""
        return {"textParagraph": {"text": text}}

    @staticmethod
    def kv_widget(
        label: str,
        value: str,
        icon: str = "",
        bottom_label: str = "",
    ) -> dict[str, Any]:
        """Create a key-value (decorated text) widget.

        Args:
            label: Top label (small text).
            value: Main text content.
            icon: Optional known icon name (e.g., "STAR", "CLOCK", "DESCRIPTION").
            bottom_label: Optional bottom label text.
        """
        widget: dict[str, Any] = {
            "decoratedText": {
                "topLabel": label,
                "text": value,
            }
        }
        if icon:
            widget["decoratedText"]["startIcon"] = {"knownIcon": icon}
        if bottom_label:
            widget["decoratedText"]["bottomLabel"] = bottom_label
        return widget

    @staticmethod
    def divider_widget() -> dict[str, Any]:
        """Create a horizontal divider widget."""
        return {"divider": {}}

    @staticmethod
    def button_list_widget(buttons: list[dict[str, str]]) -> dict[str, Any]:
        """Create a button list widget.

        Args:
            buttons: List of dicts with 'text' and 'url' keys.
        """
        return {
            "buttonList": {
                "buttons": [
                    {
                        "text": btn["text"],
                        "onClick": {"openLink": {"url": btn["url"]}},
                    }
                    for btn in buttons
                ]
            }
        }

    @staticmethod
    def columns_widget(
        items: list[tuple[str, str]],
    ) -> dict[str, Any]:
        """Create a columns widget with label-value pairs.

        Args:
            items: List of (label, value) tuples displayed as two columns.
        """
        return {
            "columns": {
                "columnItems": [
                    {
                        "horizontalSizeStyle": "FILL_AVAILABLE_SPACE",
                        "horizontalAlignment": "START",
                        "verticalAlignment": "CENTER",
                        "widgets": [
                            {"textParagraph": {"text": f"*{label}*"}},
                            {"textParagraph": {"text": value}},
                        ],
                    }
                    for label, value in items
                ]
            }
        }


# ---------------------------------------------------------------------------
# Markdown conversion
# ---------------------------------------------------------------------------


def markdown_to_gchat(text: str) -> str:
    """Convert standard Markdown to Google Chat markdown subset.

    Google Chat supports a limited markdown set:
    - *bold* (not **bold**)
    - _italic_ (not *italic*)
    - ~strikethrough~
    - `inline code`
    - ```code blocks```
    - <url|link text>

    This function converts common Markdown patterns to Google Chat format.
    """
    # Protect code blocks from other transformations
    code_blocks: list[str] = []

    def save_code_block(match: re.Match) -> str:
        code_blocks.append(match.group(0))
        return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

    text = re.sub(r"```[\s\S]*?```", save_code_block, text)

    # Protect inline code
    inline_codes: list[str] = []

    def save_inline_code(match: re.Match) -> str:
        inline_codes.append(match.group(0))
        return f"__INLINE_CODE_{len(inline_codes) - 1}__"

    text = re.sub(r"`[^`]+`", save_inline_code, text)

    # Convert **bold** to *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)

    # Convert [text](url) to <url|text>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)

    # Convert ### headers to *bold* with newline
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)

    # Convert --- or === horizontal rules to divider text
    text = re.sub(r"^[-=]{3,}$", "---", text, flags=re.MULTILINE)

    # Convert bullet points (- item) to unicode bullet
    text = re.sub(r"^[-*]\s+", "\u2022 ", text, flags=re.MULTILINE)

    # Restore code blocks and inline code
    for i, block in enumerate(code_blocks):
        text = text.replace(f"__CODE_BLOCK_{i}__", block)
    for i, code in enumerate(inline_codes):
        text = text.replace(f"__INLINE_CODE_{i}__", code)

    return text


# ---------------------------------------------------------------------------
# Enhanced chunking with continuation markers
# ---------------------------------------------------------------------------


def chunk_with_continuation(
    text: str,
    max_length: int = MAX_MESSAGE_LENGTH,
) -> list[str]:
    """Split text into chunks with continuation markers.

    Unlike basic chunking, this adds [1/N] markers at the end of each chunk
    so the reader knows the message continues.

    Args:
        text: The text to chunk.
        max_length: Maximum length per chunk (default: 4096).

    Returns:
        List of chunks with continuation markers appended.
    """
    if len(text) <= max_length:
        return [text]

    # Estimate number of chunks needed
    effective_max = max_length - CONTINUATION_RESERVE
    raw_chunks = _split_at_boundaries(text, effective_max)
    total = len(raw_chunks)

    # Add continuation markers
    result = []
    for i, chunk in enumerate(raw_chunks, 1):
        if total > 1:
            marker = f" [{i}/{total}]"
            result.append(chunk.rstrip() + marker)
        else:
            result.append(chunk)

    return result


def _split_at_boundaries(text: str, max_length: int) -> list[str]:
    """Split text at natural boundaries (newlines, spaces)."""
    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        split_at = max_length

        # Try to split at a double newline (paragraph boundary)
        double_nl = remaining[:split_at].rfind("\n\n")
        if double_nl > max_length // 3:
            split_at = double_nl + 2
        else:
            # Try single newline
            nl_pos = remaining[:split_at].rfind("\n")
            if nl_pos > max_length // 2:
                split_at = nl_pos + 1
            else:
                # Try space
                space_pos = remaining[:split_at].rfind(" ")
                if space_pos > max_length // 2:
                    split_at = space_pos + 1

        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]

    return chunks


# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------


def format_progress_update(
    orchestrator_name: str,
    status: str,
    tasks_completed: int = 0,
    tasks_total: int = 0,
    current_task: str = "",
    elapsed_time: str = "",
    details: str = "",
) -> str:
    """Format an orchestrator progress update message.

    Args:
        orchestrator_name: Name of the orchestrator session.
        status: Current status (e.g., "running", "idle", "completed", "error").
        tasks_completed: Number of tasks completed.
        tasks_total: Total number of tasks.
        current_task: Description of the current task being worked on.
        elapsed_time: Time elapsed since session start.
        details: Optional additional details.

    Returns:
        Formatted Google Chat markdown text.
    """
    status_indicators = {
        "running": ">>>",
        "idle": "...",
        "completed": "+++",
        "error": "---",
        "blocked": "***",
    }
    indicator = status_indicators.get(status, "???")

    parts = [f"{indicator} *Orchestrator: {orchestrator_name}* — {status.upper()}"]

    if tasks_total > 0:
        progress_pct = int(tasks_completed / tasks_total * 100) if tasks_total else 0
        bar_filled = progress_pct // 10
        bar_empty = 10 - bar_filled
        progress_bar = "\u2588" * bar_filled + "\u2591" * bar_empty
        parts.append(f"`{progress_bar}` {tasks_completed}/{tasks_total} ({progress_pct}%)")

    if current_task:
        parts.append(f"Current: _{current_task}_")

    if elapsed_time:
        parts.append(f"Elapsed: {elapsed_time}")

    if details:
        parts.append(f"\n{details}")

    return "\n".join(parts)


def format_beads_change(
    changes: list[dict[str, str]],
    summary: str = "",
) -> str:
    """Format a beads change notification.

    Args:
        changes: List of dicts with 'id', 'title', 'old_status', 'new_status'.
        summary: Optional summary line.

    Returns:
        Formatted Google Chat markdown text.
    """
    parts = ["*Beads Status Changes*"]

    if summary:
        parts.append(summary)

    parts.append("")
    for change in changes:
        bead_id = change.get("id", "?")
        title = change.get("title", "Untitled")
        old = change.get("old_status", "?")
        new = change.get("new_status", "?")
        parts.append(f"\u2022 `{bead_id}`: {title} ({old} \u2192 {new})")

    return "\n".join(parts)


def format_daily_briefing(
    briefing_type: str,
    date: str = "",
    beads_summary: str = "",
    orchestrator_summary: str = "",
    git_summary: str = "",
    priorities: list[str] | None = None,
    accomplishments: list[str] | None = None,
    blockers: list[str] | None = None,
    metrics: dict[str, str] | None = None,
) -> str:
    """Format a daily briefing (morning or end-of-day).

    Args:
        briefing_type: "morning" or "eod" (end of day).
        date: Date string (defaults to today).
        beads_summary: Summary of beads status.
        orchestrator_summary: Summary of orchestrator sessions.
        git_summary: Summary of git activity.
        priorities: List of priority items for the day.
        accomplishments: List of accomplishments (EOD only).
        blockers: List of blockers or issues.
        metrics: Dict of metric name -> value.

    Returns:
        Formatted Google Chat markdown text.
    """
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if briefing_type == "morning":
        title = f"*Morning Briefing* — {date}"
        greeting = "Here's what needs attention today:"
    else:
        title = f"*End-of-Day Summary* — {date}"
        greeting = "Here's what happened today:"

    parts = [title, greeting, ""]

    if beads_summary:
        parts.extend(["*Beads*", beads_summary, ""])

    if orchestrator_summary:
        parts.extend(["*Orchestrators*", orchestrator_summary, ""])

    if git_summary:
        parts.extend(["*Git Activity*", git_summary, ""])

    if priorities:
        parts.append("*Priorities*")
        for i, p in enumerate(priorities, 1):
            parts.append(f"{i}. {p}")
        parts.append("")

    if accomplishments:
        parts.append("*Accomplishments*")
        for a in accomplishments:
            parts.append(f"\u2022 {a}")
        parts.append("")

    if blockers:
        parts.append("*Blockers*")
        for b in blockers:
            parts.append(f"\u26a0 {b}")
        parts.append("")

    if metrics:
        parts.append("*Metrics*")
        for name, value in metrics.items():
            parts.append(f"\u2022 {name}: {value}")

    return "\n".join(parts)


def format_blocked_alert(
    task_title: str,
    task_id: str = "",
    blocker_description: str = "",
    options: list[str] | None = None,
    urgency: str = "medium",
) -> str:
    """Format a blocked work alert requesting user input.

    Args:
        task_title: Title of the blocked task.
        task_id: Optional task/bead ID.
        blocker_description: Description of what is blocking progress.
        options: Optional list of options for the user to choose from.
        urgency: "low", "medium", "high", or "critical".

    Returns:
        Formatted Google Chat markdown text.
    """
    urgency_markers = {
        "critical": "!!!",
        "high": "!! ",
        "medium": "!  ",
        "low": ".  ",
    }
    marker = urgency_markers.get(urgency, "!  ")

    parts = [f"{marker} *BLOCKED*: {task_title}"]

    if task_id:
        parts.append(f"ID: `{task_id}`")

    if blocker_description:
        parts.append(f"\n{blocker_description}")

    if options:
        parts.append("\n*Options:*")
        for i, opt in enumerate(options, 1):
            parts.append(f"  {i}. {opt}")
        parts.append("\n_Reply with option number or your own suggestion._")

    return "\n".join(parts)


def format_option_question(
    question: str,
    options: list[str],
    context: str = "",
    rationale: str = "",
) -> str:
    """Format an option question for user input via Google Chat.

    Args:
        question: The question to ask.
        options: List of option descriptions (2-4 options).
        context: Optional context about why this question is being asked.
        rationale: Optional rationale for the recommended option.

    Returns:
        Formatted Google Chat markdown text.
    """
    parts = [f"*Question:* {question}"]

    if context:
        parts.append(f"\n_{context}_")

    parts.append("")
    for i, opt in enumerate(options, 1):
        parts.append(f"  *{i}.* {opt}")

    if rationale:
        parts.append(f"\n_Recommendation: {rationale}_")

    parts.append("\n_Reply with the option number (1-{}) or type your own answer._".format(
        len(options)
    ))

    return "\n".join(parts)


def format_heartbeat_finding(
    finding_type: str,
    summary: str,
    details: str = "",
    action_needed: bool = True,
) -> str:
    """Format a heartbeat finding notification.

    Args:
        finding_type: Type of finding (e.g., "beads_ready", "git_changes",
                      "orchestrator_stuck", "pr_review").
        summary: Brief summary of the finding.
        details: Optional details.
        action_needed: Whether user action is required.

    Returns:
        Formatted Google Chat markdown text.
    """
    type_icons = {
        "beads_ready": ">>>",
        "git_changes": "~~~",
        "orchestrator_stuck": "***",
        "pr_review": "???",
        "orchestrator_complete": "+++",
        "error": "---",
    }
    icon = type_icons.get(finding_type, ">>>")

    parts = [f"{icon} *Heartbeat: {finding_type.replace('_', ' ').title()}*"]
    parts.append(summary)

    if details:
        parts.append(f"\n{details}")

    if action_needed:
        parts.append("\n_Action needed — reply to acknowledge or provide direction._")
    else:
        parts.append("\n_For information only — no action needed._")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Card template builders
# ---------------------------------------------------------------------------


def build_task_card(
    task_title: str,
    task_id: str = "",
    status: str = "completed",
    summary: str = "",
    details: str = "",
    metrics: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a Google Chat Card v2 for a task status update.

    Returns:
        Dict with cardsV2 payload ready for the Google Chat API.
    """
    status_labels = {
        "completed": "COMPLETED",
        "failed": "FAILED",
        "blocked": "BLOCKED",
        "in_progress": "IN PROGRESS",
    }

    builder = CardBuilder(task_title, card_id=f"task-{task_id or 'unknown'}")
    builder.subtitle(f"{status_labels.get(status, status.upper())} | {task_id}" if task_id else status_labels.get(status, status.upper()))

    # Summary section
    widgets: list[dict[str, Any]] = []
    if summary:
        widgets.append(CardBuilder.text_widget(summary))

    if metrics:
        for name, value in metrics.items():
            widgets.append(CardBuilder.kv_widget(name, value))

    if widgets:
        builder.section("Summary", widgets)

    # Details section
    if details:
        builder.section("Details", [
            CardBuilder.text_widget(f"```\n{details}\n```"),
        ])

    return builder.build()


def build_briefing_card(
    briefing_type: str,
    date: str = "",
    sections_data: dict[str, list[str]] | None = None,
    metrics: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a Google Chat Card v2 for a daily briefing.

    Args:
        briefing_type: "morning" or "eod".
        date: Date string.
        sections_data: Dict mapping section names to list of items.
        metrics: Optional metrics dict.

    Returns:
        Dict with cardsV2 payload.
    """
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    title = "Morning Briefing" if briefing_type == "morning" else "End-of-Day Summary"
    builder = CardBuilder(title, card_id=f"briefing-{briefing_type}-{date}")
    builder.subtitle(date)

    if sections_data:
        for section_name, items in sections_data.items():
            widgets = [CardBuilder.text_widget(item) for item in items]
            builder.section(section_name, widgets)

    if metrics:
        metric_widgets = [
            CardBuilder.kv_widget(name, value)
            for name, value in metrics.items()
        ]
        builder.section("Metrics", metric_widgets)

    return builder.build()

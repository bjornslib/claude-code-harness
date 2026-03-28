package tui

import (
	"fmt"
	"strings"

	"github.com/bjornslib/pipeline-watcher/dot"
	"github.com/charmbracelet/lipgloss"
)

const (
	colIDWidth      = 28
	colHandlerWidth = 18
	colStatusWidth  = 16
	colDurWidth     = 10
	colWorkerWidth  = 20
)

// RenderTable renders the node status table as a plain string for embedding
// inside a lipgloss border.
func RenderTable(nodes []dot.Node, durations map[string]string, width int) string {
	var sb strings.Builder

	// Header row
	header := fmt.Sprintf("%-*s %-*s %-*s %-*s %-*s",
		colIDWidth, "NODE ID",
		colHandlerWidth, "HANDLER",
		colStatusWidth, "STATUS",
		colDurWidth, "DURATION",
		colWorkerWidth, "WORKER",
	)
	sb.WriteString(columnHeaderStyle.Render(header))
	sb.WriteString("\n")
	sb.WriteString(dimStyle.Render(strings.Repeat("─", min(width-4, 100))))
	sb.WriteString("\n")

	for _, n := range nodes {
		status := n.EffectiveStatus()
		dur := "-"
		if d, ok := durations[n.ID]; ok {
			dur = d
		}

		idField := truncate(n.ID, colIDWidth)
		handlerField := truncate(n.Handler, colHandlerWidth)
		durField := truncate(dur, colDurWidth)
		workerField := truncate(n.WorkerType, colWorkerWidth)

		statusField := StyleForStatus(status).Render(truncate(status, colStatusWidth))

		row := fmt.Sprintf("%-*s %-*s %-*s %-*s %-*s",
			colIDWidth, idField,
			colHandlerWidth, handlerField,
			colStatusWidth, lipgloss.NewStyle().Render(""), // spacer; status rendered separately
			colDurWidth, durField,
			colWorkerWidth, workerField,
		)

		// Re-render with proper status colouring by replacing the spacer section.
		// Simpler approach: build row manually.
		row = fmt.Sprintf("%s %s %s %s %s",
			padRight(idField, colIDWidth),
			padRight(handlerField, colHandlerWidth),
			padRight(statusField, colStatusWidth+10), // +10 for ANSI escape codes
			padRight(durField, colDurWidth),
			padRight(workerField, colWorkerWidth),
		)

		sb.WriteString(row)
		sb.WriteString("\n")
	}

	return sb.String()
}

// SummaryLine builds the "pending: N | active: N | ..." summary footer.
func SummaryLine(nodes []dot.Node) string {
	counts := map[string]int{
		"pending":       0,
		"active":        0,
		"impl_complete": 0,
		"validated":     0,
		"failed":        0,
		"accepted":      0,
	}
	for _, n := range nodes {
		s := n.EffectiveStatus()
		if _, ok := counts[s]; ok {
			counts[s]++
		}
	}

	parts := []string{
		StyleForStatus("pending").Render(fmt.Sprintf("pending:%d", counts["pending"])),
		StyleForStatus("active").Render(fmt.Sprintf("active:%d", counts["active"])),
		StyleForStatus("impl_complete").Render(fmt.Sprintf("impl_complete:%d", counts["impl_complete"])),
		StyleForStatus("validated").Render(fmt.Sprintf("validated:%d", counts["validated"])),
		StyleForStatus("failed").Render(fmt.Sprintf("failed:%d", counts["failed"])),
		StyleForStatus("accepted").Render(fmt.Sprintf("accepted:%d", counts["accepted"])),
	}
	return strings.Join(parts, dimStyle.Render("  |  "))
}

func truncate(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max-1] + "…"
}

func padRight(s string, width int) string {
	// lipgloss strips ANSI codes for width calc, so we use raw spaces.
	// For ANSI-containing strings this is approximate — good enough for terminal display.
	visible := lipgloss.Width(s)
	if visible >= width {
		return s
	}
	return s + strings.Repeat(" ", width-visible)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

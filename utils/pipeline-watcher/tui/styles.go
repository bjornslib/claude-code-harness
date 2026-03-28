package tui

import "github.com/charmbracelet/lipgloss"

// Status color palette — maps canonical status strings to styled renderers.
var (
	statusStyles = map[string]lipgloss.Style{
		"pending":       lipgloss.NewStyle().Foreground(lipgloss.Color("240")),
		"active":        lipgloss.NewStyle().Foreground(lipgloss.Color("39")).Bold(true),
		"impl_complete": lipgloss.NewStyle().Foreground(lipgloss.Color("220")),
		"validated":     lipgloss.NewStyle().Foreground(lipgloss.Color("82")),
		"failed":        lipgloss.NewStyle().Foreground(lipgloss.Color("196")).Bold(true),
		"accepted":      lipgloss.NewStyle().Foreground(lipgloss.Color("46")).Bold(true),
	}

	titleStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("86")).
			Padding(0, 1)

	headerStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("255")).
			Background(lipgloss.Color("235")).
			Padding(0, 1)

	helpStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("241"))

	errorStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("196"))

	normalStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("252"))

	dimStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("240"))

	columnHeaderStyle = lipgloss.NewStyle().
				Bold(true).
				Foreground(lipgloss.Color("33")).
				Underline(true)

	logBorderStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("62")).
			Padding(0, 1)

	tableBorderStyle = lipgloss.NewStyle().
				Border(lipgloss.RoundedBorder()).
				BorderForeground(lipgloss.Color("62")).
				Padding(0, 1)
)

// StyleForStatus returns the lipgloss style for a given status string.
// Falls back to normalStyle for unknown statuses.
func StyleForStatus(status string) lipgloss.Style {
	if s, ok := statusStyles[status]; ok {
		return s
	}
	return normalStyle
}

// StatusDot returns a coloured bullet representing the status.
func StatusDot(status string) string {
	dots := map[string]string{
		"pending":       "○",
		"active":        "◉",
		"impl_complete": "◑",
		"validated":     "●",
		"failed":        "✗",
		"accepted":      "✓",
	}
	dot := "·"
	if d, ok := dots[status]; ok {
		dot = d
	}
	return StyleForStatus(status).Render(dot)
}

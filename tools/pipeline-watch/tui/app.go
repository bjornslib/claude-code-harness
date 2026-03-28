package tui

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/bjornslib/pipeline-watch/pipeline"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// ── Styles ─────────────────────────────────────────────────────────────────

var (
	titleStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("86")).
			Padding(0, 1)

	selectedStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("212")).
			Bold(true)

	normalStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("252"))

	runningBadge = lipgloss.NewStyle().
			Foreground(lipgloss.Color("46")).
			SetString("●")

	completedBadge = lipgloss.NewStyle().
			Foreground(lipgloss.Color("34")).
			SetString("✓")

	failedBadge = lipgloss.NewStyle().
			Foreground(lipgloss.Color("196")).
			SetString("✗")

	unknownBadge = lipgloss.NewStyle().
			Foreground(lipgloss.Color("240")).
			SetString("○")

	eventBorderStyle = lipgloss.NewStyle().
				Border(lipgloss.RoundedBorder()).
				BorderForeground(lipgloss.Color("62")).
				Padding(0, 1)

	listBorderStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("62")).
			Padding(0, 1)

	helpStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("241"))

	// Event type colors
	eventGreen   = lipgloss.NewStyle().Foreground(lipgloss.Color("34"))
	eventRed     = lipgloss.NewStyle().Foreground(lipgloss.Color("196"))
	eventYellow  = lipgloss.NewStyle().Foreground(lipgloss.Color("214"))
	eventCyan    = lipgloss.NewStyle().Foreground(lipgloss.Color("81"))
	eventDim     = lipgloss.NewStyle().Foreground(lipgloss.Color("240"))
	eventBlue    = lipgloss.NewStyle().Foreground(lipgloss.Color("69"))
	eventWhite   = lipgloss.NewStyle().Foreground(lipgloss.Color("252"))
	eventMagenta = lipgloss.NewStyle().Foreground(lipgloss.Color("170"))
)

func eventStyle(eventType string) lipgloss.Style {
	switch {
	case strings.HasSuffix(eventType, ".completed"):
		return eventGreen
	case strings.HasSuffix(eventType, ".failed"):
		return eventRed
	case strings.Contains(eventType, "retry") || strings.Contains(eventType, "loop"):
		return eventYellow
	case strings.HasSuffix(eventType, ".started"):
		return eventCyan
	case strings.Contains(eventType, "checkpoint") || strings.Contains(eventType, "context"):
		return eventDim
	case eventType == "agent.message":
		return eventWhite
	case eventType == "agent.tool_call":
		return eventBlue
	case eventType == "agent.thinking" || eventType == "agent.tool_result":
		return eventDim
	case strings.HasPrefix(eventType, "validation"):
		return eventMagenta
	default:
		return normalStyle
	}
}

// ── Messages ───────────────────────────────────────────────────────────────

type pipelinesLoadedMsg struct{ pipelines []pipeline.Pipeline }
type eventsLoadedMsg struct{ events []pipeline.Event }
type newEventsMsg struct {
	events []pipeline.Event
	offset int64
}
type errMsg struct{ err error }
type tickMsg time.Time

// ── Model ──────────────────────────────────────────────────────────────────

type viewMode int

const (
	modeList viewMode = iota
	modeEvents
)

// Model is the Bubble Tea model.
type Model struct {
	root       string
	pipelines  []pipeline.Pipeline
	cursor     int
	events     []pipeline.Event
	eventScroll int
	tailOffset int64
	mode       viewMode
	filter     string // event type filter
	err        error
	width      int
	height     int
}

// New creates an initialised Model.
func New(root string) Model {
	return Model{
		root: root,
	}
}

// Init kicks off the initial pipeline discovery.
func (m Model) Init() tea.Cmd {
	return tea.Batch(m.loadPipelines(), tickCmd())
}

// ── Update ─────────────────────────────────────────────────────────────────

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {

	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil

	case pipelinesLoadedMsg:
		m.pipelines = msg.pipelines
		m.err = nil
		if m.cursor >= len(m.pipelines) {
			m.cursor = max(0, len(m.pipelines)-1)
		}
		return m, nil

	case eventsLoadedMsg:
		m.events = msg.events
		m.eventScroll = max(0, len(m.events)-m.visibleEventLines())
		// Set tail offset to end of file
		if len(m.pipelines) > m.cursor {
			info, err := fileSize(m.pipelines[m.cursor].JSONLPath)
			if err == nil {
				m.tailOffset = info
			}
		}
		return m, nil

	case newEventsMsg:
		m.events = append(m.events, msg.events...)
		m.tailOffset = msg.offset
		// Auto-scroll to bottom if we were at the bottom
		maxScroll := max(0, len(m.events)-m.visibleEventLines())
		if m.eventScroll >= maxScroll-len(msg.events) {
			m.eventScroll = maxScroll
		}
		return m, nil

	case errMsg:
		m.err = msg.err
		return m, nil

	case tickMsg:
		var cmds []tea.Cmd
		cmds = append(cmds, tickCmd())
		if m.mode == modeList {
			cmds = append(cmds, m.loadPipelines())
		} else if m.mode == modeEvents && len(m.pipelines) > m.cursor {
			cmds = append(cmds, m.tailEvents())
		}
		return m, tea.Batch(cmds...)

	case tea.KeyMsg:
		return m.handleKey(msg)
	}

	return m, nil
}

func (m Model) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "q", "ctrl+c":
		return m, tea.Quit

	case "esc":
		if m.mode == modeEvents {
			m.mode = modeList
			m.events = nil
			m.eventScroll = 0
			return m, m.loadPipelines()
		}
		return m, tea.Quit

	case "up", "k":
		if m.mode == modeList {
			if m.cursor > 0 {
				m.cursor--
			}
		} else {
			if m.eventScroll > 0 {
				m.eventScroll--
			}
		}
		return m, nil

	case "down", "j":
		if m.mode == modeList {
			if m.cursor < len(m.pipelines)-1 {
				m.cursor++
			}
		} else {
			maxScroll := max(0, len(m.events)-m.visibleEventLines())
			if m.eventScroll < maxScroll {
				m.eventScroll++
			}
		}
		return m, nil

	case "enter":
		if m.mode == modeList && len(m.pipelines) > 0 {
			m.mode = modeEvents
			m.eventScroll = 0
			m.tailOffset = 0
			return m, m.loadEvents()
		}

	case "G":
		// Jump to bottom
		if m.mode == modeEvents {
			m.eventScroll = max(0, len(m.events)-m.visibleEventLines())
		}

	case "g":
		// Jump to top
		if m.mode == modeEvents {
			m.eventScroll = 0
		}

	case "a":
		// Toggle agent-only filter
		if m.mode == modeEvents {
			if m.filter == "agent" {
				m.filter = ""
			} else {
				m.filter = "agent"
			}
			m.eventScroll = max(0, len(m.filteredEvents())-m.visibleEventLines())
		}

	case "n":
		// Toggle node-only filter
		if m.mode == modeEvents {
			if m.filter == "node" {
				m.filter = ""
			} else {
				m.filter = "node"
			}
			m.eventScroll = max(0, len(m.filteredEvents())-m.visibleEventLines())
		}

	case "f":
		// Cycle through filters: all -> agent -> node -> pipeline -> all
		if m.mode == modeEvents {
			switch m.filter {
			case "":
				m.filter = "agent"
			case "agent":
				m.filter = "node"
			case "node":
				m.filter = "pipeline"
			default:
				m.filter = ""
			}
			m.eventScroll = max(0, len(m.filteredEvents())-m.visibleEventLines())
		}

	case "r":
		if m.mode == modeList {
			return m, m.loadPipelines()
		}
	}

	return m, nil
}

// ── View ───────────────────────────────────────────────────────────────────

func (m Model) View() string {
	if m.width == 0 {
		return "Loading…\n"
	}

	if m.mode == modeEvents {
		return m.viewEvents()
	}
	return m.viewList()
}

func (m Model) viewList() string {
	header := titleStyle.Render(fmt.Sprintf("pipeline-watch  %d pipeline(s)", len(m.pipelines)))

	if len(m.pipelines) == 0 {
		body := listBorderStyle.Width(m.width - 4).Render(
			normalStyle.Render("No pipelines found.\nExpected in .pipelines/pipelines/ or .claude/attractor/pipelines/"),
		)
		footer := helpStyle.Render("[r] refresh  [q] quit")
		return lipgloss.JoinVertical(lipgloss.Left, header, body, footer)
	}

	var sb strings.Builder
	for i, p := range m.pipelines {
		badge := unknownBadge.String()
		switch p.Status {
		case "running":
			badge = runningBadge.String()
		case "completed":
			badge = completedBadge.String()
		case "failed":
			badge = failedBadge.String()
		}

		age := formatAge(p.LastEvent)
		label := fmt.Sprintf("%s %-30s  %3d events  %d nodes  %s  %s",
			badge, truncate(p.ID, 30), p.EventCount, p.NodeCount, p.Status, age)

		if i == m.cursor {
			sb.WriteString(selectedStyle.Render("▶ "+label) + "\n")
		} else {
			sb.WriteString(normalStyle.Render("  "+label) + "\n")
		}
	}

	body := listBorderStyle.Width(m.width - 4).Render(sb.String())
	footer := helpStyle.Render("[↑↓/jk] navigate  [enter] view events  [r] refresh  [q] quit")

	return lipgloss.JoinVertical(lipgloss.Left, header, body, footer)
}

func (m Model) viewEvents() string {
	p := m.pipelines[m.cursor]
	filterLabel := "all"
	if m.filter != "" {
		filterLabel = m.filter + ".*"
	}
	header := titleStyle.Render(fmt.Sprintf("pipeline-watch  %s  [filter: %s]  %d events",
		p.ID, filterLabel, len(m.filteredEvents())))

	events := m.filteredEvents()
	visible := m.visibleEventLines()

	start := m.eventScroll
	if start > len(events) {
		start = len(events)
	}
	end := start + visible
	if end > len(events) {
		end = len(events)
	}

	var sb strings.Builder
	for _, ev := range events[start:end] {
		line := pipeline.FormatEvent(ev)
		style := eventStyle(ev.Type)
		sb.WriteString(style.Render(line) + "\n")
	}

	body := eventBorderStyle.Width(m.width - 4).Height(visible).Render(sb.String())

	// Scroll indicator
	scrollInfo := ""
	if len(events) > visible {
		pct := 0
		if len(events)-visible > 0 {
			pct = m.eventScroll * 100 / (len(events) - visible)
		}
		scrollInfo = fmt.Sprintf("  [%d/%d  %d%%]", start+1, len(events), pct)
	}

	footer := helpStyle.Render(fmt.Sprintf(
		"[↑↓/jk] scroll  [g/G] top/bottom  [f] cycle filter  [a] agent  [n] node  [esc] back  [q] quit%s",
		scrollInfo))

	return lipgloss.JoinVertical(lipgloss.Left, header, body, footer)
}

func (m Model) filteredEvents() []pipeline.Event {
	if m.filter == "" {
		return m.events
	}
	var filtered []pipeline.Event
	for _, ev := range m.events {
		if strings.HasPrefix(ev.Type, m.filter+".") || strings.HasPrefix(ev.Type, m.filter) {
			filtered = append(filtered, ev)
		}
	}
	return filtered
}

func (m Model) visibleEventLines() int {
	return max(5, m.height-6)
}

// ── Commands ───────────────────────────────────────────────────────────────

func (m Model) loadPipelines() tea.Cmd {
	root := m.root
	return func() tea.Msg {
		pipelines, err := pipeline.Discover(root)
		if err != nil {
			return errMsg{err}
		}
		return pipelinesLoadedMsg{pipelines}
	}
}

func (m Model) loadEvents() tea.Cmd {
	if len(m.pipelines) == 0 || m.cursor >= len(m.pipelines) {
		return nil
	}
	path := m.pipelines[m.cursor].JSONLPath
	return func() tea.Msg {
		events, err := pipeline.ReadEventsQuick(path, 0)
		if err != nil {
			return errMsg{err}
		}
		return eventsLoadedMsg{events}
	}
}

func (m Model) tailEvents() tea.Cmd {
	if len(m.pipelines) == 0 || m.cursor >= len(m.pipelines) {
		return nil
	}
	path := m.pipelines[m.cursor].JSONLPath
	offset := m.tailOffset
	return func() tea.Msg {
		events, newOffset, err := pipeline.TailEvents(path, offset)
		if err != nil {
			return errMsg{err}
		}
		if len(events) == 0 {
			return nil
		}
		return newEventsMsg{events: events, offset: newOffset}
	}
}

func tickCmd() tea.Cmd {
	return tea.Tick(2*time.Second, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

// ── Helpers ────────────────────────────────────────────────────────────────

func fileSize(path string) (int64, error) {
	info, err := os.Stat(path)
	if err != nil {
		return 0, err
	}
	return info.Size(), nil
}

func formatAge(t time.Time) string {
	if t.IsZero() {
		return "?"
	}
	d := time.Since(t)
	switch {
	case d < time.Minute:
		return fmt.Sprintf("%ds ago", int(d.Seconds()))
	case d < time.Hour:
		return fmt.Sprintf("%dm ago", int(d.Minutes()))
	case d < 24*time.Hour:
		return fmt.Sprintf("%dh ago", int(d.Hours()))
	default:
		return fmt.Sprintf("%dd ago", int(d.Hours()/24))
	}
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n-1] + "…"
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}


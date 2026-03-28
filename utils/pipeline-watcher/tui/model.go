package tui

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/bjornslib/pipeline-watcher/dot"
	"github.com/bjornslib/pipeline-watcher/signals"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

const (
	maxLogLines  = 20
	tickInterval = 2 * time.Second
)

// ── Messages ────────────────────────────────────────────────────────────────

type tickMsg time.Time
type graphLoadedMsg struct{ graph *dot.Graph }
type signalEventMsg struct{ event signals.Event }
type errMsg struct{ err error }

// ── Model ───────────────────────────────────────────────────────────────────

// Model is the bubbletea model for the pipeline-watcher TUI dashboard.
type Model struct {
	dotPath   string
	signalDir string
	stopCh    chan struct{}

	graph     *dot.Graph
	durations map[string]string
	startTime time.Time
	lastMtime time.Time

	// Ring buffer of activity log lines (newest last).
	activityLog []string

	// State for filter mode.
	filterActive bool
	filterStatus string

	err    error
	width  int
	height int
}

// New creates an initialised Model for the given DOT file.
func New(dotPath string) Model {
	return Model{
		dotPath:   dotPath,
		signalDir: signals.DeriveSignalDir(dotPath),
		stopCh:    make(chan struct{}),
		durations: make(map[string]string),
		startTime: time.Now(),
	}
}

// Init kicks off the initial graph load and background signal watcher.
func (m Model) Init() tea.Cmd {
	return tea.Batch(
		m.loadGraphCmd(),
		m.startSignalWatcher(),
		tickCmd(),
	)
}

// ── Update ──────────────────────────────────────────────────────────────────

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {

	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil

	case tickMsg:
		return m, tea.Batch(m.loadGraphCmd(), tickCmd())

	case graphLoadedMsg:
		m.graph = msg.graph
		m.err = nil
		return m, nil

	case signalEventMsg:
		if msg.event.Err != nil {
			m.appendLog(errorStyle.Render("signal error: " + msg.event.Err.Error()))
		} else {
			sig := msg.event.Signal
			line := fmt.Sprintf("[%s] %s → %s",
				time.Now().Format("15:04:05"),
				sig.NodeID,
				StyleForStatus(sig.Status).Render(sig.Status),
			)
			if sig.Message != "" {
				line += dimStyle.Render("  "+sig.Message)
			}
			m.appendLog(line)
		}
		// Reload graph to pick up updated attributes.
		return m, m.loadGraphCmd()

	case errMsg:
		m.err = msg.err
		return m, nil

	case tea.KeyMsg:
		return m.handleKey(msg)
	}

	return m, nil
}

func (m Model) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "q", "ctrl+c", "esc":
		close(m.stopCh)
		return m, tea.Quit
	case "r":
		m.appendLog(dimStyle.Render("["+time.Now().Format("15:04:05")+"] manual refresh"))
		return m, m.loadGraphCmd()
	case "f":
		m.filterActive = !m.filterActive
		if !m.filterActive {
			m.filterStatus = ""
		}
		return m, nil
	}
	return m, nil
}

// ── View ────────────────────────────────────────────────────────────────────

func (m Model) View() string {
	if m.width == 0 {
		return "Loading…\n"
	}

	sections := []string{
		m.renderHeader(),
		m.renderTable(),
		m.renderActivityLog(),
		m.renderFooter(),
	}
	return lipgloss.JoinVertical(lipgloss.Left, sections...)
}

func (m Model) renderHeader() string {
	pipelineID := "(unknown)"
	prdRef := ""
	if m.graph != nil {
		if m.graph.PipelineID != "" {
			pipelineID = m.graph.PipelineID
		} else if m.graph.Label != "" {
			pipelineID = m.graph.Label
		}
		prdRef = m.graph.PrdRef
	}

	elapsed := time.Since(m.startTime).Round(time.Second)

	title := fmt.Sprintf("pipeline-watcher  %s", pipelineID)
	if prdRef != "" {
		title += "  " + dimStyle.Render("["+prdRef+"]")
	}
	title += "  " + dimStyle.Render("elapsed: "+elapsed.String())

	return titleStyle.Render(title)
}

func (m Model) renderTable() string {
	nodes := m.visibleNodes()
	if len(nodes) == 0 {
		if m.err != nil {
			return tableBorderStyle.Render(errorStyle.Render("Error: " + m.err.Error()))
		}
		return tableBorderStyle.Render(normalStyle.Render("(no nodes found — waiting for pipeline)"))
	}

	content := RenderTable(nodes, m.durations, m.width)
	if m.graph != nil {
		content += "\n" + SummaryLine(m.graph.Nodes)
	}

	maxH := m.height - 16
	if maxH < 4 {
		maxH = 4
	}
	lines := strings.Split(content, "\n")
	if len(lines) > maxH {
		lines = lines[:maxH]
	}

	return tableBorderStyle.Width(m.width - 4).Render(strings.Join(lines, "\n"))
}

func (m Model) renderActivityLog() string {
	title := titleStyle.Render("Activity Log")
	var body string
	if len(m.activityLog) == 0 {
		body = dimStyle.Render("(no events yet)")
	} else {
		// Show last 10 lines.
		start := 0
		if len(m.activityLog) > 10 {
			start = len(m.activityLog) - 10
		}
		body = strings.Join(m.activityLog[start:], "\n")
	}
	inner := lipgloss.JoinVertical(lipgloss.Left, title, body)
	return logBorderStyle.Width(m.width - 4).Render(inner)
}

func (m Model) renderFooter() string {
	keys := helpStyle.Render("[q] quit  [r] refresh  [f] toggle filter")
	if m.filterActive {
		keys += normalStyle.Render("  filter: ON (active nodes)")
	}
	summary := ""
	if m.graph != nil {
		summary = SummaryLine(m.graph.Nodes)
	}
	return lipgloss.JoinVertical(lipgloss.Left, keys, summary)
}

// ── Helpers ──────────────────────────────────────────────────────────────────

func (m *Model) appendLog(line string) {
	m.activityLog = append(m.activityLog, line)
	if len(m.activityLog) > maxLogLines {
		m.activityLog = m.activityLog[len(m.activityLog)-maxLogLines:]
	}
}

func (m Model) visibleNodes() []dot.Node {
	if m.graph == nil {
		return nil
	}
	if !m.filterActive {
		return m.graph.Nodes
	}
	var out []dot.Node
	for _, n := range m.graph.Nodes {
		if n.EffectiveStatus() == "active" {
			out = append(out, n)
		}
	}
	return out
}

// ── Commands ──────────────────────────────────────────────────────────────────

func (m Model) loadGraphCmd() tea.Cmd {
	path := m.dotPath
	return func() tea.Msg {
		info, err := os.Stat(path)
		if err != nil {
			return errMsg{err}
		}
		_ = info // mtime available if needed for change detection
		g, err := dot.ParseFile(path)
		if err != nil {
			return errMsg{err}
		}
		return graphLoadedMsg{g}
	}
}

func (m Model) startSignalWatcher() tea.Cmd {
	return func() tea.Msg {
		ch, err := signals.Watch(m.signalDir, m.stopCh)
		if err != nil {
			return errMsg{err}
		}
		// Drain first event and return it; subsequent events are handled via
		// a recursive command pattern.
		ev, ok := <-ch
		if !ok {
			return nil
		}
		return signalEventMsg{ev}
	}
}

// WatchSignalsCmd returns a recurring command that reads from a pre-created channel.
// This is used after the first signal is received to keep listening.
func WatchSignalsCmd(ch <-chan signals.Event) tea.Cmd {
	return func() tea.Msg {
		ev, ok := <-ch
		if !ok {
			return nil
		}
		return signalEventMsg{ev}
	}
}

func tickCmd() tea.Cmd {
	return tea.Tick(tickInterval, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

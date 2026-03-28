package main

import (
	"fmt"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/bjornslib/pipeline-watcher/dot"
	"github.com/bjornslib/pipeline-watcher/signals"
	"github.com/bjornslib/pipeline-watcher/tui"
	tea "github.com/charmbracelet/bubbletea"
)

const usage = `pipeline-watcher — monitor CoBuilder Attractor DOT pipeline execution

Usage:
  pipeline-watcher watch <dot-file>    TUI dashboard mode (default)
  pipeline-watcher status <dot-file>   One-shot status summary
  pipeline-watcher tail <dot-file>     Stream pipeline events (like tail -f)
  pipeline-watcher -h                  Show this help

Status exit codes (status/tail commands):
  0  All nodes terminal (accepted/validated)
  1  One or more nodes failed
  2  Pipeline still running
`

func main() {
	if len(os.Args) < 2 {
		fmt.Fprint(os.Stderr, usage)
		os.Exit(1)
	}

	switch os.Args[1] {
	case "-h", "--help", "help":
		fmt.Print(usage)

	case "watch":
		dotFile := requireDotArg(2)
		runWatch(dotFile)

	case "status":
		dotFile := requireDotArg(2)
		runStatus(dotFile)

	case "tail":
		dotFile := requireDotArg(2)
		runTail(dotFile)

	default:
		// If the first arg looks like a file path, treat as implicit "watch".
		if fileExists(os.Args[1]) {
			runWatch(os.Args[1])
		} else {
			fmt.Fprintf(os.Stderr, "unknown command: %s\n\n%s", os.Args[1], usage)
			os.Exit(1)
		}
	}
}

// ── watch ────────────────────────────────────────────────────────────────────

func runWatch(dotFile string) {
	m := tui.New(dotFile)
	p := tea.NewProgram(m, tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		die("tui:", err)
	}
}

// ── status ───────────────────────────────────────────────────────────────────

func runStatus(dotFile string) {
	g, err := dot.ParseFile(dotFile)
	if err != nil {
		die("parse:", err)
	}

	pipelineID := g.PipelineID
	if pipelineID == "" {
		pipelineID = g.Label
	}
	if pipelineID == "" {
		pipelineID = dotFile
	}

	fmt.Printf("Pipeline: %s\n", pipelineID)
	if g.PrdRef != "" {
		fmt.Printf("PRD:      %s\n", g.PrdRef)
	}
	fmt.Printf("Nodes:    %d\n\n", len(g.Nodes))

	// Column widths.
	const (
		wID      = 30
		wHandler = 20
		wStatus  = 18
	)

	header := fmt.Sprintf("%-*s %-*s %-*s", wID, "NODE ID", wHandler, "HANDLER", wStatus, "STATUS")
	fmt.Println(header)
	fmt.Println(strings.Repeat("-", wID+wHandler+wStatus+2))

	counts := map[string]int{}
	for _, n := range g.Nodes {
		status := n.EffectiveStatus()
		counts[status]++
		fmt.Printf("%-*s %-*s %-*s\n", wID, n.ID, wHandler, n.Handler, wStatus, status)
	}

	fmt.Printf("\npending:%d  active:%d  impl_complete:%d  validated:%d  failed:%d  accepted:%d\n",
		counts["pending"], counts["active"], counts["impl_complete"],
		counts["validated"], counts["failed"], counts["accepted"])

	// Determine exit code.
	if counts["failed"] > 0 {
		os.Exit(1)
	}
	allTerminal := counts["pending"] == 0 && counts["active"] == 0 && counts["impl_complete"] == 0
	if !allTerminal {
		os.Exit(2)
	}
	os.Exit(0)
}

// ── tail ─────────────────────────────────────────────────────────────────────

func runTail(dotFile string) {
	signalDir := signals.DeriveSignalDir(dotFile)
	stop := make(chan struct{})

	// Handle Ctrl+C.
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		close(stop)
	}()

	fmt.Printf("[%s] pipeline-watcher tail: %s\n", ts(), dotFile)
	fmt.Printf("[%s] signal dir: %s\n", ts(), signalDir)

	// Initial one-shot status.
	g, err := dot.ParseFile(dotFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "[%s] warning: could not parse dot file: %v\n", ts(), err)
	} else {
		for _, n := range g.Nodes {
			fmt.Printf("[%s] initial  %s  status=%s\n", ts(), n.ID, n.EffectiveStatus())
		}
	}

	// Watch signal directory.
	eventCh, err := signals.Watch(signalDir, stop)
	if err != nil {
		die("signal watch:", err)
	}

	// Poll DOT file for mtime changes.
	var lastMtime time.Time
	if g != nil {
		if info, err := os.Stat(dotFile); err == nil {
			lastMtime = info.ModTime()
		}
	}

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-stop:
			fmt.Printf("[%s] tail stopped\n", ts())
			return

		case ev, ok := <-eventCh:
			if !ok {
				fmt.Printf("[%s] signal channel closed\n", ts())
				return
			}
			if ev.Err != nil {
				fmt.Printf("[%s] signal error: %v\n", ts(), ev.Err)
				continue
			}
			sig := ev.Signal
			fmt.Printf("[%s] signal  %-28s  status=%s  %s\n", ts(), sig.NodeID, sig.Status, sig.Message)

		case <-ticker.C:
			info, err := os.Stat(dotFile)
			if err != nil {
				continue
			}
			if info.ModTime().After(lastMtime) {
				lastMtime = info.ModTime()
				ng, err := dot.ParseFile(dotFile)
				if err != nil {
					fmt.Printf("[%s] parse error: %v\n", ts(), err)
					continue
				}
				if g != nil {
					// Diff node statuses.
					oldMap := nodeMap(g.Nodes)
					for _, n := range ng.Nodes {
						newStatus := n.EffectiveStatus()
						oldStatus := ""
						if old, ok := oldMap[n.ID]; ok {
							oldStatus = old.EffectiveStatus()
						}
						if newStatus != oldStatus {
							fmt.Printf("[%s] %-28s  %s → %s\n", ts(), n.ID, oldStatus, newStatus)
						}
					}
				}
				g = ng

				// Check if all terminal.
				if allTerminal(g.Nodes) {
					fmt.Printf("[%s] pipeline complete\n", ts())
					os.Exit(exitCode(g.Nodes))
				}
			}
		}
	}
}

// ── Helpers ──────────────────────────────────────────────────────────────────

func requireDotArg(idx int) string {
	if len(os.Args) <= idx {
		fmt.Fprintf(os.Stderr, "error: missing <dot-file> argument\n\n%s", usage)
		os.Exit(1)
	}
	return os.Args[idx]
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func ts() string {
	return time.Now().Format("15:04:05")
}

func nodeMap(nodes []dot.Node) map[string]dot.Node {
	m := make(map[string]dot.Node, len(nodes))
	for _, n := range nodes {
		m[n.ID] = n
	}
	return m
}

func allTerminal(nodes []dot.Node) bool {
	for _, n := range nodes {
		s := n.EffectiveStatus()
		if s == "pending" || s == "active" || s == "impl_complete" {
			return false
		}
	}
	return len(nodes) > 0
}

func exitCode(nodes []dot.Node) int {
	for _, n := range nodes {
		if n.EffectiveStatus() == "failed" {
			return 1
		}
	}
	return 0
}

func die(msg string, err error) {
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s %v\n", msg, err)
	} else {
		fmt.Fprintln(os.Stderr, msg)
	}
	os.Exit(1)
}

package main

import (
	"fmt"
	"os"
	"strings"

	"github.com/bjornslib/pipeline-watch/pipeline"
	"github.com/bjornslib/pipeline-watch/tui"
	tea "github.com/charmbracelet/bubbletea"
)

const usage = `pipeline-watch — interactive pipeline event viewer

Usage:
  pipeline-watch              Launch interactive TUI
  pipeline-watch list         List discovered pipelines
  pipeline-watch tail <path>  Stream events from a JSONL file (plain text)
  pipeline-watch -h           Show this help
`

func main() {
	if len(os.Args) < 2 {
		runTUI()
		return
	}

	switch os.Args[1] {
	case "-h", "--help", "help":
		fmt.Print(usage)

	case "list":
		root, _ := os.Getwd()
		pipelines, err := pipeline.Discover(root)
		if err != nil {
			die("discover:", err)
		}
		if len(pipelines) == 0 {
			fmt.Println("(no pipelines found)")
			return
		}
		for _, p := range pipelines {
			badge := "○"
			switch p.Status {
			case "running":
				badge = "●"
			case "completed":
				badge = "✓"
			case "failed":
				badge = "✗"
			}
			fmt.Printf("%s %-30s  %3d events  %d nodes  %-9s  %s\n",
				badge, p.ID, p.EventCount, p.NodeCount, p.Status, p.JSONLPath)
		}

	case "tail":
		if len(os.Args) < 3 {
			die("tail requires a JSONL file path", nil)
		}
		path := os.Args[2]
		events, err := pipeline.ReadEventsQuick(path, 0)
		if err != nil {
			die("read:", err)
		}

		// Apply optional --filter
		filter := ""
		for i, arg := range os.Args {
			if arg == "--filter" && i+1 < len(os.Args) {
				filter = os.Args[i+1]
			}
		}

		for _, ev := range events {
			if filter != "" && !strings.HasPrefix(ev.Type, filter) {
				continue
			}
			fmt.Println(pipeline.FormatEvent(ev))
		}

		// Summary
		counts := make(map[string]int)
		for _, ev := range events {
			if filter != "" && !strings.HasPrefix(ev.Type, filter) {
				continue
			}
			counts[ev.Type]++
		}
		if len(counts) > 0 {
			fmt.Println("\n--- Summary ---")
			total := 0
			for t, c := range counts {
				fmt.Printf("  %-22s  %d\n", t, c)
				total += c
			}
			fmt.Printf("  total: %d\n", total)
		}

	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n\n%s", os.Args[1], usage)
		os.Exit(1)
	}
}

func runTUI() {
	root, _ := os.Getwd()
	m := tui.New(root)
	p := tea.NewProgram(m, tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		die("tui:", err)
	}
}

func die(msg string, err error) {
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s %v\n", msg, err)
	} else {
		fmt.Fprintln(os.Stderr, msg)
	}
	os.Exit(1)
}

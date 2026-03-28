// Package pipeline discovers running pipelines and reads JSONL event streams.
package pipeline

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// Pipeline represents a discovered pipeline run directory.
type Pipeline struct {
	ID         string    // Pipeline identifier (from DOT graph or directory name)
	RunDir     string    // Absolute path to the run directory
	JSONLPath  string    // Path to pipeline-events.jsonl
	DotPath    string    // Path to the .dot file (if found)
	EventCount int       // Number of events in the JSONL file
	LastEvent  time.Time // Timestamp of the most recent event
	Status     string    // "running", "completed", "failed", or "unknown"
	NodeCount  int       // Number of nodes (from pipeline.started event)
}

// Event represents a single parsed JSONL event record.
type Event struct {
	Type       string                 `json:"type"`
	Timestamp  string                 `json:"timestamp"`
	PipelineID string                 `json:"pipeline_id"`
	NodeID     *string                `json:"node_id"`
	Data       map[string]interface{} `json:"data"`
	SpanID     *string                `json:"span_id"`
	Sequence   int                    `json:"sequence"`
	ParsedTime time.Time              // Derived from Timestamp
}

// Discover scans standard pipeline directories for JSONL event files.
// It looks in .pipelines/pipelines/ and .claude/attractor/pipelines/
// relative to the given root directory.
func Discover(root string) ([]Pipeline, error) {
	var pipelines []Pipeline

	searchDirs := []string{
		filepath.Join(root, ".pipelines", "pipelines"),
		filepath.Join(root, ".claude", "attractor", "pipelines"),
	}

	for _, base := range searchDirs {
		if _, err := os.Stat(base); os.IsNotExist(err) {
			continue
		}

		// Walk one or two levels deep looking for pipeline-events.jsonl
		entries, err := os.ReadDir(base)
		if err != nil {
			continue
		}

		for _, entry := range entries {
			if !entry.IsDir() {
				continue
			}
			pipelineDir := filepath.Join(base, entry.Name())

			// Check for JSONL directly in pipeline dir
			jsonlPath := filepath.Join(pipelineDir, "pipeline-events.jsonl")
			if _, err := os.Stat(jsonlPath); err == nil {
				if p, err := loadPipeline(entry.Name(), pipelineDir, jsonlPath); err == nil {
					pipelines = append(pipelines, p)
				}
				continue
			}

			// Check for timestamped run subdirectories
			subEntries, err := os.ReadDir(pipelineDir)
			if err != nil {
				continue
			}
			for _, sub := range subEntries {
				if !sub.IsDir() {
					continue
				}
				runDir := filepath.Join(pipelineDir, sub.Name())
				jsonlPath := filepath.Join(runDir, "pipeline-events.jsonl")
				if _, err := os.Stat(jsonlPath); err == nil {
					id := entry.Name() + "/" + sub.Name()
					if p, err := loadPipeline(id, runDir, jsonlPath); err == nil {
						pipelines = append(pipelines, p)
					}
				}
			}
		}
	}

	// Sort by last event time (most recent first)
	sort.Slice(pipelines, func(i, j int) bool {
		return pipelines[i].LastEvent.After(pipelines[j].LastEvent)
	})

	return pipelines, nil
}

// loadPipeline reads a JSONL file and extracts pipeline metadata.
func loadPipeline(id, runDir, jsonlPath string) (Pipeline, error) {
	p := Pipeline{
		ID:        id,
		RunDir:    runDir,
		JSONLPath: jsonlPath,
		Status:    "unknown",
	}

	// Look for .dot file in the run directory or parent
	dotFiles, _ := filepath.Glob(filepath.Join(runDir, "*.dot"))
	if len(dotFiles) > 0 {
		p.DotPath = dotFiles[0]
	} else {
		parentDots, _ := filepath.Glob(filepath.Join(filepath.Dir(runDir), "*.dot"))
		if len(parentDots) > 0 {
			p.DotPath = parentDots[0]
		}
	}

	// Scan JSONL for metadata (read first and last events)
	events, err := ReadEventsQuick(jsonlPath, 0)
	if err != nil {
		return p, err
	}

	p.EventCount = len(events)
	if len(events) > 0 {
		p.LastEvent = events[len(events)-1].ParsedTime

		// Determine status from events
		for i := len(events) - 1; i >= 0; i-- {
			switch events[i].Type {
			case "pipeline.completed":
				p.Status = "completed"
				goto done
			case "pipeline.failed":
				p.Status = "failed"
				goto done
			}
		}
		p.Status = "running"
	done:

		// Get node count from pipeline.started
		for _, ev := range events {
			if ev.Type == "pipeline.started" {
				if nc, ok := ev.Data["node_count"].(float64); ok {
					p.NodeCount = int(nc)
				}
				if pid, ok := ev.Data["pipeline_id"].(string); ok && pid != "" {
					p.ID = pid
				}
				break
			}
		}
	}

	return p, nil
}

// ReadEventsQuick reads all events from a JSONL file.
// If sinceMinutes > 0, only returns events from the last N minutes.
func ReadEventsQuick(path string, sinceMinutes float64) ([]Event, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var cutoff time.Time
	if sinceMinutes > 0 {
		cutoff = time.Now().UTC().Add(-time.Duration(sinceMinutes * float64(time.Minute)))
	}

	var events []Event
	scanner := bufio.NewScanner(f)
	// Increase buffer for long lines (agent messages can be large)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var ev Event
		if err := json.Unmarshal([]byte(line), &ev); err != nil {
			continue
		}
		// Parse timestamp
		if t, err := time.Parse(time.RFC3339Nano, ev.Timestamp); err == nil {
			ev.ParsedTime = t
		} else if t, err := time.Parse("2006-01-02T15:04:05.000000+00:00", ev.Timestamp); err == nil {
			ev.ParsedTime = t
		}

		if !cutoff.IsZero() && ev.ParsedTime.Before(cutoff) {
			continue
		}
		events = append(events, ev)
	}

	return events, scanner.Err()
}

// TailEvents reads new events from a JSONL file starting at byte offset.
// Returns new events and the updated offset.
func TailEvents(path string, offset int64) ([]Event, int64, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, offset, err
	}
	defer f.Close()

	if _, err := f.Seek(offset, 0); err != nil {
		return nil, offset, err
	}

	var events []Event
	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var ev Event
		if err := json.Unmarshal([]byte(line), &ev); err != nil {
			continue
		}
		if t, err := time.Parse(time.RFC3339Nano, ev.Timestamp); err == nil {
			ev.ParsedTime = t
		}
		events = append(events, ev)
	}

	// Get current position
	newOffset, _ := f.Seek(0, 2) // seek to end
	return events, newOffset, scanner.Err()
}

// FormatEvent returns a human-readable single-line representation of an event.
func FormatEvent(ev Event) string {
	ts := ev.ParsedTime.Local().Format("15:04:05.000")
	typePad := fmt.Sprintf("%-22s", ev.Type)

	node := " --"
	if ev.NodeID != nil && *ev.NodeID != "" {
		node = fmt.Sprintf("[%s]", *ev.NodeID)
	}

	detail := formatDetail(ev.Type, ev.Data)
	return fmt.Sprintf("%s  %s  %s  %s", ts, typePad, node, detail)
}

func formatDetail(eventType string, data map[string]interface{}) string {
	var parts []string

	switch eventType {
	case "pipeline.started":
		parts = append(parts, fmt.Sprintf("nodes=%v", data["node_count"]))
		if dp, ok := data["dot_path"].(string); ok {
			parts = append(parts, filepath.Base(dp))
		}
	case "pipeline.completed":
		if ms, ok := data["duration_ms"].(float64); ok {
			parts = append(parts, fmt.Sprintf("%.0fms", ms))
		}
	case "pipeline.failed":
		parts = append(parts, str(data, "error_type"), str(data, "error_message"))
	case "node.started":
		parts = append(parts, fmt.Sprintf("handler=%s", str(data, "handler_type")))
		if vc, ok := data["visit_count"].(float64); ok && vc > 1 {
			parts = append(parts, fmt.Sprintf("visit=%d", int(vc)))
		}
	case "node.completed":
		parts = append(parts, fmt.Sprintf("status=%s", str(data, "outcome_status")))
		if ms, ok := data["duration_ms"].(float64); ok {
			parts = append(parts, fmt.Sprintf("%.0fms", ms))
		}
		if tok, ok := data["tokens_used"].(float64); ok && tok > 0 {
			parts = append(parts, fmt.Sprintf("%dtok", int(tok)))
		}
	case "node.failed":
		parts = append(parts, str(data, "error_type"))
		if gg, ok := data["goal_gate"].(bool); ok && gg {
			parts = append(parts, "GOAL_GATE")
		}
	case "edge.selected":
		parts = append(parts, fmt.Sprintf("%s → %s", str(data, "from_node_id"), str(data, "to_node_id")))
	case "retry.triggered":
		parts = append(parts, fmt.Sprintf("attempt=%v", data["attempt_number"]))
		parts = append(parts, str(data, "error_type"))
	case "loop.detected":
		parts = append(parts, fmt.Sprintf("visits=%v/%v", data["visit_count"], data["limit"]))
	case "agent.message":
		parts = append(parts, fmt.Sprintf("[%s]", str(data, "agent_role")))
		parts = append(parts, fmt.Sprintf("turn=%v", data["turn"]))
		preview := str(data, "text_preview")
		if len(preview) > 120 {
			preview = preview[:120]
		}
		if i := strings.Index(preview, "\n"); i >= 0 {
			preview = preview[:i]
		}
		parts = append(parts, preview)
	case "agent.thinking":
		parts = append(parts, fmt.Sprintf("[%s]", str(data, "agent_role")))
		parts = append(parts, fmt.Sprintf("turn=%v", data["turn"]))
		parts = append(parts, fmt.Sprintf("%v chars", data["thinking_length"]))
	case "agent.tool_call":
		parts = append(parts, fmt.Sprintf("[%s]", str(data, "agent_role")))
		parts = append(parts, fmt.Sprintf("turn=%v", data["turn"]))
		parts = append(parts, str(data, "tool_name"))
		preview := str(data, "input_preview")
		if len(preview) > 100 {
			preview = preview[:100]
		}
		parts = append(parts, preview)
	case "agent.tool_result":
		parts = append(parts, fmt.Sprintf("[%s]", str(data, "agent_role")))
		parts = append(parts, fmt.Sprintf("turn=%v", data["turn"]))
		if isErr, ok := data["is_error"].(bool); ok && isErr {
			parts = append(parts, "ERROR")
		}
		parts = append(parts, fmt.Sprintf("%v chars", data["content_length"]))
	case "validation.started":
		parts = append(parts, fmt.Sprintf("rules=%v", data["rule_count"]))
	case "validation.completed":
		if passed, ok := data["passed"].(bool); ok {
			if passed {
				parts = append(parts, "PASS")
			} else {
				parts = append(parts, "FAIL")
			}
		}
	case "checkpoint.saved":
		if cp, ok := data["checkpoint_path"].(string); ok {
			parts = append(parts, filepath.Base(cp))
		}
	}

	return strings.Join(parts, "  ")
}

func str(data map[string]interface{}, key string) string {
	if v, ok := data[key].(string); ok {
		return v
	}
	return ""
}

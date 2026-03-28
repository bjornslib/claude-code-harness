// Package signals watches a pipeline signal directory for node completion events.
package signals

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	"github.com/fsnotify/fsnotify"
)

// Signal is the JSON payload written by pipeline workers to signal completion.
type Signal struct {
	NodeID       string   `json:"-"` // derived from filename
	Status       string   `json:"status"`
	Message      string   `json:"message"`
	FilesChanged []string `json:"files_changed"`
}

// Event wraps a Signal with metadata.
type Event struct {
	Signal Signal
	Err    error
}

// DeriveSignalDir computes the signal directory path from a DOT file path.
//
// Convention: if dot is at <any>/pipelines/foo.dot the signal dir is
// .pipelines/pipelines/signals/foo/  (relative to cwd).
//
// If the PIPELINE_SIGNAL_DIR env var is set it overrides this entirely.
func DeriveSignalDir(dotPath string) string {
	if env := os.Getenv("PIPELINE_SIGNAL_DIR"); env != "" {
		return env
	}

	base := filepath.Base(dotPath)
	pipelineID := strings.TrimSuffix(base, filepath.Ext(base))
	return filepath.Join(".pipelines", "pipelines", "signals", pipelineID)
}

// Watch starts watching signalDir for new/modified .json files and sends
// decoded Signal events to the returned channel.  The watcher runs until
// the stop channel is closed.
func Watch(signalDir string, stop <-chan struct{}) (<-chan Event, error) {
	events := make(chan Event, 32)

	// Ensure the directory exists (pipeline runner may create it later).
	if err := os.MkdirAll(signalDir, 0o755); err != nil {
		return nil, err
	}

	w, err := fsnotify.NewWatcher()
	if err != nil {
		return nil, err
	}

	if err := w.Add(signalDir); err != nil {
		w.Close()
		return nil, err
	}

	go func() {
		defer close(events)
		defer w.Close()
		for {
			select {
			case <-stop:
				return
			case fe, ok := <-w.Events:
				if !ok {
					return
				}
				if fe.Op&(fsnotify.Create|fsnotify.Write) == 0 {
					continue
				}
				if !strings.HasSuffix(fe.Name, ".json") {
					continue
				}
				sig, err := readSignal(fe.Name)
				select {
				case events <- Event{Signal: sig, Err: err}:
				case <-stop:
					return
				}
			case err, ok := <-w.Errors:
				if !ok {
					return
				}
				select {
				case events <- Event{Err: err}:
				case <-stop:
					return
				}
			}
		}
	}()

	return events, nil
}

func readSignal(path string) (Signal, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Signal{}, err
	}
	var sig Signal
	if err := json.Unmarshal(data, &sig); err != nil {
		return Signal{}, err
	}
	// Derive node ID from filename: e.g. "research_epic1.json" → "research_epic1"
	base := filepath.Base(path)
	sig.NodeID = strings.TrimSuffix(base, ".json")
	return sig, nil
}

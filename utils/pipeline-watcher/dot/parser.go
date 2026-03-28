// Package dot provides a regex-based parser for CoBuilder Attractor DOT pipeline files.
package dot

import (
	"os"
	"regexp"
	"strings"
)

// Node represents a single pipeline node extracted from a DOT file.
type Node struct {
	ID          string
	Label       string
	Handler     string
	Status      string
	Fillcolor   string
	WorkerType  string
	LlmProfile  string
	Shape       string
}

// Graph holds the parsed graph-level attributes and nodes from a DOT file.
type Graph struct {
	PipelineID string
	PrdRef     string
	Label      string
	Nodes      []Node
}

var (
	// matches:  nodeid [ key="val" key=val ... ]
	nodeBlockRe = regexp.MustCompile(`(?m)^\s*(\w+)\s*\[([^\]]+)\]`)
	// matches quoted attribute: key="value"
	attrQuotedRe = regexp.MustCompile(`(\w+)="([^"]*)"`)
	// matches bare attribute: key=value (no quotes)
	attrBareRe = regexp.MustCompile(`(\w+)=(\w+)`)
	// graph-level attributes in the DOT header (e.g. pipeline_id="foo")
	graphAttrRe = regexp.MustCompile(`(?m)^\s*(\w+)="([^"]*)"`)
)

// ParseFile reads and parses a DOT pipeline file from disk.
func ParseFile(path string) (*Graph, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return Parse(string(data)), nil
}

// Parse parses a DOT source string and returns a Graph.
func Parse(src string) *Graph {
	g := &Graph{}

	// Extract graph-level attributes from lines before the first node block.
	// We scan the whole source but node attrs take precedence, so do graph attrs first.
	for _, m := range graphAttrRe.FindAllStringSubmatch(src, -1) {
		key, val := m[1], m[2]
		switch key {
		case "pipeline_id":
			g.PipelineID = val
		case "prd_ref":
			g.PrdRef = val
		case "label":
			if g.Label == "" {
				g.Label = val
			}
		}
	}

	// Extract node blocks.
	for _, nm := range nodeBlockRe.FindAllStringSubmatch(src, -1) {
		nodeID := nm[1]
		attrBlock := nm[2]

		// Skip DOT keywords that look like node IDs.
		if isKeyword(nodeID) {
			continue
		}

		node := Node{ID: nodeID}
		attrs := parseAttrs(attrBlock)
		for k, v := range attrs {
			switch k {
			case "label":
				node.Label = v
			case "handler":
				node.Handler = v
			case "status":
				node.Status = v
			case "fillcolor":
				node.Fillcolor = v
			case "worker_type":
				node.WorkerType = v
			case "llm_profile":
				node.LlmProfile = v
			case "shape":
				node.Shape = v
			}
		}
		if node.Label == "" {
			node.Label = nodeID
		}
		g.Nodes = append(g.Nodes, node)
	}

	return g
}

// parseAttrs extracts key=value pairs (quoted and bare) from an attribute block string.
func parseAttrs(block string) map[string]string {
	attrs := make(map[string]string)

	// Quoted first (higher priority).
	for _, m := range attrQuotedRe.FindAllStringSubmatch(block, -1) {
		attrs[m[1]] = m[2]
	}

	// Bare values only if not already set by quoted.
	for _, m := range attrBareRe.FindAllStringSubmatch(block, -1) {
		if _, exists := attrs[m[1]]; !exists {
			attrs[m[1]] = m[2]
		}
	}

	return attrs
}

// isKeyword returns true for DOT language keywords that appear as identifiers.
func isKeyword(s string) bool {
	switch strings.ToLower(s) {
	case "graph", "digraph", "subgraph", "node", "edge", "strict":
		return true
	}
	return false
}

// StatusFromFillcolor maps a DOT fillcolor to a canonical status string
// when the status attribute is not present.
func StatusFromFillcolor(color string) string {
	switch strings.ToLower(color) {
	case "lightblue", "#add8e6":
		return "active"
	case "yellow", "#ffff00":
		return "impl_complete"
	case "green", "#00ff00", "lightgreen", "#90ee90":
		return "validated"
	case "red", "#ff0000", "lightcoral", "#f08080":
		return "failed"
	case "limegreen", "#32cd32", "brightgreen":
		return "accepted"
	default:
		return "pending"
	}
}

// EffectiveStatus returns node.Status if set, otherwise derives it from Fillcolor.
func (n *Node) EffectiveStatus() string {
	if n.Status != "" {
		return n.Status
	}
	return StatusFromFillcolor(n.Fillcolor)
}

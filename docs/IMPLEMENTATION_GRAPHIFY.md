# Graphify — Codebase Graph Extraction & Navigation

> **Status:** Active usage
> **Objective:** Generate and maintain a semantic graph of the ConciergeOS codebase to enable fast architecture queries, component discovery, and relationship analysis — replacing slow grep-based exploration with scoped subgraph lookups.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Output Structure](#2-output-structure)
3. [Commands](#3-commands)
   - [3.1 Extraction](#31-extraction)
   - [3.2 Querying](#32-querying)
   - [3.3 Navigation](#33-navigation)
4. [Graph Freshness](#4-graph-freshness)
5. [Integration with AI Assistants](#5-integration-with-ai-assistants)

---

## 1. Overview

Graphify is a codebase analysis tool that builds a semantic graph from source files. It extracts classes, functions, modules, and their relationships into a structured graph that can be queried, visualized, and navigated.

In ConciergeOS, Graphify is used to:

- **Answer architecture questions** without reading dozens of files
- **Discover component relationships** (e.g., "Which service does the guest search route call?")
- **Navigate the codebase** using natural language queries
- **Maintain up-to-date documentation** of the project's internal structure

---

## 2. Output Structure

Graphify writes all output to the `graphify-out/` directory at the project root:

```
graphify-out/
├── GRAPH_REPORT.md          # Full text report with community hubs and statistics
├── graph.json               # Machine-readable graph data (nodes + edges)
├── graph.html               # Interactive visual graph for browser viewing
├── manifest.json            # Build manifest with timestamps and file hashes
├── .graphify_analysis.json  # Internal analysis metadata
├── .graphify_labels.json    # Label mappings for nodes
├── .graphify_root           # Root marker file
├── .graphify_semantic_marker # Semantic analysis marker
├── cache/                   # Internal cache directory
└── <date>/                  # Dated snapshots for comparison (e.g., 2026-08-05/)
    ├── GRAPH_REPORT.md
    ├── graph.json
    ├── manifest.json
    └── .graphify_analysis.json
```

### Key Files

| File | Purpose | Format |
|------|---------|--------|
| `GRAPH_REPORT.md` | Human-readable report with community hubs, statistics, and freshness info | Markdown |
| `graph.json` | Full graph data for programmatic access and querying | JSON |
| `graph.html` | Interactive visualization with pan, zoom, and click-to-inspect | HTML |
| `manifest.json` | Build metadata including extracted files, timestamps, and token costs | JSON |

---

## 3. Commands

### 3.1 Extraction

Build or update the project graph:

| Command | Description |
|---------|-------------|
| `graphify extract .` | Extract graph from the current directory (full extraction) |
| `graphify update .` | Update an existing graph incrementally (no API cost) |

**Environment variables** (optional, for LLM-assisted inference):
```bash
OPENAI_BASE_URL=http://localhost:8080/v1 \
OPENAI_MODEL=model-name \
OPENAI_API_KEY="your-key" \
graphify extract .
```

> **Note:** Graphify can operate in cluster-only mode (no LLM) which produces a graph from static analysis alone. LLM-assisted mode infers additional relationships.

### 3.2 Querying

Ask questions about the codebase architecture:

| Command | Description | Example |
|---------|-------------|---------|
| `graphify query "<question>"` | General architecture question | `graphify query "how does guest search work?"` |
| `graphify explain "<concept>"` | Focused concept explanation | `graphify explain "prompt chain execution"` |
| `graphify path "<A>" "<B>"` | Find relationships between two components | `graphify path "guest_search.py" "llm.py"` |

These commands return a **scoped subgraph** — much smaller than the full report — containing only the nodes and edges relevant to the query.

### 3.3 Navigation

Type `/graphify` in Copilot Chat to trigger a graph build or update directly from the editor.

---

## 4. Graph Freshness

The graph stores the Git commit hash it was built from. To check if the graph is stale:

```bash
# Check the commit the graph was built from
head -1 graphify-out/GRAPH_REPORT.md
# Output: Built from commit: `4e30a591`

# Compare with current HEAD
git rev-parse HEAD
```

If the hashes differ, the graph is stale. Rebuild it with:

```bash
graphify update .
```

---

## 5. Integration with AI Assistants

Graphify is integrated into the project's AI assistant workflow via `.clinerules/04-questions-about-codebase.md`. The assistant follows this decision tree for codebase questions:

```
1. Is graphify-out/graph.json present?
   ├── Yes → Use graphify query/path/explain
   └── No  → Fall back to file exploration

2. Is graphify-out/wiki/index.md present?
   ├── Yes → Use for broad navigation questions
   └── No  → Skip to report

3. Read graphify-out/GRAPH_REPORT.md
   └── Only for broad architecture review or when queries return insufficient context

4. Read source files
   └── Only when (a) modifying code, (b) graph lacks detail, or (c) graph is stale
```

### Trigger Phrases

The assistant will prefer Graphify for questions containing:

- "how do I…"
- "where is…"
- "what does … do"
- "add/modify a <component>"
- "explain the architecture"
- Any question depending on how files or classes relate


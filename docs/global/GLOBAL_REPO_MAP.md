# Global Repo Map

Owner: MCamner / mansys
Last updated: 2026-05-14

## Repos

| Repo | Path | Purpose | Version |
|---|---|---|---|
| `mq-mcp` | `~/mq-mcp` | Local MCP server, OpenAI bridge, vector store tooling | 0.2.x |
| `repo-signal` | `~/repo-signal` | Repo intelligence: publish readiness, scanning, AI Q&A, semantic upload | 0.1.9 |
| `macos-scripts` | `~/macos-scripts` | mqlaunch TUI, macOS command surfaces, workflows, scripts | 0.2.3 |
| `atlas-one` | `~/atlas-one` | Adaptive prompt system and structured thinking HTML app | 0.1.0 |
| `atlas-loop` | `~/atlas-loop` | Minimal command surface for Instagram content systems | 0.1.1 |
| `mcamner-journal` | `~/mcamner-journal` | GitHub Pages journal — film, music, design, archive | 0.1.3 |
| `coolThing` | `~/coolThing` | Retro web experiments, local music tools, small repo utilities | 0.1.0 |
| `zephyr-workbench` | `~/zephyr-workbench` | Architecture/YAML modeling experiments and diagramming | 0.1.0 |

## How repos relate

```text
macos-scripts
  └── mqlaunch — TUI launcher for all local commands
      ├── ask / bridget → mq-mcp (MCP tools + OpenAI bridge)
      ├── repo-signal commands → repo-signal (scanning, publish checks)
      └── release-check → macos-scripts release flow

mq-mcp
  ├── server.py → FastMCP server (local tools)
  ├── bridge.py → OpenAI Chat API ↔ MCP
  ├── ask.py → OpenAI Responses API + vector stores
  └── scripts/build_semantic_memory_pack.sh → this vector store

repo-signal
  ├── repo-signal analyze → scan any repo
  ├── repo-signal publish-checklist → release readiness
  ├── repo-signal repoaware → AI-powered repo Q&A
  └── repo-signal semantic-upload → upload repo to vector store

atlas-one / atlas-loop
  └── standalone HTML/JS apps + prompt routing

mcamner-journal / coolThing / zephyr-workbench
  └── independent projects, GitHub Pages deployments
```

## Primary AI tooling

| Tool | Repo | What it does |
|---|---|---|
| `bridget "prompt"` | mq-mcp | OpenAI + live MCP tools |
| `ask "prompt"` | mq-mcp | Vector store Q&A |
| `repo-signal repoaware` | repo-signal | Repo-aware AI analysis |
| `mqlaunch` | macos-scripts | TUI entry point for everything |

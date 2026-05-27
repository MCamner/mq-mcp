---
id: BND-001
title: mq-mcp owns the central cognition runtime
date: 2026-05-28
status: accepted
area: boundaries, architecture, review_engine
---

## Boundary

mq-mcp owns and is solely responsible for:

- Review engine and review contracts
- Semantic retrieval and review memory
- Repo context selection for reviews
- Architecture memory and architecture drift detection
- MCP runtime and safety metadata
- Multi-pass review and risk analysis

mq-mcp must NOT absorb:

- Heavy UI or interactive terminal experience (→ macos-scripts, mq-hal)
- Duplicated repository indexing or repo metrics dashboards (→ repo-signal)
- Workflow automation logic or task scheduling (→ mq-agent)
- Voice or TTS beyond the minimal Bridget integration (→ bridget_voice.py boundary)

## Rationale

Without an explicit ownership model, AI reasoning capabilities migrate into
orchestrators and agents, creating duplicated and divergent logic. mq-mcp is
the single source of truth for how the ecosystem reasons about code and architecture.
Keeping cognition centralized makes it auditable, testable, and improvable in one place.

## Consequences

- New review capabilities go in `review_engine/`, not in mq-agent.
- mq-agent may invoke mq-mcp review tools but may not reimplement review logic.
- repo-signal exports repository intelligence; mq-mcp imports and uses it.
  mq-mcp does not duplicate repo-signal's graph building.

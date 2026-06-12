---
name: integration-stack-maintainer
description: Use when working on mq-mcp integrations with mq-hal, repo-signal, MQ_MCP_LOCAL_REPOS, semantic repo analysis, global docs, or cross-repo workflows.
---

# Integration Stack Maintainer

Use this skill for the surrounding MQ ecosystem: `mq-mcp`, `mq-hal`, `repo-signal`, local repo registration, and global documentation.

## When to use

* Working on mq-mcp integration with mq-hal, repo-signal, or configured local repos
* Changing `MQ_MCP_LOCAL_REPOS`, `MQ_MCP_ALLOWED_PATHS`, or cross-repo tool behavior
* Maintaining global docs, semantic packs, or ecosystem documentation
* Adding or debugging integration smoke checks

## When not to use

* Adding new standalone MCP tools — use `mcp-tool-safety-maintainer`
* Changing Bridget or bridge.py behavior — use `bridget-bridge-maintainer`
* Review engine changes — use `review-runtime-maintainer`

## Evals

### Should trigger

* "register a new local repo for cross-repo tools"
* "the repo-signal integration smoke check fails"
* "add a zephyr_* integration tool wired to zephyr-workbench"
* "update the global command surface docs"

### Should not trigger

* "add a standalone screenshot tool" → use `mcp-tool-safety-maintainer`
* "fix Bridget tool discovery" → use `bridget-bridge-maintainer`
* "change review contracts" → use `review-runtime-maintainer`
* "docs drift unrelated to integrations" → use `docs-maintainer`

## Integration Role

`mq-mcp` is the local MCP bridge layer. It connects local assistant workflows to safe repo analysis and publish-quality checks.

Integration tool families (`hal_*`, `repo_signal_*`, `ums_*`, `zephyr_*`, plus `list_local_repos`, `open_repo_terminal`, and `run_tests`) grow over time — do not trust a hardcoded list. Get the current surface from:

* `generated/tool-index.json` (authoritative, generated)
* `TOOL_INDEX.md`
* global docs under `docs/global/`

## Files To Inspect

* `mq-mcp/server.py`
* `docs/integration.md`
* `docs/integration.html`
* `docs/global/GLOBAL_COMMAND_SURFACE.md`
* `docs/global/GLOBAL_ARCHITECTURE_NOTES.md`
* `docs/global/GLOBAL_REPO_MAP.md`
* `docs/global/GLOBAL_VECTOR_STORE_POLICY.md`
* `VECTOR_CONTEXT.md`
* `scripts/check-integration-docs.sh`
* `scripts/check-integration-smoke.sh`
* `scripts/build_semantic_memory_pack.sh`
* `scripts/upload_semantic_memory.py`
* `scripts/upload_vector_pack.py`

## Environment Contracts

* `MQ_MCP_LOCAL_REPOS` registers known local repositories by absolute path.
* `MQ_MCP_ALLOWED_PATHS` grants explicit external file roots.
* Registered repos should be real project roots, not broad home-directory paths.
* Cross-repo tools should remain read-only unless the user explicitly asks for controlled local actions.

## Change Rules

When adding or changing an integration:

1. Keep subprocess commands allowlisted and argument-bounded.
2. Keep repo paths resolved from `MQ_MCP_LOCAL_REPOS` or allowed roots.
3. Document the integration in README and `docs/integration.md`.
4. Update `docs/TOOL_SAFETY.md` with class, resolver, write capability, and subprocess status.
5. Update smoke checks so drift is caught.
6. Add tests for blocked repos, missing tools, or malformed inputs when practical.

## Verification

```bash
./scripts/check-integration-docs.sh
./scripts/check-integration-smoke.sh
./scripts/check-bridge-tool-discovery.sh
uv --directory mq-mcp run python bridge.py --tools
```

For semantic memory work:

```bash
./scripts/build_semantic_memory_pack.sh
```

Run upload scripts only when the user explicitly asks and credentials/config are present.

## Output Standard

For integration reports, state what is wired, what is documented, what is only inferred, and the exact command that verified it.

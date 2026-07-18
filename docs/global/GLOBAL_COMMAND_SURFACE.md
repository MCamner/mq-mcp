# Global Command Surface

All important commands across MCamner repos.

## mq-mcp

```bash
# AI bridge with live MCP tools
bridget "prompt"
bridget -m gpt-5.5 "prompt"        # override model
bridget --tools                     # list available MCP tools
bridget --search "prompt"           # use vector store instead of tools

# Vector store Q&A
ask "prompt"
ask -m gpt-5.5 "prompt"

# MCP server
uv run mcp run server.py            # run server directly
uv run python bridge.py --tools     # list tools via bridge

# Validation
./scripts/validate.sh
uv --directory mq-mcp run pytest ../tests -v

# Rebuild vector pack
bash scripts/build_vector_pack.sh           # mq-mcp-only pack
bash scripts/build_semantic_memory_pack.sh  # global cross-repo pack
uv run python scripts/upload_semantic_memory.py
```

## repo-signal

```bash
repo-signal analyze                 # scan current repo
repo-signal analyze --format json
repo-signal publish-checklist .     # release readiness
repo-signal doctor                  # system health check
repo-signal repoaware --mode review "prompt"
repo-signal repoaware --mode ask "prompt"
repo-signal ask "prompt"            # vector store Q&A
repo-signal semantic-upload         # upload repo to vector store
repo-signal portfolio-check         # check multiple repos
```

## macos-scripts / mqlaunch

```bash
mqlaunch                            # open TUI in new Terminal window
mqlaunch ask "prompt"               # command-mode: AI ask
mqlaunch release-check              # run release checks
mqlaunch doctor                     # system/tool health
mqlaunch scan                       # vault scan

# Shell aliases
ghost    # network-ghost.sh — network privacy
scan     # vault-scan.sh
guard    # blackout.sh
reap     # overseer.sh
pulse    # pulse.sh
mc       # mission-control.sh
mqauto   # ai-mode.sh auto
mqone    # ai-mode.sh one
```

## zephyr-workbench

```bash
zephyr init
zephyr add
zephyr diagram
zephyr analyze
zephyr diff
uv run pytest tests/ -v
```

## Shell shortcuts (zshrc)

```bash
mqrepo      # cd ~/mq-mcp
mqpy        # cd ~/mq-mcp/mq-mcp
mqtest      # run tests
mqval       # run validate.sh
mqstat      # git status
mqreleasecheck  # full release readiness

gst         # git status --short --branch
glog        # git log --oneline --decorate --graph -20
gds         # git diff --staged
reload      # source ~/.zshrc
zshrc       # open ~/.zshrc in $EDITOR
mkcd <dir>  # mkdir + cd
```

## Model selection

```bash
OPENAI_MODEL="gpt-5.4-mini"   # default (cheap/fast)
OPENAI_MODEL="gpt-5.5"        # power mode
OPENAI_MODEL="gpt-4.1"        # fallback
```

Override per call:

```bash
OPENAI_MODEL="gpt-5.5" ask "gör en djup repo-review"
bridget -m gpt-5.5 "detailed analysis"
```

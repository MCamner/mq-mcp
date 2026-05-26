# Upgrade Guide

How to update `mq-mcp` to the latest version.

## Standard Update

To update your local installation, run these commands from the repository root:

```bash
./scripts/upgrade.sh
```

The helper pulls `main`, syncs dependencies, reinstalls the `mq-mcp` command,
and runs validation.

## Manual Update

Use the manual flow when you want to inspect each step:

1.  **Pull the latest changes**:
    ```bash
    git pull origin main
    ```

2.  **Update dependencies**:
    ```bash
    cd mq-mcp
    uv sync
    ```

3.  **Run validation**:
    ```bash
    cd ..
    mq-mcp validate
    ```

## Environment Changes

Sometimes new versions introduce new environment variables or configuration options.

1.  Compare your `.env` with `.env.example`:
    ```bash
    diff mq-mcp/.env mq-mcp/.env.example
    ```
2.  If new variables like `MQ_MCP_LOCAL_REPOS` or `MQ_MCP_ALLOWED_PATHS` have been added, update your `.env` file accordingly.

## Troubleshooting Upgrades

If the project fails after an update:

1.  **Force clean environment**:
    ```bash
    cd mq-mcp
    rm -rf .venv
    uv sync
    ```
2.  **Check for breaking changes**:
    Review the [CHANGELOG.md](../CHANGELOG.md) for any manual steps required for the new version.
3.  **Validate again**:
    Run `./scripts/validate.sh` and check the output for missing tools or files.

## Version Check

To verify your current version:

```bash
mq-mcp version
```

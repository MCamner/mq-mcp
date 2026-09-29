#!/usr/bin/env python3
"""
Upload /tmp/mq-mcp-vector-pack to an explicitly isolated mq-mcp vector store.

This legacy maintenance path replaces every file in MQ_MCP_VECTOR_STORE_ID.
It refuses the shared canonical store. Normal repository memory refreshes must
use mq-agent's identity-scoped latest-only flow.

Run from repo root:
  bash scripts/build_vector_pack.sh
  export MQ_MCP_VECTOR_STORE_ID=vs_isolated
  python3 scripts/upload_vector_pack.py
"""

from pathlib import Path
import os

from openai import OpenAI

CANONICAL_VECTOR_STORE_ID = "vs_69ffa9a4ef5c81919d7d237c3ecdc260"
PACK_DIR = Path("/tmp/mq-mcp-vector-pack")
ALLOWED_SUFFIXES = {".md", ".txt", ".py", ".sh", ".yml", ".yaml", ".html"}


def resolve_target_store() -> str:
    vector_store_id = os.getenv("MQ_MCP_VECTOR_STORE_ID", "").strip()
    if not vector_store_id:
        raise SystemExit(
            "MQ_MCP_VECTOR_STORE_ID is not set. "
            "Use mq-agent memory refresh for canonical repo memory."
        )
    if vector_store_id == CANONICAL_VECTOR_STORE_ID:
        raise SystemExit(
            "Refusing full-store replacement of the shared canonical store. "
            "Use: mq-agent memory refresh ~/mq-mcp --approve --cleanup-stale"
        )
    return vector_store_id


def pack_files() -> list[Path]:
    return sorted(
        p for p in PACK_DIR.rglob("*")
        if p.is_file() and p.suffix in ALLOWED_SUFFIXES
    )


def clear_store(client: OpenAI, vector_store_id: str) -> int:
    """Detach and delete every file in ``vector_store_id``.

    The operation is destructive and non-transactional: upload failure after this
    step can leave the store empty or partially rebuilt. Returns detached file count.
    """
    removed = 0

    while True:
        existing = client.vector_stores.files.list(vector_store_id=vector_store_id)
        if not existing.data:
            break

        for vsf in existing.data:
            client.vector_stores.files.delete(
                vector_store_id=vector_store_id,
                file_id=vsf.id,
            )
            try:
                client.files.delete(vsf.id)
            except Exception:
                pass
            removed += 1

    return removed


def upload_pack(client: OpenAI, vector_store_id: str, files: list[Path]) -> tuple[int, int]:
    ok = 0
    failed = 0

    for path in files:
        print(f"  {path.name} ...", end=" ", flush=True)
        try:
            with path.open("rb") as f:
                result = client.vector_stores.files.upload_and_poll(
                    vector_store_id=vector_store_id,
                    file=f,
                )
            print(result.status)
            ok += 1
        except Exception as exc:
            print(f"FAILED: {exc}")
            failed += 1

    return ok, failed


def main() -> None:
    vector_store_id = resolve_target_store()

    files = pack_files()
    if not files:
        raise SystemExit(
            f"No uploadable files found in {PACK_DIR}. "
            "Run scripts/build_vector_pack.sh first."
        )

    client = OpenAI()
    vs = client.vector_stores.retrieve(vector_store_id)

    print(f"Store: {vs.name} ({vs.id})")
    print(f"Current files: {vs.file_counts.total}")
    print(f"Pack files: {len(files)}")
    print()

    print("Removing existing files from store...")
    removed = clear_store(client, vector_store_id)
    print(f"  Removed {removed} files.")
    print()

    print("Uploading pack...")
    ok, failed = upload_pack(client, vector_store_id, files)

    vs = client.vector_stores.retrieve(vector_store_id)
    print()
    print(f"Done. {ok} uploaded, {failed} failed.")
    print(f"Store now has {vs.file_counts.completed} completed files.")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

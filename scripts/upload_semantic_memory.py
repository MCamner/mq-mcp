#!/usr/bin/env python3
"""
Upload the cross-repo semantic memory pack to the 'semantic repository memory' vector store.

Replaces all existing files in the store with the current pack contents.

Run from mq-mcp/mq-mcp dir:
  bash ../scripts/build_semantic_memory_pack.sh
  uv run python ../scripts/upload_semantic_memory.py
"""

from pathlib import Path
from openai import OpenAI

VECTOR_STORE_ID = "vs_69ffa9a4ef5c81919d7d237c3ecdc260"
PACK_DIR = Path("/tmp/semantic-memory-pack")
ALLOWED_SUFFIXES = {".md", ".txt", ".py", ".sh", ".yml", ".yaml", ".html"}


def clear_store(client: OpenAI) -> None:
    print("Removing existing files from store...")
    removed = 0
    while True:
        existing = client.vector_stores.files.list(vector_store_id=VECTOR_STORE_ID)
        if not existing.data:
            break
        for vsf in existing.data:
            # Detach from vector store
            client.vector_stores.files.delete(
                vector_store_id=VECTOR_STORE_ID,
                file_id=vsf.id,
            )
            # Delete underlying file object (may already be gone)
            try:
                client.files.delete(vsf.id)
            except Exception:
                pass
            removed += 1
    print(f"  Removed {removed} files.")


def upload_pack(client: OpenAI) -> None:
    files = sorted(
        p for p in PACK_DIR.rglob("*")
        if p.is_file() and p.suffix in ALLOWED_SUFFIXES
    )

    if not files:
        raise SystemExit(
            f"No uploadable files found in {PACK_DIR}. "
            "Run build_semantic_memory_pack.sh first."
        )

    print(f"\nUploading {len(files)} files...")
    ok = 0
    failed = 0
    for path in files:
        print(f"  {path.name} ...", end=" ", flush=True)
        try:
            with path.open("rb") as f:
                result = client.vector_stores.files.upload_and_poll(
                    vector_store_id=VECTOR_STORE_ID,
                    file=f,
                )
            print(result.status)
            ok += 1
        except Exception as exc:
            print(f"FAILED: {exc}")
            failed += 1

    print(f"\nDone. {ok} uploaded, {failed} failed.")


def main() -> None:
    client = OpenAI()

    vs = client.vector_stores.retrieve(VECTOR_STORE_ID)
    print(f"Store: {vs.name} ({vs.id})")
    print(f"Current files: {vs.file_counts.total}")
    print()

    clear_store(client)
    upload_pack(client)

    vs = client.vector_stores.retrieve(VECTOR_STORE_ID)
    print(f"\nStore now has {vs.file_counts.completed} completed files.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Creates an OpenAI vector store named mq-mcp-repo-knowledge
and uploads all relevant files from /tmp/mq-mcp-vector-pack.

Run from repo root:
  python3 scripts/create_vector_store.py
"""

from pathlib import Path
from openai import OpenAI

VECTOR_STORE_NAME = "mq-mcp-repo-knowledge"
PACK_DIR = Path("/tmp/mq-mcp-vector-pack")

ALLOWED_SUFFIXES = {".md", ".txt", ".py", ".sh", ".yml", ".yaml", ".html"}

client = OpenAI()


def main() -> None:
    files = sorted(
        path for path in PACK_DIR.rglob("*")
        if path.is_file() and path.suffix in ALLOWED_SUFFIXES
    )

    if not files:
        raise SystemExit(f"No uploadable files found in {PACK_DIR}")

    print(f"Files to upload: {len(files)}")
    for f in files:
        print(f"  {f.relative_to(PACK_DIR)}")
    print()

    print(f"Creating vector store: {VECTOR_STORE_NAME}")
    vector_store = client.vector_stores.create(name=VECTOR_STORE_NAME)
    print(f"Vector store ID: {vector_store.id}")
    print()

    for path in files:
        relative = path.relative_to(PACK_DIR)
        print(f"Uploading: {relative} ...", end=" ", flush=True)
        with path.open("rb") as f:
            result = client.vector_stores.files.upload_and_poll(
                vector_store_id=vector_store.id,
                file=f,
            )
        print(result.status)

    print()
    print("Done.")
    print(f"VECTOR_STORE_ID={vector_store.id}")
    print()
    print("Add this to your .env:")
    print(f"  OPENAI_VECTOR_STORE_ID={vector_store.id}")


if __name__ == "__main__":
    main()

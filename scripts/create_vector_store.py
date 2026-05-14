#!/usr/bin/env python3
"""
Creates an OpenAI vector store named mq-mcp-repo-knowledge
and uploads all relevant files from /tmp/mq-mcp-vector-pack.

Run from repo root:
  bash scripts/build_vector_pack.sh
  python3 scripts/create_vector_store.py
"""

import re
from pathlib import Path
from openai import OpenAI

VECTOR_STORE_NAME = "mq-mcp-repo-knowledge"
PACK_DIR = Path("/tmp/mq-mcp-vector-pack")
ENV_FILE = Path(__file__).resolve().parent.parent / "mq-mcp" / ".env"

ALLOWED_SUFFIXES = {".md", ".txt", ".py", ".sh", ".yml", ".yaml", ".html"}


def update_env(vector_store_id: str) -> None:
    key = "OPENAI_VECTOR_STORE_ID"
    line = f"{key}={vector_store_id}\n"

    if not ENV_FILE.exists():
        ENV_FILE.write_text(line)
        print(f"Created {ENV_FILE} with {key}")
        return

    content = ENV_FILE.read_text()

    if re.search(rf"^{key}=", content, re.MULTILINE):
        content = re.sub(rf"^{key}=.*$", line.rstrip(), content, flags=re.MULTILINE)
        print(f"Updated {key} in {ENV_FILE}")
    else:
        content = content.rstrip("\n") + "\n" + line
        print(f"Added {key} to {ENV_FILE}")

    ENV_FILE.write_text(content)


def main() -> None:
    client = OpenAI()

    files = sorted(
        p for p in PACK_DIR.rglob("*")
        if p.is_file() and p.suffix in ALLOWED_SUFFIXES
    )

    if not files:
        raise SystemExit(f"No uploadable files found in {PACK_DIR}. Run build_vector_pack.sh first.")

    print(f"Files to upload: {len(files)}")
    for p in files:
        print(f"  {p.name}")
    print()

    print(f"Creating vector store: {VECTOR_STORE_NAME}")
    vector_store = client.vector_stores.create(name=VECTOR_STORE_NAME)
    print(f"Vector store ID: {vector_store.id}")
    print()

    ok = 0
    failed = 0
    for path in files:
        print(f"Uploading: {path.name} ...", end=" ", flush=True)
        try:
            with path.open("rb") as f:
                result = client.vector_stores.files.upload_and_poll(
                    vector_store_id=vector_store.id,
                    file=f,
                )
            print(result.status)
            ok += 1
        except Exception as exc:
            print(f"FAILED: {exc}")
            failed += 1

    print()
    print(f"Done. {ok} uploaded, {failed} failed.")
    print(f"OPENAI_VECTOR_STORE_ID={vector_store.id}")
    print()

    update_env(vector_store.id)
    print()
    print("Run 'source ~/.zshrc' or re-enter the mq-mcp dir to pick up the new ID.")


if __name__ == "__main__":
    main()

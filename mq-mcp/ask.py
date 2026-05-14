#!/usr/bin/env python3
"""
Ask questions using OpenAI vector stores.

Usage:
  uv run python ask.py "What does server.py do?"
  uv run python ask.py -m gpt-5.5 "Deep review of bridge.py"
  uv run python ask.py -g "How do all my repos relate?"   # global memory only
"""

import os
import random
import sys
import time

from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID", "")
SEMANTIC_MEMORY_ID = os.getenv("OPENAI_SEMANTIC_MEMORY_ID", "")

SYSTEM_LOCAL = """You are a repo-aware assistant for the mq-mcp repository.
Always search the repository knowledge base before answering. Base your answers on what you find there.
Prefer concrete file paths, commands, and short practical answers.
If you find relevant information, cite it. If nothing is found, say so briefly and give a best-effort answer.
Answer in the same language as the question."""

SYSTEM_GLOBAL = """You are a repo-aware assistant with access to the full project memory for MCamner's repos.
Repos covered: mq-mcp, repo-signal, macos-scripts, atlas-one, atlas-loop, mcamner-journal, coolThing, zephyr-workbench.
Always search the knowledge base before answering. Prefer concrete file paths, commands, and short practical answers.
If you find relevant information, cite which repo and file it came from.
Answer in the same language as the question."""

_SCRAMBLE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!?#@%&"


def scramble_print(text: str) -> None:
    for ch in text:
        if ch in (" ", "\n", "\t"):
            sys.stdout.write(ch)
            sys.stdout.flush()
            continue
        for _ in range(3):
            sys.stdout.write(random.choice(_SCRAMBLE_CHARS) + "\b")
            sys.stdout.flush()
            time.sleep(0.008)
        sys.stdout.write(ch)
        sys.stdout.flush()
    sys.stdout.write("\n")
    sys.stdout.flush()


def run_ask(prompt: str, model: str = MODEL, global_only: bool = False) -> None:
    store_ids: list[str] = []

    if global_only:
        if not SEMANTIC_MEMORY_ID:
            print("ERROR: OPENAI_SEMANTIC_MEMORY_ID not set in environment")
            raise SystemExit(1)
        store_ids = [SEMANTIC_MEMORY_ID]
        system = SYSTEM_GLOBAL
        label = "global memory"
    else:
        if not VECTOR_STORE_ID:
            print("ERROR: OPENAI_VECTOR_STORE_ID not set in environment")
            raise SystemExit(1)
        store_ids = [VECTOR_STORE_ID]
        if SEMANTIC_MEMORY_ID:
            store_ids.append(SEMANTIC_MEMORY_ID)
        system = SYSTEM_LOCAL
        label = "local + global" if SEMANTIC_MEMORY_ID else "local"

    client = OpenAI()

    print(f"--- ask [{label}] ---")
    print(f"Model: {model}")
    print(f"Prompt: {prompt}\n")

    response = client.responses.create(
        model=model,
        instructions=system,
        input=prompt,
        tools=[{
            "type": "file_search",
            "vector_store_ids": store_ids,
        }],
    )

    sys.stdout.write("Bridget: ")
    sys.stdout.flush()
    scramble_print(response.output_text)


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]

    argv = sys.argv[1:]

    if not argv or argv[0] in {"-h", "--help"}:
        print('Usage: uv run python ask.py [-g] [-m model] "your question"')
        print('  -g / --global   search global semantic memory only')
        raise SystemExit(0)

    model = MODEL
    if argv[0] in {"-m", "--model"} and len(argv) >= 2:
        model = argv[1]
        argv = argv[2:]

    global_only = False
    if argv and argv[0] in {"-g", "--global"}:
        global_only = True
        argv = argv[1:]

    prompt = " ".join(argv)
    if not prompt:
        print("ERROR: no prompt given.")
        raise SystemExit(1)

    run_ask(prompt, model, global_only=global_only)


if __name__ == "__main__":
    main()

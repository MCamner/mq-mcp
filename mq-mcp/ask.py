#!/usr/bin/env python3
"""
Ask questions about the mq-mcp project using the OpenAI vector store.

Usage:
  uv run python ask.py "What does server.py do?"
  uv run python ask.py "Which tools are read-only?"
"""

import os
import random
import sys
import time

from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID", "")

SYSTEM = """You are a repo-aware assistant for the mq-mcp repository.
Always search the repository knowledge base before answering. Base your answers on what you find there.
Prefer concrete file paths, commands, and short practical answers.
If you find relevant information, cite it. If nothing is found, say so briefly and give a best-effort answer.
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


def run_ask(prompt: str, model: str = MODEL) -> None:
    if not VECTOR_STORE_ID:
        print("ERROR: OPENAI_VECTOR_STORE_ID not set in environment")
        raise SystemExit(1)

    client = OpenAI()

    print("--- mq-mcp ask ---")
    print(f"Model: {model}")
    print(f"Prompt: {prompt}\n")

    response = client.responses.create(
        model=model,
        instructions=SYSTEM,
        input=prompt,
        tools=[{
            "type": "file_search",
            "vector_store_ids": [VECTOR_STORE_ID],
        }],
    )

    sys.stdout.write("Bridget: ")
    sys.stdout.flush()
    scramble_print(response.output_text)


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]

    argv = sys.argv[1:]

    if not argv or argv[0] in {"-h", "--help"}:
        print('Usage: uv run python ask.py "your question about mq-mcp"')
        raise SystemExit(0)

    model = MODEL
    if argv[0] in {"-m", "--model"} and len(argv) >= 2:
        model = argv[1]
        argv = argv[2:]

    prompt = " ".join(argv)
    if not prompt:
        print('ERROR: no prompt given.')
        raise SystemExit(1)

    run_ask(prompt, model)


if __name__ == "__main__":
    main()

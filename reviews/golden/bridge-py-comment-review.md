# Golden Review: mq-mcp/bridge.py — Comment Mode

This is a reference example of a high-quality comment review.
It demonstrates correct severity labeling, precise line citations,
and the expected tone and depth.

---

## Review output

```
[MISSING] mq-mcp/bridge.py:76
scramble_print has no docstring. The function has a non-obvious side effect:
it animates each character to stdout (or a given file handle) with randomized
intermediate characters and backspace sequences. The `file` parameter and its
fallback to sys.stdout should be documented.

[MISSING] mq-mcp/bridge.py:110
parse_prompt has no docstring explaining the return tuple. The 5-tuple
(prompt, list_tools_only, model, search, search_global) has purely positional
semantics — the caller must destructure all five to use any of them.

[MISSING] mq-mcp/bridge.py:146
tool_catalog_text has no docstring. It is called in run_bridge to build the
system prompt — its role in the request pipeline is non-obvious from the name alone.

[MISSING] mq-mcp/bridge.py:192
call_mcp_tool has no docstring. It has a notable implicit side effect:
it prints "-> MCP tool call: {name}({args})" to stdout unconditionally.
This should be documented so callers know it is also a logging statement.

[MISSING] mq-mcp/bridge.py:372
run_bridge has no docstring. It is the main async entry point and orchestrates
the full MCP ↔ OpenAI bridge pipeline. Its lifecycle — connect, discover tools,
send prompt, dispatch tool calls, return final response — deserves a summary.

[WARNING] mq-mcp/bridge.py:270
show_bridget_face opens /dev/tty at line 275 but does not use a try/finally
block. If an exception is raised between the open() and tty.close() at line 298,
the file handle leaks. Use try/finally or a context manager to guarantee closure.

[WARNING] mq-mcp/bridge.py:44
_last_bridget_image is mutable module-level state that persists for the life of
the process. This is intentional (anti-repeat image selection) but undocumented.
A comment explaining why global state is used here would prevent future readers
from treating it as an accidental global.

[SUGGESTION] mq-mcp/bridge.py:302
known_local_repos imports Path as _Path inside the function body, but Path is
already imported at module level (line 10). The alias adds no value and creates
the impression of a deliberate shadowing. Remove the local import.

[SUGGESTION] mq-mcp/bridge.py:110
parse_prompt returns a 5-tuple with positional semantics. The return type
annotation tuple[str, bool, str, bool, bool] gives no indication of what each
position means. A short docstring naming the five fields would eliminate the
need to read the function body at every call site.

[NOTE] mq-mcp/bridge.py:339
The inline comment "Shell wrapper reads this prefix and runs cd itself. / A
subprocess cannot cd in the parent shell directly." correctly explains a
non-obvious constraint. This comment is valuable and should not be removed.

[NOTE] mq-mcp/bridge.py:28
SYSTEM_PROMPT contains the string "Du är världens smartaste Calzone :)" — a
hardcoded personal greeting. This is clearly intentional for the current user
but is worth noting as persona that would need adjustment in any other deployment.

[NOTE] mq-mcp/bridge.py:235
choose_bridget_image uses a global statement to update _last_bridget_image.
This is the only global mutation in the file. The behavior (avoid repeating the
last shown image) is correct and intentional; a docstring line would make it
self-evident without requiring readers to trace the global declaration.
```

---

## Why this review is correct

These notes illustrate the reasoning behind each finding.
They are not part of the review output — they explain the standard.

**scramble_print (line 76):** The function writes escape sequences
(`\b` backspace) directly to the output stream. This is invisible from
the function name. The `file` parameter accepting `Any` is also worth
naming — the caller must pass a file-like object, not a string.

**parse_prompt return tuple (line 110):** A 5-tuple with `bool` in
positions 1, 3, and 4 is indistinguishable without reading the function.
A dataclass would solve this structurally; a docstring is the minimum.

**call_mcp_tool stdout side effect (line 192):** The `print(f"-> MCP
tool call: ...")` statement makes this function produce observable output
even when the caller only expects a return value. This is intentional UX
but surprises readers who expect pure function behavior.

**tty handle leak (line 270):** The pattern is:
```python
tty = open("/dev/tty", "w")
...
tty.close()
```
If any exception occurs between open and close, the handle is never
closed. In practice the exception paths here (image rendering failures)
are all caught, but the structure is fragile. The correct pattern is:
```python
try:
    ...
finally:
    if tty:
        tty.close()
```

**known_local_repos internal import (line 302):** `from pathlib import
Path as _Path` inside the function body shadows the module-level `Path`
import needlessly. It was likely added to avoid a perceived name conflict
but there is none.

**The CD: comment (line 339):** This is an example of a WHY comment that
should stay. It explains a real constraint (subprocess cannot cd in parent
shell) that would not be obvious to a reader unfamiliar with how shell
wrappers work.

---

## What was deliberately excluded

- Cosmetic whitespace (double blank line at line 342)
- Functions with no public-facing callers and obvious names
  (`is_goto_repo_prompt`, `is_bridget_face_prompt`)
- The `BRIDGET_LOCAL_LINES` list content — it is data, not documentation
- The `cast()` calls in `run_bridge` — they are a known limitation
  of the OpenAI SDK type stubs, not a documentation issue

---

## Metadata

```
file: mq-mcp/bridge.py
mode: comment
contract: comment-review v1.0
skill: python-comment-review
findings: 12
severity-distribution: MISSING=5, WARNING=2, SUGGESTION=2, NOTE=3
```

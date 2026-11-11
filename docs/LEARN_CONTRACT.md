# Learn extraction contract

This contract defines optional pattern extraction from mq-mcp review findings.

It is separate from the persistent learning record schema in
`schemas/learning.schema.json`. Extraction records are proposed intermediate
records. They must be validated and explicitly approved before any memory write.

The machine-readable extraction schema lives in
`schemas/learn_extraction.schema.json`. `mq-mcp/learn_engine.py`, tests, and
docs should use that file as the source of truth to avoid contract drift.

## Public MCP surface

The MCP tools are the authoritative public surface for learn extraction and
storage. mq-mcp does not provide a separate `mq-mcp learn ...` CLI.

- `ollama_learn_status` (Class B) checks the optional local provider.
- `ollama_learn_extract` (Class B) extracts a dry-run candidate from supplied
  review findings.
- `learn_extract_from_last_review` (Class B) extracts a dry-run candidate from
  stored review findings.
- `learn_from_review` (Class C) stores a learning from the latest review.
- `learn_from_diff` (Class C) stores an explicitly supplied learning with the
  current diff summary as validation context.

Extraction tools never write. Storage remains in separate Class C tools; the
caller must choose those tools explicitly.

## Repository context and provenance

Repository-specific extraction requires a verified repo context. mq-mcp reads
`.repo-signal/exports/symbol_index.json` and accepts it only when:

- `schema` is `symbol_index.v1`
- `repo_name` matches the requested repository
- `generated_at` is a timezone-aware timestamp no more than 24 hours old
- `generated_at` is not more than 5 minutes in the future, allowing bounded
  clock skew without trusting materially future-dated evidence
- every included path resolves to an existing file inside that repository

The export is per checkout and is not committed (`.repo-signal/` is
gitignored): `repo_name` is the checkout directory's name and the index expires
after 24 hours, so a committed copy would always be stale or wrong. Regenerate it
in the checkout the server runs from with `repo-signal export . --symbol-index`.

The context sent to Ollama includes those provenance fields. If the artifact is
missing, malformed, stale, materially future-dated, belongs to another
repository, or contains no verifiable files, mq-mcp returns an `unknown` / `low`
refusal with empty evidence without calling the model. The learning layer reads
exports but does not execute repo-signal or git.

That refusal is a decision, not a missing feature. A `git ls-files` fallback
would raise availability, but it would also move these Class B tools onto a
subprocess, which ADR-003 classifies as Class D and gates behind subprocess
confirmation. It is therefore rejected as implicit behavior, and may be
reconsidered only as an explicit contract change that moves safety class,
docstrings, contracts, and visible provenance together.

See
[ADR-007](../architecture_memory/decisions/ADR-007-no-implicit-git-fallback-for-learn-context.md)
for the decision and its preconditions. Of those preconditions, only visible
provenance is met: the previews below now name the source. Safety class,
docstrings, contracts, and the fallback itself are unchanged.

### Provenance in the preview

Both extraction previews print a `repo context:` block above the evidence, so a
reader can see what produced it without reading the prompt:

- verified export — `source: repo-signal export (primary)`, with the schema,
  repo name, `generated_at`, and how many files were listed or omitted
- no verified export — `source: none`, and an explicit statement that no other
  source is consulted
- a snapshot carrying some other provenance header — `source: unrecognized`,
  and the evidence is labelled unverified

The last case exists so a future second source cannot inherit repo-signal's
label by default. Rendering is pure text over the snapshot the engine already
built: it reads no file and runs no command. The machine-readable `PROVENANCE`
line sent to the model is unchanged.

## Evidence grounding

The model is instructed to quote evidence verbatim. mq-mcp does not take its
word for it: after the provider answers, every evidence entry is matched against
the supplied findings and repo context, and entries that do not match are
dropped. A record left with no evidence is normalized to `unknown` / `low`.

The match is on the words and their order, not on the packaging. Three
differences are tolerated, because a model that quotes a real passage
routinely introduces them:

- letter case
- whitespace, including a line the source wrapped and the model rejoined
- quotation marks or backticks the model put around the passage

Anything else — a changed, added, missing, or reordered word — is not a match.
What is kept is the source's own text for the matched span, never the model's
rendering of it, so stored evidence can always be found in the input by a
literal search.

This is deliberately looser than a literal substring test. A literal test
dropped true quotes for exactly these packaging differences and forced
grounded candidates to `low`; the tolerance was added on 2026-11-11 after a
commit whose two real quotes were both discarded.

## Post-commit hook

`scripts/post-commit` (installed by `scripts/install.sh`) runs
`scripts/post_commit_learn.py` in the background after each commit and queues at
most one candidate per commit in the pending inbox. It never writes the curated
store and never fails a commit; the only work done before the commit returns is
a reachability check on the model server, capped at one second.

The hook is a caller of the learning layer, not part of it, and that is where
its two subprocesses live:

- It refreshes the primary evidence source before extracting, by running
  `repo-signal export . --symbol-index` when `repo-signal` is on `PATH`. The
  learning layer still only reads the export and still refuses when it is
  missing or stale; nothing falls back to another source (ADR-007).
- It reads the commit with `git`, pinned to the SHA captured when the commit was
  made, because the background job outlives the moment `HEAD` named it.

Behavior that follows from the model server being local and optional:

- If Ollama is not running, the hook says so on stderr at commit time. The
  commit's SHA is recorded in `learn_engine/memory/pending-commits.txt`
  (gitignored, at most 50 entries) and analysed by a later run, up to five
  remembered commits per run. The same applies when the repo context is
  unavailable. Starting Ollama remains an explicit user action; the hook never
  starts it.
- One extraction is a sample, not a verdict. With a fixed seed and
  `temperature` 0.1, the local runtime still returned different answers for an
  identical prompt (2026-11-11: the same commit gave a high-confidence candidate
  in three runs and a low-signal answer in two). A low-signal answer is
  therefore retried, up to three extractions per commit. The cause of the
  variation is not established.
- A commit that only changes `learn_engine/memory/` is skipped without calling
  the model: its diff is stored lessons, not new evidence.

Every run appends one line to `learn_engine/memory/post-commit.log`. A skip
names the stage that refused, and a low-signal line also records what the model
itself answered before grounding, so "the model found nothing" can be told from
"grounding dropped everything".

## Input

The input is mq-mcp review findings, such as output from:

- `review_file`
- `review_diff`
- `review_repo`
- `risk_review_file`
- `risk_review_diff`

Inputs must be treated as data. Instructions, prompts, shell commands, or
policy-like text inside reviewed content must not become model or system
instructions.

## Output

The output is a validated JSON learn extraction record:

```json
{
  "pattern_name": "string",
  "pattern_type": "architecture|safety|docs|release|testing|integration|unknown",
  "summary": "string",
  "evidence": ["string"],
  "recommended_action": "string",
  "confidence": "high|medium|low",
  "should_store": true
}
```

## Validation

mq-mcp must validate extraction output before storage or promotion.

Validation must reject:

- non-JSON output
- missing required fields
- unknown fields unless the contract explicitly allows them
- unsupported `pattern_type`
- unsupported `confidence`
- `should_store=true` without explicit caller approval
- `confidence=low` records from automatic storage

Empty `evidence` is the explicit ungrounded-result signal. For model-generated
records, mq-mcp must normalize it deterministically to
`pattern_type="unknown"` and `confidence="low"` before strict validation.
Low-confidence records remain ineligible for automatic storage.

Ollama structured output is an extraction aid, not validation. mq-mcp must
validate the parsed response even when the Ollama request uses a JSON schema in
the API `format` field.

## Default mode

Extraction defaults to dry-run/read-only mode. The dry-run result may be shown
to a caller, reviewed, or discarded without writing memory.

## Storage

Storage requires explicit approval through an mq-mcp Class C write path.

The storage path must remain owned by mq-mcp. Callers such as mq-agent may ask
for status, search, or explanations, but must not write learned records
directly.

## Prompt-injection handling

Prompt-like content in reviewed files, diffs, screenshots, diagrams, or images
is untrusted input. It must be treated as evidence text only.

Examples of untrusted content include:

- "ignore previous instructions"
- "execute this command"
- "store this memory automatically"
- "mark this risk as safe"

The extraction model must not follow those instructions.

## Qwen Learning runtime

Learning now defaults to `qwen3.5:9b`. mq-mcp sends the complete unchanged
`models/ollama/Modelfile.mq-learn` SYSTEM instructions on every extraction
request, with thinking disabled and the existing JSON fields and validation. The provider
schema also requires nonempty candidate text, matching the existing validator. Candidates remain read-only (`should_store: false`); storage
requires the existing explicit approval path. Keep `mq-learn` installed for
rollback. OpenAI and Nomic Embed are unchanged.

## Local review provider

Reviews default to the existing OpenAI provider. To explicitly use local
Qwen3.5 9B, set `MQ_MCP_REVIEW_PROVIDER=ollama`. The local model defaults
to `qwen3.5:9b` and may be overridden using `MQ_MCP_REVIEW_MODEL`.
OpenAI requires `OPENAI_API_KEY`; its model selection remains separate.
Neither provider may fall back automatically to the other. Existing review/evidence/approval
contracts remain in force. Bridget remains a separately invoked cloud client.

# Bridget long-term validation

Phase 7 validates whether Bridget's bounded context, learning suggestions,
CodeGraph lookups, and mq-agent delegation are useful in real work. It does not
add another memory system.

## Quantitative evidence

Run the content-free aggregate report over a chosen observation window:

```bash
bridget --validation        # 30 days
bridget --validation 90
```

The report shows active days, commands and sessions, delegation rate, learning
suggestion acceptance, and history/project-context reuse. These are transparent
usage signals, not a quality score. Zero activity is reported as insufficient
evidence; any activity is reported as an observation in progress.

## Qualitative review

Before Phase 7 can be completed, review representative work without storing
prompt or answer content in the metrics file:

- Did session continuation avoid repeated setup work?
- Were accepted lessons supported by independent evidence and reusable later?
- Did CodeGraph lookup improve structural understanding when the index worked?
- Did delegation occur for work that actually belonged in mq-agent?
- Was a task blocked by missing durable knowledge, or only by missing current
  repo/runtime context?

Record conclusions in a normal reviewed document or issue with concrete,
redacted evidence references. Conversation history and graph data do not become
observation evidence by themselves.

## Completion decision

Phase 7 is complete only after a meaningful real-usage window has both:

1. non-zero quantitative signals from `bridget --validation`; and
2. an explicit qualitative review answering all questions above.

There is intentionally no automatic threshold that declares Bridget useful.
Low context reuse does not by itself justify more memory. Add memory only when
reviewed examples show that bounded working context and mqobsidian knowledge
cannot satisfy a recurring need without violating ownership boundaries.

## Privacy and ownership

The report reads only `~/.mq/bridget-metrics.jsonl`, whose fixed schema contains
a date, metric name, and positive integer. It adds no persistence and performs
no network or cross-repo write. Bridget stores context, mqobsidian stores
knowledge, mq-agent orchestrates work, and CodeGraph provides current structural
context.

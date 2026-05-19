# Bridget Voice

Bridget can speak responses locally on macOS using the built-in `say` command.

Disabled by default. No external TTS, no API cost.

## Commands

```bash
uv --directory mq-mcp run python bridge.py --voice-on
uv --directory mq-mcp run python bridge.py --voice-off
uv --directory mq-mcp run python bridge.py --voice-status
uv --directory mq-mcp run python bridge.py --voice-test
uv --directory mq-mcp run python bridge.py --voice-list
uv --directory mq-mcp run python bridge.py --voice-name Samantha
```

Or via the `bridget` shell alias (from `~/mq-mcp`):

```bash
bridget --voice-on
bridget --voice-test
bridget --voice-off
```

## List available voices

```bash
bridget --voice-list
```

Pick a voice from the list and set it:

```bash
bridget --voice-name Alva
```

## Environment overrides

| Variable | Description |
| --- | --- |
| `BRIDGET_VOICE_ENABLED` | `1` / `0` — override state file |
| `BRIDGET_VOICE_NAME` | Voice name — override name file |
| `BRIDGET_VOICE_MAX_CHARS` | Max characters before truncation (default 700) |
| `BRIDGET_VOICE_STATE_FILE` | Path to state file |
| `BRIDGET_VOICE_NAME_FILE` | Path to voice name file |

## Local state

Voice state is stored in `~/.mq-mcp/`:

```text
~/.mq-mcp/bridget_voice_enabled
~/.mq-mcp/bridget_voice_name
```

## Safety

- Voice is local-only — `say` is a macOS built-in.
- Code blocks are stripped before speech.
- Long answers are truncated before speech.
- Voice errors are silently suppressed and never break Bridget output.

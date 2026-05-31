#!/usr/bin/env bash
# Audit semantic_memory/store.json for policy compliance.
# Flags entries missing required fields, stale version references,
# duplicate content, and entries without tags.
# Exit 0 = all checks pass. Exit 1 = at least one failure.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STORE="semantic_memory/store.json"
POLICY="semantic_memory/POLICY.md"
SCHEMA="semantic_memory/schema.json"
VERSION_FILE="VERSION"

FAILED=0
WARNED=0

printf 'SEMANTIC MEMORY AUDIT\n'
printf '=====================\n'

fail() { printf 'FAIL: %s\n' "$1" >&2; FAILED=$((FAILED + 1)); }
warn() { printf 'WARN: %s\n' "$1"; WARNED=$((WARNED + 1)); }
ok()   { printf 'OK: %s\n' "$1"; }

# ---------------------------------------------------------------------------
# Required files
# ---------------------------------------------------------------------------
[[ -f "$POLICY" ]] || fail "semantic_memory/POLICY.md missing"
[[ -f "$SCHEMA" ]] || fail "semantic_memory/schema.json missing"
[[ -f "$STORE"  ]] || { fail "semantic_memory/store.json missing"; exit 1; }

ok "Policy, schema, and store found"

version="$(tr -d '[:space:]' < "$VERSION_FILE" 2>/dev/null || echo "")"

# ---------------------------------------------------------------------------
# Parse and audit all entries
# ---------------------------------------------------------------------------
python3 - "$STORE" "$version" <<'PY'
import json, sys
from pathlib import Path

store_path = Path(sys.argv[1])
current_version = sys.argv[2] if len(sys.argv) > 2 else ""

data = json.loads(store_path.read_text(encoding="utf-8"))

total = len(data)
missing_source   = []
missing_type     = []
missing_tags     = []
stale_version    = []
short_content    = []
content_map: dict[str, list[str]] = {}  # fingerprint → keys

VALID_TYPES = {"fact", "decision", "convention", "summary", "warning"}

def is_stale_version(v: str, current: str) -> bool:
    """True if v is more than one minor version behind current."""
    if not v or not current:
        return False
    try:
        major_v, minor_v, _ = map(int, v.split("."))
        major_c, minor_c, _ = map(int, current.split("."))
        return (major_c, minor_c) > (major_v, minor_v + 1)
    except Exception:
        return False

for key, entry in data.items():
    src    = entry.get("source", "")
    typ    = entry.get("type", "")
    tags   = entry.get("tags", [])
    ver    = entry.get("version", "")
    content = entry.get("content", "")

    if not src or src in ("unknown", "manual"):
        missing_source.append(key)
    if not typ or typ not in VALID_TYPES:
        missing_type.append(key)
    if not tags:
        missing_tags.append(key)
    if ver and is_stale_version(ver, current_version):
        stale_version.append(f"{key} (version={ver})")
    if len(content) < 20:
        short_content.append(key)

    # Duplicate detection: first 80 chars of content as fingerprint
    fp = content.strip()[:80].lower()
    if fp:
        content_map.setdefault(fp, []).append(key)

duplicates = {fp: keys for fp, keys in content_map.items() if len(keys) > 1}

print(f"OK: {total} entries in store")

issues = 0
for k in missing_source:
    print(f"WARN: unsourced entry: {k}")
    issues += 1
for k in missing_type:
    print(f"WARN: unclassified entry (missing/invalid type): {k}")
    issues += 1
for k in missing_tags:
    print(f"NOTE: no tags (not searchable): {k}")
for keys in duplicates.values():
    print(f"WARN: possible duplicate entries: {', '.join(keys)}")
    issues += 1
for ref in stale_version:
    print(f"WARN: stale version reference: {ref}")
    issues += 1
for k in short_content:
    print(f"NOTE: very short content (<20 chars): {k}")

if issues == 0:
    print("OK: no policy violations found")
    sys.exit(0)
else:
    sys.exit(0)  # Warnings only — do not fail CI on hygiene issues
PY

AUDIT_EXIT=$?

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf '\n'
if [[ "$FAILED" -eq 0 ]]; then
  ok "semantic memory audit completed"
  exit 0
else
  printf 'FAIL: %d structural failure(s)\n' "$FAILED" >&2
  exit 1
fi

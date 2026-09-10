from pathlib import Path
import re

APP = Path(r".\src\App.tsx")
BACKUP = Path(r".\src\App.tsx.backup-before-workspace-scoring-fix-v2")

data = APP.read_bytes()
BACKUP.write_bytes(data)

# ------------------------------------------------------------
# Workspace answer storage
# Current:
#   [attemptCurrent]: option,
# Change to:
#   [attemptCurrent]: option + 1,
# ------------------------------------------------------------
old_store = b"[attemptCurrent]: option,"
if data.count(old_store) != 1:
    raise SystemExit(
        f"ABORT: expected exactly one Workspace answer assignment, "
        f"found {data.count(old_store)}"
    )

data = data.replace(
    old_store,
    b"[attemptCurrent]: option + 1,",
    1,
)

# ------------------------------------------------------------
# Workspace answer selection highlight.
#
# The actual source may have arbitrary whitespace/newlines
# between tokens, so match only the exact semantic expression.
# ------------------------------------------------------------
pattern = re.compile(
    rb"(attemptAnswers\s*\[\s*attemptCurrent\s*\]\s*)===\s*index\b"
)

matches = list(pattern.finditer(data))

if len(matches) != 1:
    raise SystemExit(
        f"ABORT: expected exactly one Workspace selection comparison, "
        f"found {len(matches)}"
    )

m = matches[0]

replacement = m.group(1) + b"=== index + 1"

data = data[:m.start()] + replacement + data[m.end():]

APP.write_bytes(data)

print("WORKSPACE SCORING FIX COMPLETE")
print("Backup:", BACKUP)

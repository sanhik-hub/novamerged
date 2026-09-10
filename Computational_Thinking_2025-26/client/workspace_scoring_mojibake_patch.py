from pathlib import Path

APP = Path(r".\src\App.tsx")

BACKUP = Path(r".\src\App.tsx.backup-before-workspace-scoring-fix")

data = APP.read_bytes()
BACKUP.write_bytes(data)

replacements = [
    # Workspace attempt selection: store 1-based answer numbers.
    (
        b'[attemptCurrent]: option,',
        b'[attemptCurrent]: option + 1,',
    ),

    # Workspace attempt selection highlight: compare against 1-based answer.
    (
        b'attemptAnswers[\n                                attemptCurrent\n                              ] === index;',
        b'attemptAnswers[\n                                attemptCurrent\n                              ] === index + 1;',
    ),

    # Workspace solution answer highlighting is also 1-based.
    (
        b'index ===\n                              solveResponse.user_question\n                                .correct_option',
        b'index + 1 ===\n                              solveResponse.user_question\n                                .correct_option',
    ),
    (
        b'index ===\n                                        item.correct_option',
        b'index + 1 ===\n                                        item.correct_option',
    ),

    # Visible provider/status text.
    (
        b'Gemini Online Solver',
        b'Online Solver',
    ),
    (
        b'Solve with Gemini',
        b'Solve',
    ),
    (
        b'Gemini \xc3\x82\xc2\xb7 Online',
        b'Online Solver',
    ),
    (
        b'GEMINI \xc3\x82\xc2\xb7 GUIDED ATTEMPT',
        b'GUIDED ATTEMPT',
    ),

    # Visible mojibake close/check symbols.
    (
        b'\xc3\x83\xc3\xa2\xe2\x80\x94',
        b'X',
    ),
    (
        b'\xc3\xa2\xc3\x85\xe2\x80\x9c\xc3\xa2\xe2\x80\x9e',
        b'\\u2713',
    ),
]

counts = {}

for old, new in replacements:
    count = data.count(old)
    counts[old] = count

    if count:
        data = data.replace(old, new)

# The critical scoring change MUST have happened exactly once.
if counts[b'[attemptCurrent]: option,'] != 1:
    raise SystemExit(
        "ABORT: expected exactly one Workspace attempt answer assignment, "
        f"found {counts[b'[attemptCurrent]: option,']}"
    )

if counts[
    b'attemptAnswers[\n                                attemptCurrent\n                              ] === index;'
] != 1:
    raise SystemExit(
        "ABORT: expected exactly one Workspace attempt selection comparison, "
        f"found {counts[b'attemptAnswers[\n                                attemptCurrent\n                              ] === index;']}"
    )

if data == APP.read_bytes():
    raise SystemExit("ABORT: no changes were made")

APP.write_bytes(data)

print("WORKSPACE SCORING + MOJIBAKE PATCH COMPLETE")
print("Backup:", BACKUP)

for old, count in counts.items():
    if count:
        print("Replaced:", count)

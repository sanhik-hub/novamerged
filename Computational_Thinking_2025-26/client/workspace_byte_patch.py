from pathlib import Path

app = Path(r".\src\App.tsx")
css = Path(r".\src\App.css")

app_backup = Path(r".\src\App.tsx.backup-before-workspace-byte-patch")
css_backup = Path(r".\src\App.css.backup-before-workspace-byte-patch")

app_bytes = app.read_bytes()
css_bytes = css.read_bytes()

app_backup.write_bytes(app_bytes)
css_backup.write_bytes(css_bytes)

lines = app_bytes.splitlines(keepends=True)

out = []
in_question_prompt = False
in_meta = False
meta_found = 0
math_open = False
question_math_found = False
removed_attempt_permission = 0

for raw in lines:
    stripped = raw.strip()

    if stripped == b'<div className="workspace-question-prompt">':
        in_question_prompt = True
        out.append(raw)
        continue

    if in_question_prompt and stripped == b'<div className="workspace-detail-meta">':
        in_meta = True
        meta_found += 1
        continue

    if in_meta:
        if stripped == b'</div>':
            in_meta = False
        continue

    if in_question_prompt and stripped == b'<MathText>':
        indent = raw[:len(raw) - len(raw.lstrip())]
        out.append(indent + b'<div className="workspace-question-plain-text">' + raw[len(raw.rstrip(b"\r\n")):])
        math_open = True
        question_math_found = True
        continue

    if in_question_prompt and math_open and stripped == b'</MathText>':
        indent = raw[:len(raw) - len(raw.lstrip())]
        ending = raw[len(raw.rstrip(b"\r\n")):]
        out.append(indent + b'</div>' + ending)
        math_open = False
        in_question_prompt = False
        continue

    if stripped == b'className="workspace-attempt-optionsworkspace-v4-attempt-options"':
        indent = raw[:len(raw) - len(raw.lstrip())]
        ending = raw[len(raw.rstrip(b"\r\n")):]
        out.append(indent + b'className="workspace-v4-attempt-options"' + ending)
        continue

    if stripped == b'!canSolve':
        removed_attempt_permission += 1
        continue

    # Online-only frontend default.
    if (
        b'const [mode, setMode] = useState<"offline" | "online">' in raw
        and b'computation_mode' in raw
    ):
        indent = raw[:len(raw) - len(raw.lstrip())]
        ending = raw[len(raw.rstrip(b"\r\n")):]
        out.append(
            indent
            + b'const [mode, setMode] = useState<"offline" | "online">("online");'
            + ending
        )
        continue

    if stripped.startswith(b'setMode(settings?.computation_mode === "online"'):
        indent = raw[:len(raw) - len(raw.lstrip())]
        ending = raw[len(raw.rstrip(b"\r\n")):]
        out.append(indent + b'setMode("online");' + ending)
        continue

    # Remove the offline frontend choice.
    if stripped == b'<option value="offline">Offline</option>':
        continue

    raw = raw.replace(
        b'with Gemini-powered solving and guided attempts.',
        b'with online solving and guided attempts.'
    )
    raw = raw.replace(
        b'Pick a question, solve it with Gemini,',
        b'Pick a question, solve it online,'
    )
    raw = raw.replace(
        b'Gemini Online Solver',
        b'Online Solver'
    )
    raw = raw.replace(
        b'Solve with Gemini',
        b'Solve'
    )
    raw = raw.replace(
        b'GEMINI SOLUTION',
        b'SOLUTION'
    )
    raw = raw.replace(
        b'Gemini generated these guided',
        b'Generated guided'
    )
    raw = raw.replace(
        b'GEMINI',
        b'ONLINE'
    )

    out.append(raw)

if meta_found != 1:
    raise SystemExit(f"ABORT: expected 1 workspace question metadata block, found {meta_found}")

if not question_math_found:
    raise SystemExit("ABORT: workspace question MathText block was not found")

if removed_attempt_permission != 1:
    raise SystemExit(
        f"ABORT: expected exactly 1 standalone !canSolve in Start Attempt disabled state, found {removed_attempt_permission}"
    )

new_app = b"".join(out)

if new_app == app_bytes:
    raise SystemExit("ABORT: App.tsx did not change")

# Append CSS without altering existing bytes.
css_marker = b"NOVA WORKSPACE BYTE-SAFE FINAL OVERRIDES"

if css_marker not in css_bytes:
    ending = b"" if css_bytes.endswith(b"\n") else b"\n"
    css_patch = (
        ending
        + b"\n/* "
        + css_marker
        + b" */\n"
        + b".workspace-question-plain-text {\n"
        + b"  margin-top: 18px;\n"
        + b"  color: #edf3ff !important;\n"
        + b"  font-size: 19px;\n"
        + b"  line-height: 1.75;\n"
        + b"  white-space: pre-wrap;\n"
        + b"  overflow-wrap: anywhere;\n"
        + b"  word-break: normal;\n"
        + b"}\n"
        + b"\n"
        + b".workspace-question-prompt {\n"
        + b"  text-align: left;\n"
        + b"}\n"
        + b"\n"
        + b".workspace-v4-attempt-options {\n"
        + b"  display: flex !important;\n"
        + b"  flex-direction: column !important;\n"
        + b"  align-items: stretch !important;\n"
        + b"  gap: 12px !important;\n"
        + b"  width: 100% !important;\n"
        + b"  box-sizing: border-box !important;\n"
        + b"}\n"
        + b"\n"
        + b".workspace-v4-attempt-options > button {\n"
        + b"  width: 100% !important;\n"
        + b"  box-sizing: border-box !important;\n"
        + b"  min-width: 0 !important;\n"
        + b"  min-height: 72px !important;\n"
        + b"  align-self: stretch !important;\n"
        + b"}\n"
        + b"\n"
        + b".workspace-option-content {\n"
        + b"  min-width: 0 !important;\n"
        + b"  max-width: none !important;\n"
        + b"  overflow-wrap: anywhere !important;\n"
        + b"  word-break: normal !important;\n"
        + b"  white-space: normal !important;\n"
        + b"}\n"
        + b"\n"
        + b".workspace-option-content .katex,\n"
        + b".workspace-option-content .katex-display {\n"
        + b"  max-width: 100% !important;\n"
        + b"  overflow-x: auto !important;\n"
        + b"}\n"
    )
    new_css = css_bytes + css_patch
else:
    new_css = css_bytes

css_backup.write_bytes(css_bytes)
app.write_bytes(new_app)
css.write_bytes(new_css)

print("BYTE-SAFE WORKSPACE PATCH COMPLETE")
print(f"App backup: {app_backup}")
print(f"CSS backup: {css_backup}")

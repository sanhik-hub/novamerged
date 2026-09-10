from pathlib import Path

APP = Path(r".\src\App.tsx")
CSS = Path(r".\src\App.css")

APP_BACKUP = Path(r".\src\App.tsx.backup-before-workspace-byte-patch-v2")
CSS_BACKUP = Path(r".\src\App.css.backup-before-workspace-byte-patch-v2")

app = APP.read_bytes()
css = CSS.read_bytes()

APP_BACKUP.write_bytes(app)
CSS_BACKUP.write_bytes(css)

lines = app.splitlines(keepends=True)
out = []

meta_removed = False
question_math_replaced = False
attempt_disabled_fixed = False
attempt_guard_preserved = False
mcq_class_fixed = False

i = 0

while i < len(lines):
    raw = lines[i]
    stripped = raw.strip()

    # Preserve the createAttempt permission guard.
    if stripped == b"!canSolve" and i >= 1:
        previous = lines[i - 1].strip()
        if previous == b"!selectedQuestion?.id ||":
            out.append(raw)
            attempt_guard_preserved = True
            i += 1
            continue

    # Remove only the metadata block inside the Workspace question prompt.
    if stripped == b'<div className="workspace-detail-meta">':
        depth = 1
        i += 1
        while i < len(lines) and depth > 0:
            current = lines[i].strip()
            if current.startswith(b"<div"):
                depth += 1
            if current == b"</div>":
                depth -= 1
            i += 1
        meta_removed = True
        continue

    # Replace ONLY the Workspace question MathText wrapper.
    if stripped == b"<MathText>" and i >= 1:
        previous = lines[i - 1].strip()
        if previous == b"<div className=\"workspace-question-prompt\">":
            # This case is defensive; normally metadata exists between them.
            indent = raw[:len(raw) - len(raw.lstrip())]
            ending = raw[len(raw.rstrip(b"\r\n")):]
            out.append(indent + b'<div className="workspace-question-plain-text">' + ending)
            i += 1

            while i < len(lines) and lines[i].strip() != b"</MathText>":
                out.append(lines[i])
                i += 1

            if i >= len(lines):
                raise SystemExit("ABORT: question MathText closing tag not found")

            close = lines[i]
            close_indent = close[:len(close) - len(close.lstrip())]
            close_ending = close[len(close.rstrip(b"\r\n")):]
            out.append(close_indent + b"</div>" + close_ending)
            question_math_replaced = True
            i += 1
            continue

    # More reliable question MathText replacement: detect the exact indentation
    # and selectedQuestion.question expression.
    if stripped == b"<MathText>" and i + 2 < len(lines):
        if b"selectedQuestion.question" in lines[i + 1]:
            indent = raw[:len(raw) - len(raw.lstrip())]
            ending = raw[len(raw.rstrip(b"\r\n")):]
            out.append(indent + b'<div className="workspace-question-plain-text">' + ending)
            out.append(lines[i + 1])
            i += 2

            if lines[i].strip() != b"</MathText>":
                raise SystemExit("ABORT: expected workspace question MathText closing tag")

            close = lines[i]
            close_indent = close[:len(close) - len(close.lstrip())]
            close_ending = close[len(close.rstrip(b"\r\n")):]
            out.append(close_indent + b"</div>" + close_ending)
            question_math_replaced = True
            i += 1
            continue

    # Fix the malformed MCQ class exactly.
    if stripped == b'className="workspace-attempt-optionsworkspace-v4-attempt-options"':
        indent = raw[:len(raw) - len(raw.lstrip())]
        ending = raw[len(raw.rstrip(b"\r\n")):]
        out.append(indent + b'className="workspace-v4-attempt-options"' + ending)
        mcq_class_fixed = True
        i += 1
        continue

    # Remove !canSolve ONLY from the Start Attempt disabled block.
    if (
        stripped == b"!canSolve"
        and i >= 3
        and any(b"onClick={() => void" in lines[j] and b"createAttempt" in lines[j]
                for j in range(max(0, i - 6), i))
    ):
        attempt_disabled_fixed = True
        i += 1
        continue

    raw2 = raw

    # Visible labels only.
    raw2 = raw2.replace(
        b"with Gemini-powered solving and guided attempts.",
        b"with online solving and guided attempts."
    )
    raw2 = raw2.replace(
        b"Pick a question, solve it with Gemini,",
        b"Pick a question, solve it online,"
    )
    raw2 = raw2.replace(
        b"Gemini Online Solver",
        b"Online Solver"
    )
    raw2 = raw2.replace(
        b'Solve with Gemini',
        b'Solve'
    )
    raw2 = raw2.replace(
        b'GEMINI SOLUTION',
        b'SOLUTION'
    )
    raw2 = raw2.replace(
        b'Gemini generated these guided',
        b'Generated guided'
    )

    # Make the frontend online-only.
    if b'const [mode, setMode] = useState<"offline" | "online">' in raw2:
        indent = raw2[:len(raw2) - len(raw2.lstrip())]
        ending = raw2[len(raw2.rstrip(b"\r\n")):]
        out.append(
            indent +
            b'const [mode, setMode] = useState<"offline" | "online">("online");' +
            ending
        )
        i += 1
        continue

    if b'setMode(settings?.computation_mode === "online"' in raw2:
        indent = raw2[:len(raw2) - len(raw2.lstrip())]
        ending = raw2[len(raw2.rstrip(b"\r\n")):]
        out.append(indent + b'setMode("online");' + ending)
        i += 1
        continue

    if stripped == b'<option value="offline">Offline</option>':
        i += 1
        continue

    out.append(raw2)
    i += 1

if not meta_removed:
    raise SystemExit("ABORT: Workspace question metadata block not found")

if not question_math_replaced:
    raise SystemExit("ABORT: Workspace question MathText block not found")

if not attempt_guard_preserved:
    raise SystemExit("ABORT: createAttempt permission guard was not verified")

if not attempt_disabled_fixed:
    raise SystemExit("ABORT: Start Attempt disabled block was not found")

if not mcq_class_fixed:
    raise SystemExit("ABORT: malformed MCQ class was not found")

new_app = b"".join(out)

css_marker = b"NOVA WORKSPACE BYTE SAFE V2"

if css_marker not in css:
    ending = b"" if css.endswith(b"\n") else b"\n"

    css_patch = (
        ending +
        b"\n/* " + css_marker + b" */\n"
        b".workspace-question-plain-text {\n"
        b"  margin-top: 18px;\n"
        b"  color: #edf3ff !important;\n"
        b"  font-size: 19px;\n"
        b"  line-height: 1.75;\n"
        b"  white-space: pre-wrap;\n"
        b"  overflow-wrap: anywhere;\n"
        b"  word-break: normal;\n"
        b"}\n"
        b"\n"
        b".workspace-v4-attempt-options {\n"
        b"  display: flex !important;\n"
        b"  flex-direction: column !important;\n"
        b"  align-items: stretch !important;\n"
        b"  gap: 12px !important;\n"
        b"  width: 100% !important;\n"
        b"  box-sizing: border-box !important;\n"
        b"}\n"
        b"\n"
        b".workspace-v4-attempt-options > button {\n"
        b"  display: grid !important;\n"
        b"  grid-template-columns: 42px minmax(0, 1fr) 24px !important;\n"
        b"  width: 100% !important;\n"
        b"  min-width: 0 !important;\n"
        b"  min-height: 72px !important;\n"
        b"  box-sizing: border-box !important;\n"
        b"  align-self: stretch !important;\n"
        b"}\n"
        b"\n"
        b".workspace-option-content {\n"
        b"  min-width: 0 !important;\n"
        b"  max-width: 100% !important;\n"
        b"  overflow: hidden !important;\n"
        b"  overflow-wrap: anywhere !important;\n"
        b"  word-break: normal !important;\n"
        b"  white-space: normal !important;\n"
        b"}\n"
        b"\n"
        b".workspace-option-content .katex,\n"
        b".workspace-option-content .katex-display {\n"
        b"  max-width: 100% !important;\n"
        b"  overflow-x: auto !important;\n"
        b"}\n"
        b"\n"
        b".workspace-online-badge {\n"
        b"  font-size: 0 !important;\n"
        b"}\n"
        b"\n"
        b".workspace-online-badge::after {\n"
        b'  content: "Online";\n'
        b"  font-size: 11px;\n"
        b"}\n"
        b"\n"
        b".workspace-attempt-window-header .eyebrow {\n"
        b"  font-size: 0 !important;\n"
        b"}\n"
        b"\n"
        b".workspace-attempt-window-header .eyebrow::after {\n"
        b'  content: "GUIDED ATTEMPT";\n'
        b"  font-size: 10px;\n"
        b"  letter-spacing: .12em;\n"
        b"}\n"
    )

    new_css = css + css_patch
else:
    new_css = css

APP.write_bytes(new_app)
CSS.write_bytes(new_css)

print("WORKSPACE BYTE-SAFE V2 PATCH COMPLETE")
print("App backup:", APP_BACKUP)
print("CSS backup:", CSS_BACKUP)

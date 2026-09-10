from pathlib import Path
import re

APP = Path(r".\src\App.tsx")
CSS = Path(r".\src\App.css")

APP_BACKUP = Path(r".\src\App.tsx.backup-before-workspace-byte-patch-v3")
CSS_BACKUP = Path(r".\src\App.css.backup-before-workspace-byte-patch-v3")

app = APP.read_bytes()
css = CSS.read_bytes()

APP_BACKUP.write_bytes(app)
CSS_BACKUP.write_bytes(css)

original_app = app

# ------------------------------------------------------------
# 1. Remove ONLY the Workspace question metadata block.
# ------------------------------------------------------------
meta_pattern = re.compile(
    rb'(\s*)<div className="workspace-detail-meta">.*?\r?\n\s*</div>',
    re.S,
)

app, meta_count = meta_pattern.subn(b"", app, count=1)

if meta_count != 1:
    raise SystemExit(
        f"ABORT: expected exactly one workspace-detail-meta block, found {meta_count}"
    )

# ------------------------------------------------------------
# 2. Replace ONLY the Workspace question MathText wrapper.
# ------------------------------------------------------------
question_pattern = re.compile(
    rb'<MathText>\s*(\{\s*selectedQuestion\.question\s*\})\s*</MathText>',
    re.S,
)

app, question_count = question_pattern.subn(
    rb'<div className="workspace-question-plain-text">\n'
    rb'                  \1\n'
    rb'                </div>',
    app,
    count=1,
)

if question_count != 1:
    raise SystemExit(
        f"ABORT: expected exactly one Workspace selectedQuestion MathText block, found {question_count}"
    )

# ------------------------------------------------------------
# 3. Fix the MCQ container class.
# ------------------------------------------------------------
old_mcq = b'className="workspace-attempt-options workspace-v4-attempt-options"'
new_mcq = b'className="workspace-v4-attempt-options"'

if old_mcq not in app:
    raise SystemExit("ABORT: expected Workspace MCQ class was not found")

app = app.replace(old_mcq, new_mcq, 1)

# ------------------------------------------------------------
# 4. Remove !canSolve ONLY from the Start Attempt disabled
#    expression. Preserve the createAttempt() guard.
# ------------------------------------------------------------
button_pattern = re.compile(
    rb'(onClick=\{\(\) => void\s*createAttempt\(\)\}\s*'
    rb'disabled=\{\s*busy\s*\|\|\s*attemptLoading\s*\|\|\s*)!canSolve'
)

app, button_count = button_pattern.subn(rb'\1', app, count=1)

if button_count != 1:
    raise SystemExit(
        "ABORT: Start Attempt disabled expression was not found"
    )

# ------------------------------------------------------------
# 5. Visible Workspace provider labels only.
# ------------------------------------------------------------
visible_replacements = [
    (
        b"with Gemini-powered solving and guided attempts.",
        b"with online solving and guided attempts.",
    ),
    (
        b"Pick a question, solve it with Gemini,",
        b"Pick a question, solve it online,",
    ),
    (
        b"Gemini Online Solver",
        b"Online Solver",
    ),
    (
        b"Solve with Gemini",
        b"Solve",
    ),
    (
        b"GEMINI SOLUTION",
        b"SOLUTION",
    ),
    (
        b"Gemini generated these guided",
        b"Generated guided",
    ),
]

for old, new in visible_replacements:
    app = app.replace(old, new)

# ------------------------------------------------------------
# 6. Make Workspace frontend online-only.
# ------------------------------------------------------------
online_state_pattern = re.compile(
    rb'const \[mode, setMode\] = useState<"offline" \| "online">'
    rb'\(settings\?\.computation_mode === "online" \? "online" : "offline"\);'
)

app, state_count = online_state_pattern.subn(
    b'const [mode, setMode] = useState<"offline" | "online">("online");',
    app,
    count=1,
)

if state_count != 1:
    raise SystemExit(
        f"ABORT: Workspace mode state initializer not found, count={state_count}"
    )

sync_pattern = re.compile(
    rb'setMode\(settings\?\.computation_mode === "online" \? "online" : "offline"\);'
)

app, sync_count = sync_pattern.subn(
    b'setMode("online");',
    app,
    count=1,
)

if sync_count != 1:
    raise SystemExit(
        f"ABORT: Workspace mode sync initializer not found, count={sync_count}"
    )

offline_option = b'<option value="offline">Offline</option>'

if offline_option not in app:
    raise SystemExit("ABORT: Offline option not found")

app = app.replace(offline_option, b"", 1)

# ------------------------------------------------------------
# 7. Ensure required targets changed and the permission guard
#    still exists.
# ------------------------------------------------------------
if b'workspace-detail-meta' in app:
    raise SystemExit("ABORT: workspace metadata block still exists")

if b'className="workspace-attempt-options workspace-v4-attempt-options"' in app:
    raise SystemExit("ABORT: old MCQ class still exists")

if b'!canSolve' not in app:
    raise SystemExit("ABORT: createAttempt() permission guard disappeared")

if b'allow_member_solving' not in app:
    raise SystemExit("ABORT: admin solve-permission setting disappeared")

if b'<option value="offline">Offline</option>' in app:
    raise SystemExit("ABORT: offline option still exists")

if app == original_app:
    raise SystemExit("ABORT: App.tsx did not change")

# ------------------------------------------------------------
# 8. Append CSS overrides without rewriting existing CSS.
# ------------------------------------------------------------
marker = b"NOVA WORKSPACE BYTE SAFE V3"

if marker not in css:
    ending = b"" if css.endswith(b"\n") else b"\n"

    css += (
        ending +
        b"\n/* " + marker + b" */\n"
        b".workspace-question-plain-text {\n"
        b"  margin-top: 18px;\n"
        b"  width: 100%;\n"
        b"  box-sizing: border-box;\n"
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
        b"  width: 100% !important;\n"
        b"  gap: 12px !important;\n"
        b"  padding: 0 24px !important;\n"
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
        b".workspace-question-prompt .workspace-detail-meta {\n"
        b"  display: none !important;\n"
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

APP.write_bytes(app)
CSS.write_bytes(css)

print("WORKSPACE BYTE-SAFE V3 PATCH COMPLETE")
print("App backup:", APP_BACKUP)
print("CSS backup:", CSS_BACKUP)

from pathlib import Path
from datetime import datetime
import shutil
import sys

root = Path.cwd()
app = root / "client" / "src" / "App.tsx"
css = root / "client" / "src" / "App.css"

if not app.exists():
    print("ERROR: App.tsx not found:", app)
    sys.exit(1)

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = app.with_name(f"App.tsx.backup-before-workspace-guided-{stamp}")
shutil.copy2(app, backup)
print("Backup:", backup)

data = app.read_bytes()

def replace_once(old: str, new: str, label: str):
    global data
    old_b = old.encode("utf-8")
    new_b = new.encode("utf-8")
    count = data.count(old_b)
    if count != 1:
        print(f"ERROR: {label}: expected 1 match, found {count}")
        print("No further App.tsx changes will be made.")
        sys.exit(1)
    data = data.replace(old_b, new_b, 1)
    print("Patched:", label)

replace_once(
'''  createWorkspaceAttempt,
  getWorkspaceQuestionAttempts,''',
'''  createWorkspaceAttempt,
  completeWorkspaceAttempt,
  getWorkspaceQuestionAttempts,''',
"completeWorkspaceAttempt import",
)

replace_once(
'''  computeWorkspaceQuestion,
''',
''' ''',
"remove old provider compute import",
)

replace_once(
'''  const [followUp, setFollowUp] = useState("");
  const [computationProvider, setComputationProvider] = useState("wolfram");

  const [activeTab, setActiveTab] = useState<"dashboard" |"questions" | "members" | "invitations" | "settings">("dashboard");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");''',
'''  const [followUp, setFollowUp] = useState("");

  const [attemptQuestions, setAttemptQuestions] = useState<Question[]>([]);
  const [attemptAnswers, setAttemptAnswers] = useState<Record<number, number>>({});
  const [attemptCurrent, setAttemptCurrent] = useState(0);
  const [attemptShowHint, setAttemptShowHint] = useState(false);
  const [activeAttemptId, setActiveAttemptId] = useState<number | null>(null);
  const [attemptCompleted, setAttemptCompleted] = useState(false);
  const [attemptCorrect, setAttemptCorrect] = useState(0);
  const [attemptWrong, setAttemptWrong] = useState(0);
  const [attemptSolution, setAttemptSolution] = useState("");

  const [activeTab, setActiveTab] = useState<"dashboard" |"questions" | "members" | "invitations" | "settings">("dashboard");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");''',
"guided attempt state",
)

replace_once(
'''      setSelectedQuestion(null);
      setSolution(null);
      setAttempts([]);''',
'''      setSelectedQuestion(null);
      setSolution(null);
      setAttempts([]);
      setAttemptQuestions([]);
      setAttemptAnswers({});
      setAttemptCurrent(0);
      setAttemptShowHint(false);
      setActiveAttemptId(null);
      setAttemptCompleted(false);
      setAttemptCorrect(0);
      setAttemptWrong(0);
      setAttemptSolution("");''',
"reset guided attempt on workspace load",
)

replace_once(
'''  async function computeQuestion() {
    if (!selectedWorkspace?.id || !selectedQuestion?.id) return;

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const response = await computeWorkspaceQuestion({
        workspace_id: Number(selectedWorkspace.id),
        question_id: Number(selectedQuestion.id),
        operation: "compute",
        provider: computationProvider,
      });

      const result = response as WorkspaceSolution;
      setSolution(result);
      setMessage("Computation completed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Computation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createAttempt() {
    if (!selectedWorkspace?.id || !selectedQuestion?.id) return;

    setBusy(true);

    try {
      await createWorkspaceAttempt(Number(selectedWorkspace.id), Number(selectedQuestion.id), "solver", "");

      const response = await getWorkspaceQuestionAttempts(
        Number(selectedWorkspace.id),
        Number(selectedQuestion.id),
      );

      setAttempts(Array.isArray(response.data) ? response.data : []);
      setMessage("Attempt started.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start attempt.");
    } finally {
      setBusy(false);
    }
  }''',
'''  async function computeQuestion() {
    if (!selectedWorkspace?.id || !selectedQuestion?.id) return;

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const rawResponse = await postQuestion(
        user.username,
        selectedQuestion.question,
        selectedQuestion.image_path ?? "",
      );

      const response = validateQuestionResponse(rawResponse);

      if (!response || response.is_relevant !== true) {
        throw new Error(
          response?.error_message || "This question could not be solved.",
        );
      }

      const userQuestion = response.user_question;

      setSolution({
        workspace_question_id: Number(selectedQuestion.id),
        status: "completed",
        result_json: userQuestion.solution ?? userQuestion,
      });

      setMessage("Solution ready.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to solve the question.");
    } finally {
      setBusy(false);
    }
  }

  async function createAttempt() {
    if (!selectedWorkspace?.id || !selectedQuestion?.id) return;

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const attemptResponse = await createWorkspaceAttempt(
        Number(selectedWorkspace.id),
        Number(selectedQuestion.id),
        "guided",
        "",
      );

      const createdAttempt = attemptResponse.data as WorkspaceAttempt;

      if (createdAttempt?.id == null) {
        throw new Error("Unable to create the attempt.");
      }

      const rawResponse = await postQuestion(
        user.username,
        selectedQuestion.question,
        selectedQuestion.image_path ?? "",
      );

      const response = validateQuestionResponse(rawResponse);

      if (!response || response.is_relevant !== true) {
        throw new Error(
          response?.error_message || "Unable to prepare the guided attempt.",
        );
      }

      const guidedQuestions = Array.isArray(response.ai_questions)
        ? response.ai_questions.filter(
            (item) =>
              item &&
              typeof item.question === "string" &&
              Array.isArray(item.options) &&
              item.options.length === 4 &&
              typeof item.correct_option === "number" &&
              item.correct_option >= 1 &&
              item.correct_option <= 4,
          )
        : [];

      if (guidedQuestions.length === 0) {
        throw new Error("No guided questions were generated. Please try again.");
      }

      setActiveAttemptId(Number(createdAttempt.id));
      setAttemptQuestions(guidedQuestions);
      setAttemptAnswers({});
      setAttemptCurrent(0);
      setAttemptShowHint(false);
      setAttemptCompleted(false);
      setAttemptCorrect(0);
      setAttemptWrong(0);
      setAttemptSolution(response.user_question.solution ?? "");
      setMessage("Guided attempt started.");

      const attemptsResponse = await getWorkspaceQuestionAttempts(
        Number(selectedWorkspace.id),
        Number(selectedQuestion.id),
      );

      setAttempts(
        Array.isArray(attemptsResponse.data)
          ? attemptsResponse.data
          : [],
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start attempt.");
    } finally {
      setBusy(false);
    }
  }

  function chooseAttemptAnswer(option: number) {
    if (attemptCompleted) return;

    setAttemptAnswers((previous) => ({
      ...previous,
      [attemptCurrent]: option,
    }));
  }

  async function finishWorkspaceAttempt() {
    if (
      !selectedWorkspace?.id ||
      activeAttemptId == null ||
      attemptQuestions.length === 0
    ) {
      return;
    }

    const unanswered = attemptQuestions.some(
      (_question, index) => attemptAnswers[index] == null,
    );

    if (unanswered) {
      setError("Answer every guided question before finishing.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      const correct = attemptQuestions.reduce(
        (total, question, index) =>
          total +
          (attemptAnswers[index] === question.correct_option ? 1 : 0),
        0,
      );

      const wrong = attemptQuestions.length - correct;

      const result = {
        question_count: attemptQuestions.length,
        answers: attemptAnswers,
        correct,
        wrong,
        questions: attemptQuestions,
      };

      await completeWorkspaceAttempt(
        Number(selectedWorkspace.id),
        activeAttemptId,
        result,
        correct,
        true,
      );

      setAttemptCorrect(correct);
      setAttemptWrong(wrong);
      setAttemptCompleted(true);

      const attemptsResponse = await getWorkspaceQuestionAttempts(
        Number(selectedWorkspace.id),
        Number(selectedQuestion?.id),
      );

      setAttempts(
        Array.isArray(attemptsResponse.data)
          ? attemptsResponse.data
          : [],
      );

      setMessage("Attempt completed.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to complete the attempt.",
      );
    } finally {
      setBusy(false);
    }
  }

  function closeWorkspaceAttempt() {
    if (!attemptCompleted) return;

    setAttemptQuestions([]);
    setAttemptAnswers({});
    setAttemptCurrent(0);
    setAttemptShowHint(false);
    setActiveAttemptId(null);
    setAttemptSolution("");
  }''',
"guided attempt handlers",
)

replace_once(
'''                          <div className="workspace-compute-row">
                            <select
                              value={computationProvider}
                              onChange={(event) =>
                                setComputationProvider(event.target.value)
                              }
                            >
                              <option value="wolfram">Wolfram Engine</option>
                              <option value="sympy">SymPy</option>
                              <option value="local_llm">Local LLM</option>
                            </select>

                            <button
                              type="button"
                              className="primary"
                              onClick={() => void computeQuestion()}
                              disabled={busy}
                            >
                              Compute
                            </button>

                            <button
                              type="button"
                              className="secondary"
                              onClick={() => void createAttempt()}
                              disabled={busy}
                            >
                              Start Attempt
                            </button>
                          </div>''',
'''                          <div className="workspace-compute-row">
                            {canSolve && (
                              <button
                                type="button"
                                className="primary"
                                onClick={() => void computeQuestion()}
                                disabled={busy}
                              >
                                Solve
                              </button>
                            )}

                            <button
                              type="button"
                              className="secondary"
                              onClick={() => void createAttempt()}
                              disabled={busy}
                            >
                              Start Attempt
                            </button>
                          </div>''',
"generic solve controls",
)

replace_once(
'''                              <div className="workspace-solution-header">
                                <span className="eyebrow">Solution</span>
                                <span>
                                  {solution.engine ?? computationProvider} ?{" "}
                                  {solution.status ?? "completed"}
                                </span>
                              </div>''',
'''                              <div className="workspace-solution-header">
                                <span className="eyebrow">Solution</span>
                                <span>
                                  {solution.status ?? "completed"}
                                </span>
                              </div>''',
"generic solution header",
)

replace_once(
'''                          <div className="workspace-follow-up">
                            <h3>Ask a Follow-up</h3>
                            <textarea
                              value={followUp}
                              onChange={(event) => setFollowUp(event.target.value)}
                              placeholder="Ask about this problem, method or solution..."
                              rows={3}
                            />
                            <button
                              type="button"
                              className="secondary"
                              onClick={() => void sendFollowUp()}
                              disabled={busy || !followUp.trim()}
                            >
                              Ask Follow-up
                            </button>
                          </div>''',
'''                          <div className={`workspace-follow-up ${
                            !attemptCompleted ? "locked" : ""
                          }`}>
                            <h3>Ask a Follow-up</h3>

                            {!attemptCompleted ? (
                              <p className="workspace-follow-up-lock">
                                Complete a Start Attempt session to unlock follow-up questions.
                              </p>
                            ) : (
                              <>
                                <textarea
                                  value={followUp}
                                  onChange={(event) => setFollowUp(event.target.value)}
                                  placeholder="Ask about this problem, method or solution..."
                                  rows={3}
                                />
                                <button
                                  type="button"
                                  className="secondary"
                                  onClick={() => void sendFollowUp()}
                                  disabled={busy || !followUp.trim()}
                                >
                                  Ask Follow-up
                                </button>
                              </>
                            )}
                          </div>''',
"follow-up lock",
)

replace_once(
'''  const isAdmin =
    selectedWorkspace?.role === "owner" ||
    selectedWorkspace?.role === "admin";''',
'''  const isAdmin =
    selectedWorkspace?.role === "owner" ||
    selectedWorkspace?.role === "admin";

  const canSolve =
    isAdmin || settings?.allow_member_solving === true;''',
"solve permission",
)

replace_once(
'''      <div className="workspace-user">
        Signed in as <strong>{user.username}</strong>
      </div>
    </motion.div>''',
'''      {attemptQuestions.length > 0 && activeAttemptId != null && (
        <div className="workspace-attempt-overlay">
          <div
            className="workspace-attempt-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Guided attempt"
          >
            {!attemptCompleted ? (
              <>
                <div className="workspace-attempt-header">
                  <div>
                    <span className="eyebrow">Guided Attempt</span>
                    <h3>Build your understanding</h3>
                  </div>
                  <span className="workspace-attempt-progress">
                    {attemptCurrent + 1} / {attemptQuestions.length}
                  </span>
                </div>

                <div className="workspace-attempt-progress-bar">
                  <span
                    style={{
                      width: `${
                        ((attemptCurrent + 1) /
                          attemptQuestions.length) *
                        100
                      }%`,
                    }}
                  />
                </div>

                <div className="workspace-attempt-question">
                  {attemptQuestions[attemptCurrent]?.question}
                </div>

                <div className="workspace-attempt-options">
                  {attemptQuestions[attemptCurrent]?.options.map(
                    (option, index) => {
                      const number = index + 1;
                      const selected =
                        attemptAnswers[attemptCurrent] === number;

                      return (
                        <button
                          type="button"
                          key={`${attemptCurrent}-${number}`}
                          className={`workspace-attempt-option ${
                            selected ? "selected" : ""
                          }`}
                          onClick={() => chooseAttemptAnswer(number)}
                        >
                          <span className="workspace-attempt-option-label">
                            {String.fromCharCode(64 + number)}
                          </span>
                          <span>{option}</span>
                        </button>
                      );
                    },
                  )}
                </div>

                <div className="workspace-attempt-footer">
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      setAttemptShowHint((value) => !value)
                    }
                  >
                    {attemptShowHint ? "Hide Hint" : "Show Hint"}
                  </button>

                  <div className="workspace-attempt-actions">
                    {attemptCurrent > 0 && (
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => {
                          setAttemptCurrent((value) => value - 1);
                          setAttemptShowHint(false);
                        }}
                      >
                        Previous
                      </button>
                    )}

                    {attemptCurrent < attemptQuestions.length - 1 ? (
                      <button
                        type="button"
                        className="primary"
                        onClick={() => {
                          if (attemptAnswers[attemptCurrent] == null) {
                            setError("Choose an answer first.");
                            return;
                          }
                          setError("");
                          setAttemptCurrent((value) => value + 1);
                          setAttemptShowHint(false);
                        }}
                        disabled={busy}
                      >
                        Next
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="primary"
                        onClick={() => void finishWorkspaceAttempt()}
                        disabled={
                          busy ||
                          attemptAnswers[attemptCurrent] == null
                        }
                      >
                        Finish Attempt
                      </button>
                    )}
                  </div>
                </div>

                {attemptShowHint && (
                  <div className="workspace-attempt-hint">
                    <span className="eyebrow">Hint</span>
                    <p>
                      {attemptQuestions[attemptCurrent]?.hint ||
                        "Break the problem into smaller steps and identify the quantity or rule being tested."}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="workspace-attempt-complete">
                <span className="eyebrow">Attempt Complete</span>
                <h2>Good work.</h2>

                <div className="workspace-attempt-score">
                  <strong>
                    {attemptCorrect} / {attemptQuestions.length}
                  </strong>
                  <span>
                    {attemptCorrect} correct ? {attemptWrong} wrong
                  </span>
                </div>

                <div className="workspace-attempt-final-solution">
                  <span className="eyebrow">Solution</span>
                  <p>
                    {attemptSolution ||
                      "The complete solution is available from the solved question above."}
                  </p>
                </div>

                <button
                  type="button"
                  className="primary"
                  onClick={closeWorkspaceAttempt}
                >
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="workspace-user">
        Signed in as <strong>{user.username}</strong>
      </div>
    </motion.div>''',
"guided attempt modal",
)

# Online-only settings: keep the backend contract but remove the user-facing mode selector.
settings_path = root / "client" / "src" / "App.tsx"
data2 = data

old_mode_state = '''  const [mode, setMode] = useState<"offline" | "online">(
    settings?.computation_mode === "online" ? "online" : "offline"
  );'''
new_mode_state = '''  const [mode] = useState<"offline" | "online">("online");'''

if data2.count(old_mode_state.encode("utf-8")) == 1:
    data2 = data2.replace(
        old_mode_state.encode("utf-8"),
        new_mode_state.encode("utf-8"),
        1,
    )
    print("Patched: online-only mode default")
else:
    print("Notice: online-only mode state fragment was not changed.")

old_mode_select = '''        <select
          value={mode}
          onChange={(event) =>
            setMode(event.target.value as "offline" | "online")
          }
          disabled={!enabled || busy}
        >
          <option value="offline">Offline</option>
          <option value="online">Online</option>
        </select>'''
new_mode_select = '''        <div className="workspace-online-only">
          Online
        </div>'''

if data2.count(old_mode_select.encode("utf-8")) == 1:
    data2 = data2.replace(
        old_mode_select.encode("utf-8"),
        new_mode_select.encode("utf-8"),
        1,
    )
    print("Patched: online-only settings control")
else:
    print("Notice: mode selector fragment was not changed.")

data = data2
app.write_bytes(data)
print("App.tsx written without global re-encoding.")

# Append CSS only if our marker is not already present.
css_data = css.read_bytes() if css.exists() else b""
marker = b"/* NOVA WORKSPACE GUIDED ATTEMPT */"

if marker not in css_data:
    css_patch = b'''
\n\n/* NOVA WORKSPACE GUIDED ATTEMPT */
.workspace-attempt-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(8, 12, 24, 0.62);
  backdrop-filter: blur(12px);
}

.workspace-attempt-modal {
  width: min(760px, 100%);
  max-height: min(820px, calc(100vh - 48px));
  overflow-y: auto;
  padding: 28px;
  border-radius: 24px;
  background: var(--surface, #ffffff);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.28);
}

.workspace-attempt-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.workspace-attempt-header h3 {
  margin: 4px 0 0;
}

.workspace-attempt-progress {
  white-space: nowrap;
  font-weight: 700;
}

.workspace-attempt-progress-bar {
  height: 7px;
  margin: 18px 0 24px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(127, 127, 127, 0.16);
}

.workspace-attempt-progress-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: currentColor;
  transition: width 220ms ease;
}

.workspace-attempt-question {
  padding: 8px 0 20px;
  font-size: 1.15rem;
  line-height: 1.65;
  font-weight: 650;
}

.workspace-attempt-options {
  display: grid;
  gap: 12px;
}

.workspace-attempt-option {
  display: grid;
  grid-template-columns: 38px 1fr;
  gap: 14px;
  width: 100%;
  padding: 15px 16px;
  border: 1px solid rgba(127, 127, 127, 0.22);
  border-radius: 16px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: transform 150ms ease, border-color 150ms ease, box-shadow 150ms ease;
}

.workspace-attempt-option:hover {
  transform: translateY(-1px);
}

.workspace-attempt-option.selected {
  border-color: currentColor;
  box-shadow: 0 8px 28px rgba(127, 127, 127, 0.14);
}

.workspace-attempt-option-label {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 10px;
  background: rgba(127, 127, 127, 0.1);
  font-weight: 800;
}

.workspace-attempt-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 24px;
}

.workspace-attempt-actions {
  display: flex;
  gap: 10px;
}

.workspace-attempt-hint {
  margin-top: 16px;
  padding: 15px 17px;
  border-radius: 16px;
  background: rgba(127, 127, 127, 0.08);
  line-height: 1.55;
}

.workspace-attempt-hint p {
  margin: 6px 0 0;
}

.workspace-attempt-complete {
  text-align: center;
}

.workspace-attempt-score {
  display: grid;
  gap: 4px;
  margin: 24px 0;
}

.workspace-attempt-score strong {
  font-size: 2.5rem;
  line-height: 1;
}

.workspace-attempt-final-solution {
  margin: 22px 0;
  padding: 18px;
  border-radius: 18px;
  background: rgba(127, 127, 127, 0.08);
  text-align: left;
  line-height: 1.65;
}

.workspace-attempt-final-solution p {
  margin: 8px 0 0;
  white-space: pre-wrap;
}

.workspace-follow-up.locked {
  opacity: 0.8;
}

.workspace-follow-up-lock {
  margin: 0;
  line-height: 1.55;
}

.workspace-online-only {
  display: inline-flex;
  align-items: center;
  min-height: 40px;
  padding: 0 14px;
  border-radius: 12px;
  background: rgba(127, 127, 127, 0.1);
  font-weight: 700;
}

@media (max-width: 700px) {
  .workspace-attempt-overlay {
    padding: 12px;
  }

  .workspace-attempt-modal {
    padding: 20px;
    border-radius: 20px;
    max-height: calc(100vh - 24px);
  }

  .workspace-attempt-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .workspace-attempt-actions {
    justify-content: flex-end;
  }
}
'''
    css.write_bytes(css_data + css_patch)
    print("App.css: guided-attempt styles appended.")
else:
    print("App.css: guided-attempt styles already present.")

print("Patch completed successfully.")

import { useState } from "react";
import { adminLogin, getStudentHistory, getStudentHistoryDetail, type AdminUser, type HistoryDetail, type HistoryEntry } from "./api";
import "./App.css";

type View = "login" | "search" | "detail";
type StoredAdminSession = { admin: AdminUser; password: string };

const ADMIN_SESSION_KEY = "nova_ai_admin_session";

// Floating math symbols — same set as client
const MATH_SYMBOLS = [
  { char: "∑", size: 110, left: 5,  delay: 0,   duration: 18 },
  { char: "∫", size: 130, left: 15, delay: 3,   duration: 22 },
  { char: "π",  size: 95,  left: 28, delay: 6,   duration: 16 },
  { char: "√",  size: 105, left: 42, delay: 1.5, duration: 20 },
  { char: "∞",  size: 90,  left: 58, delay: 9,   duration: 25 },
  { char: "Δ",  size: 100, left: 72, delay: 4,   duration: 19 },
  { char: "θ",  size: 85,  left: 85, delay: 7,   duration: 21 },
  { char: "λ",  size: 115, left: 93, delay: 2,   duration: 17 },
  { char: "∂",  size: 92,  left: 35, delay: 11,  duration: 23 },
  { char: "≠",  size: 88,  left: 65, delay: 5,   duration: 15 },
  { char: "∇",  size: 108, left: 50, delay: 13,  duration: 24 },
  { char: "∈",  size: 82,  left: 78, delay: 8,   duration: 20 },
];

function MathBackground() {
  return (
    <div className="math-bg" aria-hidden="true">
      {MATH_SYMBOLS.map((sym, i) => (
        <span
          key={i}
          className="math-symbol"
          style={{
            left: `${sym.left}%`,
            bottom: "-80px",
            fontSize: `${sym.size}px`,
            animationDuration: `${sym.duration}s`,
            animationDelay: `${sym.delay}s`,
          }}
        >
          {sym.char}
        </span>
      ))}
    </div>
  );
}

function readStoredAdminSession(): StoredAdminSession | null {
  try {
    const raw = localStorage.getItem(ADMIN_SESSION_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      !("admin" in parsed) ||
      !("password" in parsed) ||
      typeof parsed.password !== "string" ||
      !parsed.password ||
      typeof parsed.admin !== "object" ||
      parsed.admin === null ||
      !("id" in parsed.admin) ||
      !("username" in parsed.admin) ||
      typeof parsed.admin.id !== "number" ||
      typeof parsed.admin.username !== "string" ||
      !parsed.admin.username.trim()
    ) {
      localStorage.removeItem(ADMIN_SESSION_KEY);
      return null;
    }
    return parsed as StoredAdminSession;
  } catch {
    localStorage.removeItem(ADMIN_SESSION_KEY);
    return null;
  }
}

function parseStoredList(value: string): string[] {
  try {
    const parsed: unknown = JSON.parse(value);
    if (Array.isArray(parsed)) return parsed.filter((item): item is string => typeof item === "string");
  } catch {
    // Fall through to legacy comma-separated format.
  }
  return value.split(", ").map((item) => item.trim()).filter(Boolean);
}

function scorePercent(score: string): number {
  const [correct, total] = score.split("/").map(Number);
  return total > 0 ? Math.round((correct / total) * 100) : 0;
}

export default function App() {
  const [storedSession] = useState<StoredAdminSession | null>(() => readStoredAdminSession());
  const [view, setView] = useState<View>(() => (storedSession ? "search" : "login"));
  const [admin, setAdmin] = useState<AdminUser | null>(() => storedSession?.admin ?? null);
  const [adminPassword, setAdminPassword] = useState(() => storedSession?.password ?? "");
  const [studentUsername, setStudentUsername] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  async function handleLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!username.trim() || !password) {
      setError("Enter your admin username and password.");
      return;
    }
    setLoading(true);
    try {
      const response = await adminLogin(username.trim(), password);
      setAdmin(response.data);
      setAdminPassword(password);
      localStorage.setItem(
        ADMIN_SESSION_KEY,
        JSON.stringify({ admin: response.data, password } satisfies StoredAdminSession),
      );
      setView("search");
      setPassword("");
      setHasSearched(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Admin login failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!admin || !studentUsername.trim()) {
      setError("Enter a student username.");
      return;
    }
    setError("");
    setLoading(true);
    setDetail(null);
    try {
      const response = await getStudentHistory(admin.username, adminPassword, studentUsername.trim());
      setStudentUsername(studentUsername.trim());
      setHistory(response.data);
      setHasSearched(true);
    } catch (err) {
      setHistory([]);
      setError(err instanceof Error ? err.message : "Unable to load student history.");
    } finally {
      setLoading(false);
    }
  }

  async function openHistory(entry: HistoryEntry) {
    if (!admin) return;
    setError("");
    setLoading(true);
    try {
      const response = await getStudentHistoryDetail(admin.username, adminPassword, studentUsername, entry.id);
      setDetail(response.data);
      setView("detail");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load performance details.");
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem(ADMIN_SESSION_KEY);
    setAdmin(null);
    setAdminPassword("");
    setStudentUsername("");
    setHistory([]);
    setDetail(null);
    setHasSearched(false);
    setView("login");
  }

  function resetStudentSearch() {
    setStudentUsername("");
    setHistory([]);
    setDetail(null);
    setError("");
    setHasSearched(false);
  }

  return (
    <div className="admin-shell">
      <MathBackground />
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      {/* ── Topbar ── */}
      <header className="topbar">
        <div className="brand">
          <span className="brand-icon">∑</span>
          <span className="brand-label">nova ai</span>
          <span className="brand-sub">admin</span>
        </div>
        {admin && (
          <button className="text-button" onClick={logout}>
            Log out
          </button>
        )}
      </header>

      <main className="admin-main">

        {/* ════════════ LOGIN ════════════ */}
        {view === "login" && (
          <section className="auth-card">
            <span className="eyebrow">Restricted access</span>
            <h1>Admin sign in</h1>
            <p className="muted">Review student learning sessions and performance.</p>
            <form onSubmit={handleLogin}>
              <label htmlFor="admin-username">
                Username
                <input
                  id="admin-username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  placeholder="Enter username"
                  disabled={loading}
                />
              </label>
              <label htmlFor="admin-password">
                Password
                <input
                  id="admin-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  placeholder="Enter password"
                  disabled={loading}
                />
              </label>
              {error && <div className="error">{error}</div>}
              <button className="primary full" disabled={loading}>
                {loading ? "Signing in…" : "Log in"}
              </button>
            </form>
          </section>
        )}

        {/* ════════════ SEARCH ════════════ */}
        {view === "search" && (
          <section className="workspace">
            {hasSearched && (
              <button className="back-button" onClick={resetStudentSearch}>
                ← Back
              </button>
            )}

            <div className="page-heading">
              <div>
                <span className="eyebrow">Student performance</span>
                <h1>Find a student</h1>
              </div>
              <span className="admin-badge">{admin?.username}</span>
            </div>

            <form className="search-form" onSubmit={handleSearch}>
              <input
                value={studentUsername}
                onChange={(e) => { setStudentUsername(e.target.value); setHasSearched(false); }}
                placeholder="Enter student username"
                aria-label="Student username"
              />
              <button className="primary" disabled={loading}>
                {loading ? "Loading…" : "Search"}
              </button>
            </form>

            {error && <div className="error">{error}</div>}

            {history.length > 0 && (
              <section className="history-panel">
                <div className="section-heading">
                  <h2>{studentUsername}'s sessions</h2>
                  <span>{history.length} sessions</span>
                </div>
                <div className="history-list">
                  {history.map((entry) => (
                    <button
                      className="history-item"
                      key={entry.id}
                      onClick={() => void openHistory(entry)}
                    >
                      <span>{entry.user_question}</span>
                      <small>{entry.score}</small>
                    </button>
                  ))}
                </div>
              </section>
            )}

            {!loading && hasSearched && history.length === 0 && !error && (
              <div className="empty-state">No sessions found for this student.</div>
            )}
          </section>
        )}

        {/* ════════════ DETAIL ════════════ */}
        {view === "detail" && detail && (
          <section className="workspace">
            <button className="back-button" onClick={() => setView("search")}>
              ← Back to sessions
            </button>

            {/* Score card */}
            <div className="result-card">
              <span className="eyebrow">Performance review</span>
              <h1>{studentUsername}</h1>
              <div className="score">{detail.score}</div>
              <div className="progress">
                <div style={{ width: `${scorePercent(detail.score)}%` }} />
              </div>
              <p>{scorePercent(detail.score)}% correct</p>
            </div>

            {/* Original question */}
            <section className="detail-section">
              <span className="eyebrow">Original question</span>
              <h2>{detail.user_question}</h2>
            </section>

            {/* Question-by-question review */}
            <section className="detail-section">
              <div className="section-heading">
                <h2>Question review</h2>
                <span>{parseStoredList(detail.ai_questions).length} questions</span>
              </div>
              <div className="review-list">
                {parseStoredList(detail.ai_questions).map((question, index) => {
                  const isWrong = parseStoredList(detail.wrong_answered_question ?? "").some(
                    (wq) => question.includes(wq) || wq.includes(question.substring(0, 30)),
                  );
                  return (
                    <article className="review-item" key={`${index}-${question}`}>
                      <div
                        className={`review-status ${isWrong ? "incorrect" : "correct"}`}
                        aria-label={isWrong ? "Incorrect" : "Correct"}
                      >
                        {isWrong ? "×" : "✓"}
                      </div>
                      <div className="review-content">
                        <div className="review-number">Question {index + 1}</div>
                        <div className="review-question">{question}</div>
                        <div className="review-answer">
                          Correct answer:{" "}
                          <strong>
                            {parseStoredList(detail.ai_answers)[index] || "Not recorded"}
                          </strong>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>

            {/* AI remarks */}
            <section className="remarks">
              <span className="eyebrow">AI Remarks</span>
              <p>{detail.remarks || "No remarks were recorded for this session."}</p>
            </section>
          </section>
        )}

      </main>
    </div>
  );
}

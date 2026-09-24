import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  login,
  postDoubtQuestion,
  postGraphicalQuestion,
  postQuestion,
  postScore,
  signup,
  getUserHistory,
  getHistoryDetail,
  createWorkspace,
  joinWorkspace,
  getWorkspaces,
  getWorkspaceDetails,
  leaveWorkspace,
  inviteToWorkspace,
  getWorkspaceInvitations,
  getWorkspaceSentInvitations,
  acceptWorkspaceInvitation,
  declineWorkspaceInvitation,
  promoteWorkspaceMember,
  removeWorkspaceMember,
  transferWorkspaceOwnership,
  updateWorkspaceSettings,
  createWorkspaceQuestion,
  getWorkspaceQuestions,
  getWorkspaceQuestionDetails,
  deleteWorkspaceQuestion,
  getWorkspaceQuestionSolution,
  computeWorkspaceQuestion,
  createWorkspaceAttempt,
  completeWorkspaceAttempt,
  exitWorkspaceAttempt,
  terminateWorkspaceAttempt,
  getWorkspaceQuestionAttempts,
  getWorkspaceMemberPerformance,
  postWorkspaceQuestionFollowUp,
} from "./services/api";
import { getQuestionImageUrl, uploadQuestionImage } from "./services/supabase";
import type {
  Coordinate,
  LearnAgainResponse,
  Question,
  QuestionResponse,
  User,
  HistoryEntry,
  HistoryDetail,
  Workspace,
  WorkspaceMember,
  WorkspaceSettings,
  WorkspaceQuestion,
  WorkspaceSolution,
  WorkspaceAttempt,
  WorkspaceInvitation,
  WorkspaceFollowUp,
} from "./types";
import MathText from "./components/MathText";
import WorkspaceRichText from "./components/WorkspaceRichText";
import WorkspaceSolutionText from "./components/WorkspaceSolutionText";
import "./App.css";
import VoiceTutor from "./components/VoiceTutor";
import { useVoiceTutor } from "./hooks/useVoiceTutor";

type Page = "landing" | "login" | "signup" | "app";
type Stage = "home" | "loading" | "quiz" | "result" | "learnAgain" | "original" | "evaluation" | "history_view" | "workspace";
type Mode = "standard" | "graphical";

type StoredSession = {
  id: number | string;
  username: string;
};

const SESSION_KEY = "nova_ai_session";
const MAX_IMAGE_SIZE = 10 * 1024 * 1024;
const DESKTOP_SIDEBAR_QUERY = "(min-width: 701px)";

const quotes = [
  "Every expert was once a beginner.",
  "The important thing is not to stop questioning.",
  "Learning never exhausts the mind.",
  "Small steps lead to big discoveries.",
  "Curiosity is the beginning of understanding.",
];

// Floating math symbols for decorative background
const MATH_SYMBOLS = [
  { char: "∑", size: 110, left: 5, delay: 0, duration: 18 },
  { char: "∫", size: 130, left: 15, delay: 3, duration: 22 },
  { char: "π", size: 95, left: 28, delay: 6, duration: 16 },
  { char: "√", size: 105, left: 42, delay: 1.5, duration: 20 },

  // Science
  { char: "⚛", size: 100, left: 58, delay: 9, duration: 25 },
  { char: "H₂O", size: 82, left: 72, delay: 4, duration: 19 },
  { char: "DNA", size: 78, left: 85, delay: 7, duration: 21 },
  { char: "CO₂", size: 82, left: 93, delay: 2, duration: 17 },

  // Computer Science / AI
  { char: "</>", size: 82, left: 35, delay: 11, duration: 23 },
  { char: "0101", size: 72, left: 65, delay: 5, duration: 15 },
  { char: "AI", size: 88, left: 50, delay: 13, duration: 24 },
  { char: "{ }", size: 82, left: 78, delay: 8, duration: 20 },
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

function readStoredSession(): User | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      !("id" in parsed) ||
      !("username" in parsed) ||
      (typeof parsed.id !== "string" && typeof parsed.id !== "number") ||
      typeof parsed.username !== "string" ||
      !parsed.username.trim()
    ) {
      localStorage.removeItem(SESSION_KEY);
      return null;
    }
    return parsed as StoredSession;
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

function isQuestion(value: unknown): value is Question {
  if (typeof value !== "object" || value === null) return false;
  if (!("question" in value) || !("options" in value) || !("hint" in value) || !("correct_option" in value)) {
    return false;
  }

  const question = value.question;
  const options = value.options;
  const hint = value.hint;
  const correctOption = value.correct_option;
  const solution = "solution" in value ? value.solution : undefined;
  const coordinates = "coordinates" in value ? value.coordinates : undefined;

  return (
    typeof question === "string" &&
    question.trim().length > 0 &&
    Array.isArray(options) &&
    options.length === 4 &&
    options.every((option) => typeof option === "string") &&
    typeof hint === "string" &&
    typeof correctOption === "number" &&
    Number.isInteger(correctOption) &&
    correctOption >= 1 &&
    correctOption <= 4 &&
    (solution === undefined || typeof solution === "string") &&
    (coordinates === undefined || (
      Array.isArray(coordinates) &&
      coordinates.length <= 4 &&
      coordinates.every((point) => (
        Array.isArray(point) && point.length === 2 &&
        point.every((coordinate) => typeof coordinate === "number" && Number.isFinite(coordinate))
      ))
    ))
  );
}

function validateQuestionResponse(value: unknown): QuestionResponse | null {
  if (typeof value !== "object" || value === null) return null;
  if (!("is_relevant" in value) || typeof value.is_relevant !== "boolean") return null;
  if (!("error_message" in value) || typeof value.error_message !== "string") return null;

  if (!value.is_relevant) {
    return value as QuestionResponse;
  }

  if (
    !("ai_questions" in value) ||
    !Array.isArray(value.ai_questions) ||
    value.ai_questions.length === 0 ||
    !value.ai_questions.every(isQuestion) ||
    !("user_question" in value) ||
    !isQuestion(value.user_question)
  ) {
    return null;
  }

  return value as QuestionResponse;
}

function validateLearnAgainResponse(value: unknown): LearnAgainResponse | null {
  if (typeof value !== "object" || value === null) return null;
  if (
    !("ai_questions" in value) ||
    !Array.isArray(value.ai_questions) ||
    value.ai_questions.length === 0 ||
    !value.ai_questions.every(isQuestion)
  ) {
    return null;
  }
  if (!("user_question" in value) || !isQuestion(value.user_question)) return null;
  return value as LearnAgainResponse;
}

function App() {
  const [page, setPage] = useState<Page>(() => (readStoredSession() ? "app" : "landing"));
  const [user, setUser] = useState<User | null>(() => readStoredSession());

  function authenticate(userData: User) {
    const safeUser = { id: userData.id, username: userData.username.trim() };
    localStorage.setItem(SESSION_KEY, JSON.stringify(safeUser));
    setUser(safeUser);
    setPage("app");
  }

  function logout() {
    localStorage.removeItem(SESSION_KEY);
    setUser(null);
    setPage("landing");
  }

  if (page === "landing") {
    return <Landing onLogin={() => setPage("login")} onSignup={() => setPage("signup")} />;
  }

  if (page === "login" || page === "signup") {
    return (
      <Auth
        mode={page}
        onBack={() => setPage("landing")}
        onSwitch={() => setPage(page === "login" ? "signup" : "login")}
        onAuthenticated={authenticate}
      />
    );
  }

  if (!user) {
    return <Landing onLogin={() => setPage("login")} onSignup={() => setPage("signup")} />;
  }

  return <NovaAI user={user} onLogout={logout} />;
}

function Landing({ onLogin, onSignup }: { onLogin: () => void; onSignup: () => void }) {
  return (
    <motion.main
      className="landing"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.65 }}
    >
      <MathBackground />
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <motion.div
        className="landing-content"
        initial={{ opacity: 0, y: 45, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 90, damping: 15 }}
      >
        <motion.div
          className="logo"
          initial={{ y: -18, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.15 }}
        >
          <span className="logo-icon">∑</span>
          Stepwise Prism AI
        </motion.div>

        <motion.p
          className="landing-formula"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          f(x) = ∫₀∞ g(t) dt &nbsp;·&nbsp; lim(n→∞) (1 + 1/n)ⁿ = e &nbsp;·&nbsp; ∇²φ = ρ/ε₀
        </motion.p>

        <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
          Learn by <span>understanding.</span>
        </motion.h1>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}>
          Ask any question, practice the concept through AI-generated scaffolding, and discover whether you truly understood it.
        </motion.p>
        <motion.div className="landing-actions" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>
          <motion.button whileHover={{ scale: 1.045, y: -3 }} whileTap={{ scale: 0.97 }} className="primary" onClick={onSignup}>Get started</motion.button>
          <motion.button whileHover={{ scale: 1.045, y: -3 }} whileTap={{ scale: 0.97 }} className="secondary" onClick={onLogin}>Log in</motion.button>
        </motion.div>

        <motion.div
          className="landing-pills"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.65 }}
        >
          <span className="landing-pill"><span>∑</span>Scaffolded MCQs</span>
          <span className="landing-pill"><span>∫</span>Step-by-step hints</span>
          <span className="landing-pill"><span>π</span>Graph mode</span>
          <span className="landing-pill"><span>Δ</span>Learn Again</span>
          <span className="landing-pill"><span>√</span>AI-powered feedback</span>
        </motion.div>
      </motion.div>
    </motion.main>
  );
}

function Auth({
  mode,
  onBack,
  onSwitch,
  onAuthenticated,
}: {
  mode: "login" | "signup";
  onBack: () => void;
  onSwitch: () => void;
  onAuthenticated: (user: User) => void;
}) {
  const isLogin = mode === "login";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [standard, setStandard] = useState<number | "">("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const cleanUsername = username.trim();
    if (!cleanUsername || !password) {
      setError("Username and password are required.");
      return;
    }

    if (!isLogin && (standard === "" || standard < 6 || standard > 12)) {
      setError("Please select your class (6 – 12).");
      return;
    }

    setLoading(true);
    try {
      const response = isLogin
        ? await login(cleanUsername, password)
        : await signup(cleanUsername, password, standard as number);
      if (!response.data || typeof response.data.username !== "string") {
        throw new Error("Stepwise Prism AI returned an invalid account response.");
      }
      onAuthenticated(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <motion.main className="auth-page" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.45 }}>
      <MathBackground />
      <motion.form className="auth-card" onSubmit={submit} initial={{ opacity: 0, y: 35, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: "spring", stiffness: 100, damping: 16 }}>
        <motion.button type="button" className="back" onClick={onBack} whileHover={{ x: -4 }} whileTap={{ scale: 0.96 }}>← Back</motion.button>
        <motion.div className="logo" initial={{ scale: 0.7, rotate: -8 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 160 }}>
          <span className="logo-icon">∑</span>
          Stepwise Prism AI
        </motion.div>
        <motion.h1 initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>{isLogin ? "Welcome back" : "Create your account"}</motion.h1>
        <p className="muted">{isLogin ? "Log in to continue learning." : "Start your learning journey."}</p>

        <label htmlFor="username">Username
          <input
            id="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="Enter username"
            autoComplete="username"
            disabled={loading}
          />
        </label>

        <label htmlFor="password">Password
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Enter password"
            autoComplete={isLogin ? "current-password" : "new-password"}
            disabled={loading}
          />
        </label>

        {!isLogin && (
          <label htmlFor="standard">Class / Standard
            <select
              id="standard"
              value={standard}
              onChange={(event) => setStandard(event.target.value === "" ? "" : Number(event.target.value))}
              disabled={loading}
              aria-required="true"
            >
              <option value="">Select your class</option>
              {[6, 7, 8, 9, 10, 11, 12].map((cls) => (
                <option key={cls} value={cls}>Class {cls}</option>
              ))}
            </select>
          </label>
        )}

        <AnimatePresence>
          {error && (
            <motion.div
              className="global-error-popup"
              role="alert"
              initial={{ opacity: 0, y: -20, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.96 }}
              transition={{ duration: 0.2 }}
              style={{
                position: "fixed",
                top: "20px",
                left: "50%",
                transform: "translateX(-50%)",
                zIndex: 9999,
                display: "flex",
                alignItems: "center",
                gap: "12px",
                maxWidth: "min(560px, calc(100vw - 32px))",
                padding: "13px 16px",
                borderRadius: "10px",
                border: "1px solid rgba(255, 90, 90, 0.45)",
                background: "rgba(105, 20, 25, 0.96)",
                color: "#fff",
                boxShadow: "0 12px 35px rgba(0, 0, 0, 0.35)",
                backdropFilter: "blur(12px)",
                fontSize: "14px",
                lineHeight: 1.45,
              }}
            >
              <span style={{ flex: 1 }}>{error}</span>
              <button
                type="button"
                aria-label="Dismiss error"
                onClick={() => setError("")}
                style={{
                  border: 0,
                  background: "transparent",
                  color: "#fff",
                  fontSize: "20px",
                  lineHeight: 1,
                  cursor: "pointer",
                  padding: "2px 4px",
                  opacity: 0.85,
                }}
              >
                ×
              </button>
            </motion.div>
          )}
        </AnimatePresence>
        <AnimatePresence mode="wait">
          {error && <motion.div className="error" role="alert" initial={{ opacity: 0, height: 0, y: -8 }} animate={{ opacity: 1, height: "auto", y: 0 }} exit={{ opacity: 0, height: 0, y: -8 }}> {error}</motion.div>}
        </AnimatePresence>
        <motion.button whileHover={{ scale: 1.02, y: -2 }} whileTap={{ scale: 0.98 }} className="primary full" disabled={loading}>
          {loading ? (isLogin ? "Signing in..." : "Creating account...") : isLogin ? "Log in" : "Create account"}
        </motion.button>
        <motion.button whileHover={{ y: -1 }} type="button" className="switch-auth" onClick={onSwitch} disabled={loading}>
          {isLogin ? "Don't have an account? Sign up" : "Already have an account? Log in"}
        </motion.button>
      </motion.form>
    </motion.main>
  );
}

function NovaAI({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [sidebarOpen, setSidebarOpen] = useState(() => (
    typeof window === "undefined" ? true : window.matchMedia(DESKTOP_SIDEBAR_QUERY).matches
  ));
  const [stage, setStage] = useState<Stage>("home");
  const [quote, setQuote] = useState(() => quotes[Math.floor(Math.random() * quotes.length)]);
  const [questionText, setQuestionText] = useState("");
  const [mode, setMode] = useState<Mode>("standard");
  const [coordinates, setCoordinates] = useState<Coordinate[]>([]);
  const [image, setImage] = useState<File | null>(null);
  const [imagePath, setImagePath] = useState("");
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageUploading, setImageUploading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("Understanding your question...");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [originalQuestion, setOriginalQuestion] = useState<Question | null>(null);
  const [sessionResponse, setSessionResponse] = useState<QuestionResponse | null>(null);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [showHint, setShowHint] = useState(false);
  const [error, setError] = useState("");
  const [score, setScore] = useState(0);
  const [finalAnswer, setFinalAnswer] = useState<number | null>(null);
  const [learnAnswers, setLearnAnswers] = useState<Record<number, number>>({});
  const [learnCurrent, setLearnCurrent] = useState(0);
  const [learnQuestions, setLearnQuestions] = useState<Question[]>([]);
  const [learnError, setLearnError] = useState("");
  const [learnLoadingIndex, setLearnLoadingIndex] = useState<number | null>(null);
  const [learnScore, setLearnScore] = useState(0);
  const [showLearnResult, setShowLearnResult] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [currentHistoryDetail, setCurrentHistoryDetail] = useState<HistoryDetail | null>(null);
  const [voiceModalOpen, setVoiceModalOpen] = useState(false);
  const { status, isRecording, userBars, aiLevel, isMuted, startSession, stopSession, toggleMute } = useVoiceTutor();

  useEffect(() => {
    return () => {
      if (imagePreview) URL.revokeObjectURL(imagePreview);
    };
  }, [imagePreview]);

  useEffect(() => {
    const mediaQuery = window.matchMedia(DESKTOP_SIDEBAR_QUERY);
    const syncSidebar = (event: MediaQueryListEvent) => setSidebarOpen(event.matches);

    mediaQuery.addEventListener("change", syncSidebar);
    return () => mediaQuery.removeEventListener("change", syncSidebar);
  }, []);

  useEffect(() => {
    // Load history when component mounts
    async function loadHistory() {
      try {
        const response = await getUserHistory(user.username);
        setHistory(response.data);
      } catch (err) {
        // History loading error - silently fail, not critical to user experience
        console.error("Failed to load history:", err);
      }
    }
    void loadHistory();
  }, [user.username]);

  function removeImage() {
    setImage(null);
    setImagePath("");
    setImagePreview((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return null;
    });
  }

  function newChat() {
    removeImage();
    setQuestionText("");
    setMode("standard");
    setCoordinates([]);
    setQuestions([]);
    setOriginalQuestion(null);
    setSessionResponse(null);
    setCurrent(0);
    setAnswers({});
    setShowHint(false);
    setScore(0);
    setFinalAnswer(null);
    setError("");
    setLearnError("");
    setLearnQuestions([]);
    setLearnAnswers({});
    setLearnCurrent(0);
    setLearnLoadingIndex(null);
    setLearnScore(0);
    setShowLearnResult(false);
    setQuote(quotes[Math.floor(Math.random() * quotes.length)]);
    setStage("home");
    window.location.reload();
  }

  function openWorkspace() {
    setStage("workspace");
  }
  async function viewHistoryItem(historyId: number) {
    try {
      setStage("loading");
      setLoadingMessage("Loading your history...");

      const response = await getHistoryDetail(user.username, historyId);
      setCurrentHistoryDetail(response.data);
      setStage("history_view");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history detail");
      setStage("home");
    }
  }

  async function selectImage(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const allowedTypes = [
      "image/jpeg",
      "image/png",
      "image/webp",
      "image/heic",
      "image/heif",
    ];
    const fileExtension = file.name.split(".").pop()?.toLowerCase();
    const allowedExtensions = ["jpg", "jpeg", "png", "webp", "heic", "heif"];
    if (
      (file.type && !allowedTypes.includes(file.type)) ||
      (!file.type && !fileExtension) ||
      (fileExtension && !allowedExtensions.includes(fileExtension))
    ) {
      setError("Please choose a JPG, PNG, WEBP, HEIC or HEIF image.");
      return;
    }
    if (file.size > MAX_IMAGE_SIZE) {
      setError("Image is too large. Please choose an image up to 10 MB.");
      return;
    }

    setError("");
    removeImage();
    setImage(file);
    setImagePreview(URL.createObjectURL(file));

    setImageUploading(true);
    try {
      const uploadedPath = await uploadQuestionImage(file);
      setImagePath(uploadedPath);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Image upload failed. Please try again.");
      removeImage();
    } finally {
      setImageUploading(false);
    }
  }

  async function submitQuestion() {
    const cleanQuestion = questionText.trim();
    if (!cleanQuestion && !image) {
      setError("Enter a question or upload an image.");
      return;
    }

    if (imageUploading || stage === "loading") return;

    setError("");
    setStage("loading");

    try {
      setLoadingMessage(
        mode === "graphical" ? "Reading your graph..." :
          "Understanding your question..."
      );
      await new Promise<void>((resolve) => window.setTimeout(resolve, 100));
      setLoadingMessage("Generating a personalized practice session...");

      const rawResponse = mode === "graphical"
        ? await postGraphicalQuestion(user.username, cleanQuestion, coordinates)
        : await postQuestion(user.username, cleanQuestion, imagePath);
      const response = validateQuestionResponse(rawResponse);

      if (!response) {
        throw new Error("Something went wrong while preparing your practice session. Please try again.");
      }

      if (response.is_relevant !== true) {
        setError(response.error_message || "This question could not be processed.");
        setStage("home");
        return;
      }

      setSessionResponse(response);
      setQuestions(response.ai_questions);
      setOriginalQuestion(response.user_question);
      setCurrent(0);
      setAnswers({});
      setShowHint(false);
      setStage("quiz");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to connect to Stepwise Prism AI. Please try again.");
      setStage("home");
    } finally {
      setImageUploading(false);
    }
  }

  function chooseAnswer(option: number) {
    setAnswers((previous) => ({ ...previous, [current]: option }));
  }

  function finishPractice() {
    const finalScore = questions.reduce(
      (total, item, index) => total + (answers[index] === item.correct_option ? 1 : 0),
      0,
    );
    const wrongAnsweredQuestions = questions
      .filter((item, index) => answers[index] !== item.correct_option)
      .map((item) => item.question)
      .join(", ");

    setScore(finalScore);
    setShowHint(false);
    setStage("result");

    if (sessionResponse) {
      void postScore(
        user.username,
        JSON.stringify(sessionResponse),
        wrongAnsweredQuestions,
        `${finalScore}/${questions.length}`,
      ).catch(() => {
        // Saving the score should not prevent the result from being shown.
      });
    }
  }

  function nextQuestion() {
    if (answers[current] == null) return;

    if (current < questions.length - 1) {
      setCurrent((value) => value + 1);
      setShowHint(false);
      return;
    }

    finishPractice();
  }

  function previousQuestion() {
    if (current === 0) return;
    setCurrent((value) => value - 1);
    setShowHint(false);
  }

  function startOriginal() {
    setFinalAnswer(null);
    setShowHint(false);
    setStage("original");
  }

  function submitOriginal() {
    if (!originalQuestion || finalAnswer == null) return;
    setStage("evaluation");
  }

  async function learnAgain(question: Question, reviewIndex: number) {
    if (!sessionResponse || learnLoadingIndex !== null) return;

    setLearnError("");
    setLearnLoadingIndex(reviewIndex);
    setLoadingMessage("Preparing easier practice...");
    setStage("loading");

    try {
      const rawResponse = await postDoubtQuestion(
        user.username,
        question.question,
        JSON.stringify(sessionResponse),
      );
      const response = validateLearnAgainResponse(rawResponse);
      if (!response) {
        throw new Error("Something went wrong while preparing the new practice session. Please try again.");
      }

      setLearnQuestions(response.ai_questions);
      setLearnAnswers({});
      setLearnCurrent(0);
      setLearnScore(0);
      setShowLearnResult(false);
      setShowHint(false);
      setLearnError("");
      setStage("learnAgain");
    } catch (err) {
      setLearnError(err instanceof Error ? err.message : "Unable to prepare easier practice. Please try again.");
      setStage("result");
    } finally {
      setLearnLoadingIndex(null);
    }
  }

  function chooseLearnAnswer(option: number) {
    setLearnAnswers((previous) => ({ ...previous, [learnCurrent]: option }));
  }

  function nextLearnQuestion() {
    if (learnAnswers[learnCurrent] == null) return;
    if (learnCurrent < learnQuestions.length - 1) {
      setLearnCurrent((value) => value + 1);
      setShowHint(false);
      return;
    }
    const finalLearnScore = learnQuestions.reduce(
      (total, item, index) => total + (learnAnswers[index] === item.correct_option ? 1 : 0),
      0,
    );
    setLearnScore(finalLearnScore);
    setShowLearnResult(true);
    setShowHint(false);
    setStage("result");
  }

  const progress = questions.length ? ((current + 1) / questions.length) * 100 : 0;
  const learnProgress = learnQuestions.length ? ((learnCurrent + 1) / learnQuestions.length) * 100 : 0;

  const review = useMemo(
    () => questions.map((question, index) => ({
      question,
      index,
      selected: answers[index] ?? null,
      correct: answers[index] === question.correct_option,
    })),
    [answers, questions],
  );

  const learnReview = useMemo(
    () => learnQuestions.map((question, index) => ({
      question,
      index,
      selected: learnAnswers[index] ?? null,
      correct: learnAnswers[index] === question.correct_option,
    })),
    [learnAnswers, learnQuestions],
  );

  return (
    <div className={`app-shell ${sidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
      <motion.div className="ambient ambient-app-one" animate={{ x: [0, 35, 0], y: [0, -20, 0] }} transition={{ duration: 9, repeat: Infinity, ease: "easeInOut" }} />
      <motion.div className="ambient ambient-app-two" animate={{ x: [0, -28, 0], y: [0, 25, 0] }} transition={{ duration: 11, repeat: Infinity, ease: "easeInOut" }} />
      <MathBackground />
      {/* Voice Tutor ChatGPT-like overlay */}
      <VoiceTutor
        isOpen={voiceModalOpen}
        onClose={() => {
          setVoiceModalOpen(false);
          stopSession(); // Stops audio when closed
        }}
        status={status}
        isRecording={isRecording}
        userBars={userBars}
        aiLevel={aiLevel}
        isMuted={isMuted}
        onToggleMute={toggleMute}
        onReconnect={startSession}
      />
      <button
        type="button"
        className={`sidebar-toggle ${sidebarOpen ? "is-open" : ""}`}
        onClick={() => setSidebarOpen((value) => !value)}
        aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
        aria-expanded={sidebarOpen}
      >
        <span />
        <span />
        <span />
      </button>

      {sidebarOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close sidebar"
        />
      )}
      <motion.aside className="sidebar" aria-hidden={!sidebarOpen} initial={false} animate={{ opacity: sidebarOpen ? 1 : 0.85 }} transition={{ type: "spring", stiffness: 240, damping: 26 }}>

        <div className="brand">
          <span className="brand-icon">∑</span>
          <span className="brand-name"><span>Stepwise</span><span>Prism AI</span></span>
        </div>
        <button
          type="button"
          className="workspace-button"
          onClick={openWorkspace}
          style={{
            minHeight: "40px",
            padding: "0 18px",
            borderRadius: "10px",
            border: "1px solid rgba(255, 255, 255, 0.16)",
            background: "linear-gradient(180deg, rgba(255,255,255,0.09), rgba(255,255,255,0.04))",
            color: "inherit",
            fontWeight: 600,
            letterSpacing: "0.01em",
            boxShadow: "0 4px 14px rgba(0,0,0,0.16)",
            cursor: "pointer",
          }}
        >
          Workspaces
        </button>
        <button className="new-chat" onClick={newChat}>+ New Chat</button>

        <div className="mode-switcher" aria-label="Question mode">
          <button
            type="button"
            className={mode === "standard" ? "active" : ""}
            aria-pressed={mode === "standard"}
            onClick={() => { setMode("standard"); setCoordinates([]); }}
          >
            Standard
          </button>
          <button
            type="button"
            className={mode === "graphical" ? "active" : ""}
            aria-pressed={mode === "graphical"}
            onClick={() => setMode("graphical")}
          >
            Graphical
          </button>
        </div>

        {/* History Section */}
        {history.length > 0 && (
          <div className="history-section">
            <div className="history-title">Chat History</div>
            <div className="history-list">
              {history.map((item) => (
                <button
                  key={item.id}
                  className="history-item"
                  onClick={() => viewHistoryItem(item.id)}
                  title={item.user_question}
                >
                  <span className="history-question">{item.user_question.substring(0, 30)}{item.user_question.length > 30 ? "..." : ""}</span>
                  <span className="history-score">{item.score}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="sidebar-bottom">
          <div className="username" title={user.username}>{user.username}</div>
          <button className="logout" onClick={onLogout}>Log out</button>
        </div>
      </motion.aside>

      <main className="main">
        <AnimatePresence mode="wait" initial={false}>
          {stage === "home" && (
            <motion.div key="home" className="home-content" initial={{ opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.45, ease: "easeOut" }}>
              <div className="welcome">
                <h1>Hi, {user.username} 👋</h1>
                <p>“{quote}”</p>
              </div>

              <div className="composer-wrapper">
                {imagePreview && (
                  <div className="image-preview">
                    <img src={imagePreview} alt="Selected question preview" />
                    <button type="button" onClick={removeImage} aria-label="Remove image">×</button>
                  </div>
                )}

                {error && <div className="error composer-error" role="alert">{error}</div>}

                {mode === "graphical" && (
                  <GraphEditor coordinates={coordinates} onChange={setCoordinates} />
                )}
                <Composer
                  value={questionText}
                  onChange={setQuestionText}
                  onSubmit={submitQuestion}
                  onImage={selectImage}
                  onOpenVoice={() => {
                    setVoiceModalOpen(true);
                    void startSession(); // Starts audio IMMEDIATELY on click!
                  }}
                  disabled={imageUploading}
                  graphical={mode === "graphical"}
                />
                {image && (
                  <p className="attachment-name">
                    {imageUploading ? "Uploading image..." : image.name}
                  </p>
                )}
              </div>
            </motion.div>
          )}

          {stage === "loading" && (
            <motion.div key="loading" initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 1.05 }} transition={{ type: "spring", stiffness: 120, damping: 18 }}><LoadingState message={loadingMessage} /></motion.div>
          )}

          {stage === "quiz" && questions[current] && (
            <motion.div key={`quiz-${current}`} initial={{ opacity: 0, x: 55, scale: 0.98 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: -55, scale: 0.98 }} transition={{ type: "spring", stiffness: 120, damping: 20 }}>
              <Quiz
                question={questions[current]}
                current={current}
                total={questions.length}
                progress={progress}
                selected={answers[current] ?? null}
                showHint={showHint}
                onSelect={chooseAnswer}
                onHint={() => setShowHint(true)}
                onNext={nextQuestion}
                onPrevious={previousQuestion}
              />
            </motion.div>
          )}

          {stage === "result" && (
            <motion.div key="result" className="result-page" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -25 }} transition={{ duration: 0.5 }}>
              <div className="result-card">
                <span className="eyebrow">Practice complete</span>
                <h1>Quiz Complete!</h1>
                <div className="score">{score} / {questions.length}</div>
                <div className="progress-track" aria-label={`${questions.length ? Math.round((score / questions.length) * 100) : 0}% correct`}>
                  <div style={{ width: `${questions.length ? (score / questions.length) * 100 : 0}%` }} />
                </div>
                <p>{questions.length ? Math.round((score / questions.length) * 100) : 0}% Correct</p>
              </div>

              {learnError && <div className="error review-error" role="alert">{learnError}</div>}

              <QuestionReview
                review={review}
                loadingIndex={learnLoadingIndex}
                onLearnAgain={learnAgain}
                hideLearnAgain={mode === "graphical"}
              />

              {showLearnResult && learnQuestions.length > 0 && (
                <LearnAgainResult
                  score={learnScore}
                  review={learnReview}
                />
              )}

              <button className="primary result-next" onClick={startOriginal}>Try Original Question</button>
            </motion.div>
          )}

          {stage === "learnAgain" && learnQuestions[learnCurrent] && (
            <motion.div key={`learn-${learnCurrent}`} initial={{ opacity: 0, x: 55, scale: 0.98 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: -55, scale: 0.98 }} transition={{ type: "spring", stiffness: 120, damping: 20 }}>
              <Quiz
                question={learnQuestions[learnCurrent]}
                current={learnCurrent}
                total={learnQuestions.length}
                progress={learnProgress}
                selected={learnAnswers[learnCurrent] ?? null}
                showHint={showHint}
                learnAgain
                onSelect={chooseLearnAnswer}
                onHint={() => setShowHint(true)}
                onNext={nextLearnQuestion}
                onPrevious={() => {
                  if (learnCurrent > 0) {
                    setLearnCurrent((value) => value - 1);
                    setShowHint(false);
                  } else {
                    setStage("result");
                  }
                }}
              />
            </motion.div>
          )}

          {stage === "original" && originalQuestion && (
            <motion.div key="original" initial={{ opacity: 0, scale: 0.96, y: 25 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 1.03 }} transition={{ type: "spring", stiffness: 110, damping: 18 }}>
              <Quiz
                question={originalQuestion}
                current={0}
                total={1}
                progress={100}
                selected={finalAnswer}
                showHint={showHint}
                finalQuestion
                onSelect={setFinalAnswer}
                onHint={() => setShowHint(true)}
                onNext={submitOriginal}
                onPrevious={() => setStage("result")}
              />
            </motion.div>
          )}

          {stage === "evaluation" && originalQuestion && finalAnswer != null && (
            <motion.div key="evaluation" className="result-card final-result" initial={{ opacity: 0, scale: 0.82, y: 35 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.9 }} transition={{ type: "spring", stiffness: 120, damping: 16 }}>
              {finalAnswer === originalQuestion.correct_option ? (
                <>
                  <div className="result-icon correct-icon">✓</div>
                  <h1>Correct! 🎉</h1>
                  <p>
                    Correct answer:{" "}
                    <strong><MathText>{originalQuestion.options[originalQuestion.correct_option - 1]}</MathText></strong>
                  </p>
                  <p>You understood the concept.</p>
                </>
              ) : (
                <>
                  <div className="result-icon incorrect-icon">×</div>
                  <h1>Not quite.</h1>
                  <p>
                    Correct answer:{" "}
                    <strong><MathText>{originalQuestion.options[originalQuestion.correct_option - 1]}</MathText></strong>
                  </p>
                  <p>Review the concept and try again.</p>
                </>
              )}
              {originalQuestion.solution && (
                <div className="solution-block">
                  <div className="solution-label">Solution</div>
                  <p>{originalQuestion.solution}</p>
                </div>
              )}
              <button className="primary" onClick={newChat}>Start New Chat</button>
            </motion.div>
          )}

          {stage === "history_view" && currentHistoryDetail && (
            <motion.div key="history" className="result-page history-result" initial={{ opacity: 0, y: 25 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.45 }}>
              <div className="result-card">
                <span className="eyebrow">History Entry</span>
                <h1>Quiz Result</h1>
                <div className="score">{currentHistoryDetail.score}</div>
                <div className="progress-track" aria-label="Score display">
                  <div style={{
                    width: `${(() => {
                      const parts = currentHistoryDetail.score.split('/');
                      return parts.length === 2 ? Math.round((parseInt(parts[0]) / parseInt(parts[1])) * 100) : 0;
                    })()}%`
                  }} />
                </div>
                <p>{(() => {
                  const parts = currentHistoryDetail.score.split('/');
                  return parts.length === 2 ? Math.round((parseInt(parts[0]) / parseInt(parts[1])) * 100) : 0;
                })()}% Correct</p>
              </div>

              <HistoryReview historyDetail={currentHistoryDetail} />

              <button className="primary result-next" onClick={newChat}>Back to Home</button>
            </motion.div>
          )}
          {stage === "workspace" && (
            <WorkspacePanel
              user={user}
              onBack={() => setStage("home")}
            />
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}

function WorkspacePanel({
  user,
  onBack,
}: {
  user: User;
  onBack: () => void;
}) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [questions, setQuestions] = useState<WorkspaceQuestion[]>([]);
  const [selectedQuestion, setSelectedQuestion] = useState<WorkspaceQuestion | null>(null);
  const [attachmentUrl, setAttachmentUrl] = useState<string | null>(null);
  const [solution, setSolution] = useState<WorkspaceSolution | null>(null);
  const [attempts, setAttempts] = useState<WorkspaceAttempt[]>([]);
  const [followUps, setFollowUps] = useState<WorkspaceFollowUp[]>([]);
  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([]);
  const [sentInvitations, setSentInvitations] = useState<WorkspaceInvitation[]>([]);
  const [performanceMember, setPerformanceMember] =
    useState<WorkspaceMember | null>(null);
  const [memberPerformance, setMemberPerformance] =
    useState<WorkspaceAttempt[]>([]);
  const [performanceLoading, setPerformanceLoading] = useState(false);


  const [workspaceName, setWorkspaceName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [inviteUsername, setInviteUsername] = useState("");
  const [questionText, setQuestionText] = useState("");
  const [workspaceImage, setWorkspaceImage] = useState<File | null>(null);
  const [workspaceImagePath, setWorkspaceImagePath] = useState("");
  const [workspaceImagePreview, setWorkspaceImagePreview] = useState<string | null>(null);
  const [workspaceImageUploading, setWorkspaceImageUploading] = useState(false);
  const [openMemberMenu, setOpenMemberMenu] = useState<string | null>(null); const [visibility, setVisibility] = useState("public");
  const [followUp, setFollowUp] = useState("");

  const [guidedAttempt, setGuidedAttempt] = useState<{
    attemptId: number;
    questions: any[];
    currentIndex: number;
    answers: Record<number, number>;
    hints: Record<number, boolean>;
    completed: boolean;
    correct: number;
    wrong: number;
    solution: unknown;
  } | null>(null);

  const [activeTab, setActiveTab] = useState<"dashboard" | "questions" | "members" | "invitations" | "settings">("dashboard");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function showMemberPerformance(member: WorkspaceMember) {
    if (!selectedWorkspace?.id || !isAdmin || !member.user_id) {
      return;
    }

    setPerformanceMember(member);
    setMemberPerformance([]);
    setPerformanceLoading(true);
    setError("");

    try {
      const response = await getWorkspaceMemberPerformance(
        Number(selectedWorkspace.id),
        Number(member.user_id),
      );

      setMemberPerformance(
        Array.isArray(response.data) ? response.data : [],
      );
    } catch (err) {
      setPerformanceMember(null);
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load member performance.",
      );
    } finally {
      setPerformanceLoading(false);
    }
  }
  async function loadWorkspaces() {
    setBusy(true);
    setError("");

    try {
      const [workspaceResponse, invitationResponse] = await Promise.all([
        getWorkspaces(),
        getWorkspaceInvitations(),
      ]);

      setWorkspaces(
        Array.isArray(workspaceResponse.data) ? workspaceResponse.data : [],
      );

      setInvitations(
        Array.isArray(invitationResponse.data)
          ? invitationResponse.data
          : [],
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load workspaces.");
    } finally {
      setBusy(false);
    }
  }

  async function loadWorkspace(workspaceId: number) {
    setBusy(true);
    setError("");

    try {
      const response = await getWorkspaceDetails(workspaceId);
      const workspace = response.data as Workspace;
      setSelectedWorkspace(workspace);

      const [questionResponse, invitationResponse] = await Promise.all([
        getWorkspaceQuestions(workspaceId),
        getWorkspaceInvitations(),
      ]);

      setQuestions(Array.isArray(questionResponse.data) ? questionResponse.data : []);
      setInvitations(Array.isArray(invitationResponse.data) ? invitationResponse.data : []);

      if (
        workspace.role === "owner" ||
        workspace.role === "admin"
      ) {
        const sentInvitationResponse = await getWorkspaceSentInvitations(workspaceId);
        setSentInvitations(
          Array.isArray(sentInvitationResponse.data)
            ? sentInvitationResponse.data
            : [],
        );
      } else {
        setSentInvitations([]);
      }

      const workspaceWithDetails = workspace as Workspace & {
        members?: WorkspaceMember[];
        settings?: WorkspaceSettings;
      };

      setMembers(workspaceWithDetails.members ?? []);
      setSettings(workspaceWithDetails.settings ?? null);
      setSelectedQuestion(null);
      setSolution(null);
      setAttempts([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load workspace.");
    } finally {
      setBusy(false);
    }
  }

  async function createNewWorkspace() {
    const name = workspaceName.trim();
    if (!name) return;

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const response = await createWorkspace(name);
      const workspace = response.data as Workspace;

      setWorkspaceName("");
      setMessage("Workspace created successfully.");
      await loadWorkspaces();

      if (workspace?.id != null) {
        await loadWorkspace(Number(workspace.id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create workspace.");
    } finally {
      setBusy(false);
    }
  }

  async function joinExistingWorkspace() {
    const code = joinCode.trim();
    if (!code) return;

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const response = await joinWorkspace(code);
      const workspace = response.data as Workspace;

      setJoinCode("");
      setMessage("Joined workspace successfully.");
      await loadWorkspaces();

      if (workspace?.id != null) {
        await loadWorkspace(Number(workspace.id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to join workspace.");
    } finally {
      setBusy(false);
    }
  }

  async function refreshQuestions() {
    if (!selectedWorkspace?.id) return;

    try {
      const response = await getWorkspaceQuestions(Number(selectedWorkspace.id));
      setQuestions(Array.isArray(response.data) ? response.data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load questions.");
    }
  }

  function removeWorkspaceImage() {
    if (workspaceImagePreview) {
      URL.revokeObjectURL(workspaceImagePreview);
    }

    setWorkspaceImage(null);
    setWorkspaceImagePath("");
    setWorkspaceImagePreview(null);
  }

  async function selectWorkspaceImage(
    event: React.ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    const allowedTypes = new Set([
      "image/jpeg",
      "image/png",
      "image/webp",
      "image/heic",
      "image/heif",
    ]);

    const allowedExtensions = new Set([
      "jpg",
      "jpeg",
      "png",
      "webp",
      "heic",
      "heif",
    ]);

    const extension =
      file.name.split(".").pop()?.toLowerCase() ?? "";

    if (
      !allowedTypes.has(file.type) &&
      !allowedExtensions.has(extension)
    ) {
      setError(
        "Please select a JPG, PNG, WebP, HEIC, or HEIF image.",
      );
      event.target.value = "";
      return;
    }

    if (file.size > MAX_IMAGE_SIZE) {
      setError("Image must be 10 MB or smaller.");
      event.target.value = "";
      return;
    }

    setError("");
    setWorkspaceImageUploading(true);

    try {
      const uploadedPath = await uploadQuestionImage(file);

      if (workspaceImagePreview) {
        URL.revokeObjectURL(workspaceImagePreview);
      }

      setWorkspaceImage(file);
      setWorkspaceImagePath(uploadedPath);
      setWorkspaceImagePreview(URL.createObjectURL(file));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to upload image.",
      );
      setWorkspaceImage(null);
      setWorkspaceImagePath("");
      setWorkspaceImagePreview(null);
    } finally {
      setWorkspaceImageUploading(false);
      event.target.value = "";
    }
  }
  async function createQuestion() {
    if (
      !selectedWorkspace?.id ||
      (!questionText.trim() && !workspaceImage)
    ) {
      return;
    }

    if (workspaceImageUploading) {
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");

    try {
      await createWorkspaceQuestion({
        WorkspaceId: Number(selectedWorkspace.id),
        Question: questionText.trim(),
        ImagePath: workspaceImagePath || null,
        Visibility: visibility,
      });

      setQuestionText("");
      removeWorkspaceImage();
      setMessage("Question posted successfully.");
      await refreshQuestions();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create question.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function deleteQuestion(question: WorkspaceQuestion) {
    if (!selectedWorkspace?.id || !question.id) {
      return;
    }

    const confirmed = window.confirm(
      "Delete this question permanently? Its solution, attempts, and follow-ups will also be deleted.",
    );

    if (!confirmed) {
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");

    try {
      await deleteWorkspaceQuestion(
        Number(selectedWorkspace.id),
        Number(question.id),
      );

      const deletedQuestionId = Number(question.id);

      setQuestions((current) =>
        current.filter(
          (item) => Number(item.id) !== deletedQuestionId,
        ),
      );

      if (
        selectedQuestion &&
        Number(selectedQuestion.id) === deletedQuestionId
      ) {
        setSelectedQuestion(null);
        setSolution(null);
        setAttempts([]);
        setFollowUps([]);
        setAttachmentUrl(null);
      }

      setMessage("Question deleted permanently.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to delete the question.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function openQuestion(questionId: number) {
    if (!selectedWorkspace?.id) return;

    setBusy(true);
    setError("");

    try {
      const response = await getWorkspaceQuestionDetails(
        Number(selectedWorkspace.id),
        questionId,
      );

      setSelectedQuestion(response.data as WorkspaceQuestion);
      setFollowUps([]);

      const solutionResponse = await getWorkspaceQuestionSolution(
        Number(selectedWorkspace.id),
        questionId,
      );

      if (solutionResponse.cached) {
        setSolution(solutionResponse.data as WorkspaceSolution);
      } else {
        setSolution(null);
      }

      try {
        const attemptResponse = await getWorkspaceQuestionAttempts(
          Number(selectedWorkspace.id),
          questionId,
        );
        setAttempts(
          Array.isArray(attemptResponse.data)
            ? attemptResponse.data
            : [],
        );
      } catch {
        setAttempts([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open question.");
    } finally {
      setBusy(false);
    }
  }


  function unwrapWorkspaceComputation(response: any): any {
    return (
      response?.result?.result ??
      response?.data?.result?.result ??
      response?.result ??
      response?.data?.result ??
      response?.data ??
      response
    );
  }

  async function computeQuestion() {
    if (!selectedWorkspace?.id || !selectedQuestion?.id) return;

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const workspaceId = Number(selectedWorkspace.id);
      const questionId = Number(selectedQuestion.id);

      const response = await computeWorkspaceQuestion({
        workspace_id: workspaceId,
        question_id: questionId,
        operation: "compute",
      });

      const computed = response as any;

      if (computed?.success === false) {
        throw new Error(
          computed?.error || "Unable to solve the question.",
        );
      }

      const generated = unwrapWorkspaceComputation(computed);

      if (generated?.is_relevant === false) {
        throw new Error(
          generated?.error_message ||
          "This question could not be processed.",
        );
      }

      setSolution({
        status: "completed",
        result_json: generated,
      } as WorkspaceSolution);

      setMessage("Solution completed.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to solve the question.",
      );
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
      const workspaceId = Number(selectedWorkspace.id);
      const questionId = Number(selectedQuestion.id);

      // Refresh attempts before creating anything.
      // This prevents stale React state from creating duplicate
      // active guided attempts for the same question.
      const attemptsResponse = await getWorkspaceQuestionAttempts(
        workspaceId,
        questionId,
      );

      const currentAttempts = Array.isArray(attemptsResponse.data)
        ? attemptsResponse.data
        : [];

      setAttempts(currentAttempts);

      let attempt = currentAttempts.find(
        (item) =>
          item.status === "active" &&
          Number(item.question_id) === questionId &&
          String(item.mode || "").toLowerCase() === "guided",
      );

      // Reuse the existing active guided attempt.
      if (!attempt?.id) {
        const attemptResponse = await createWorkspaceAttempt(
          workspaceId,
          questionId,
          "guided",
          "",
        );

        attempt = attemptResponse.data;
      }

      if (!attempt?.id) {
        throw new Error("Unable to create guided attempt.");
      }

      const computeResponse = await computeWorkspaceQuestion({
        workspace_id: workspaceId,
        question_id: questionId,
        operation: "compute",
      });

      const computed = computeResponse as any;

      if (computed?.success === false) {
        throw new Error(
          computed?.error || "Unable to prepare guided attempt.",
        );
      }

      const payload = unwrapWorkspaceComputation(computed);

      if (payload?.is_relevant === false) {
        throw new Error(
          payload?.error_message ||
          "This question could not be processed.",
        );
      }

      const guidedQuestions = Array.isArray(payload?.ai_questions)
        ? payload.ai_questions
        : [];

      if (guidedQuestions.length === 0) {
        throw new Error("No guided questions were returned.");
      }

      setGuidedAttempt({
        attemptId: Number(attempt.id),
        questions: guidedQuestions,
        currentIndex: 0,
        answers: {},
        hints: {},
        completed: false,
        correct: 0,
        wrong: 0,
        solution: null,
      });

      setMessage("Guided attempt started.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to start guided attempt.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function finishGuidedAttempt() {
    if (
      !guidedAttempt ||
      !selectedWorkspace?.id ||
      !selectedQuestion?.id
    ) {
      return;
    }

    const correct = guidedAttempt.questions.reduce(
      (count: number, question: any, index: number) =>
        guidedAttempt.answers[index] ===
          Number(question.correct_option)
          ? count + 1
          : count,
      0,
    );

    const wrong = guidedAttempt.questions.length - correct;

    setBusy(true);
    setError("");

    try {
      const workspaceId = Number(selectedWorkspace.id);
      const questionId = Number(selectedQuestion.id);

      const solutionResponse = await getWorkspaceQuestionSolution(
        workspaceId,
        questionId,
      );

      const rawSolution =
        (solutionResponse as any)?.data ??
        solutionResponse ??
        null;

      const finalSolution =
        unwrapWorkspaceComputation(rawSolution);

      await completeWorkspaceAttempt(
        workspaceId,
        guidedAttempt.attemptId,
        {
          answers: guidedAttempt.answers,
          questions: guidedAttempt.questions,
          correct,
          wrong,
          solution: finalSolution,
        },
        correct,
        true,
      );

      setGuidedAttempt({
        ...guidedAttempt,
        completed: true,
        correct,
        wrong,
        solution: finalSolution,
      });

      const response = await getWorkspaceQuestionAttempts(
        workspaceId,
        questionId,
      );

      setAttempts(
        Array.isArray(response.data)
          ? response.data
          : [],
      );

      setMessage("Attempt completed.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to complete attempt.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function closeGuidedAttempt(
    action: "exit" | "terminate",
  ) {
    if (!guidedAttempt || !selectedWorkspace?.id) return;

    setBusy(true);
    setError("");

    try {
      const workspaceId = Number(selectedWorkspace.id);
      const questionId = Number(selectedQuestion?.id);

      if (action === "exit") {
        await exitWorkspaceAttempt(
          workspaceId,
          guidedAttempt.attemptId,
        );
      } else {
        await terminateWorkspaceAttempt(
          workspaceId,
          guidedAttempt.attemptId,
        );
      }

      if (selectedQuestion?.id) {
        const response = await getWorkspaceQuestionAttempts(
          workspaceId,
          questionId,
        );

        setAttempts(
          Array.isArray(response.data)
            ? response.data
            : [],
        );
      }

      setGuidedAttempt(null);

      setMessage(
        action === "exit"
          ? "Attempt exited."
          : "Attempt terminated.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to close attempt.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function sendFollowUp() {
    if (!selectedWorkspace?.id || !selectedQuestion?.id || !followUp.trim()) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      const response = await postWorkspaceQuestionFollowUp(
        Number(selectedWorkspace.id),
        Number(selectedQuestion.id),
        followUp.trim(),
      );

      const createdFollowUp = response.data as WorkspaceFollowUp;

      setFollowUps((current) => [...current, createdFollowUp]);
      setFollowUp("");
      setMessage("Follow-up answered.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit follow-up.");
    } finally {
      setBusy(false);
    }
  }

  async function removeMember(member: WorkspaceMember) {
    if (!selectedWorkspace?.id || !member.username) {
      return;
    }

    const confirmed = window.confirm(
      `Remove ${member.username} from this workspace?`,
    );

    if (!confirmed) {
      return;
    }

    setBusy(true);
    setError("");
    setOpenMemberMenu(null);

    try {
      await removeWorkspaceMember(
        Number(selectedWorkspace.id),
        member.username,
      );
      await loadWorkspace(Number(selectedWorkspace.id));
      setMessage(`${member.username} removed from the workspace.`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to remove workspace member.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function transferOwnership(member: WorkspaceMember) {
    if (!selectedWorkspace?.id || !member.username) {
      return;
    }

    const confirmed = window.confirm(
      `Transfer workspace ownership to ${member.username}?`,
    );

    if (!confirmed) {
      return;
    }

    setBusy(true);
    setError("");
    setOpenMemberMenu(null);

    try {
      await transferWorkspaceOwnership(
        Number(selectedWorkspace.id),
        member.username,
      );
      await loadWorkspace(Number(selectedWorkspace.id));
      setMessage(`${member.username} is now the workspace owner.`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to transfer workspace ownership.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function sendInvitation() {
    if (!selectedWorkspace?.id || !inviteUsername.trim()) return;

    setBusy(true);
    setError("");

    try {
      await inviteToWorkspace(
        Number(selectedWorkspace.id),
        inviteUsername.trim(),
      );

      setInviteUsername("");
      setMessage("Invitation sent.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to send invitation.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAcceptInvitation(id: number) {
    setBusy(true);

    try {
      await acceptWorkspaceInvitation(id);
      const response = await getWorkspaceInvitations();
      setInvitations(Array.isArray(response.data) ? response.data : []);
      await loadWorkspaces();
      setMessage("Invitation accepted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to accept invitation.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeclineInvitation(id: number) {
    setBusy(true);

    try {
      await declineWorkspaceInvitation(id);
      const response = await getWorkspaceInvitations();
      setInvitations(Array.isArray(response.data) ? response.data : []);
      setMessage("Invitation declined.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to decline invitation.");
    } finally {
      setBusy(false);
    }
  }

  async function leaveCurrentWorkspace() {
    if (!selectedWorkspace?.id) return;

    setBusy(true);

    try {
      await leaveWorkspace(Number(selectedWorkspace.id));
      setSelectedWorkspace(null);
      setQuestions([]);
      setMembers([]);
      setSettings(null);
      setSelectedQuestion(null);
      setSolution(null);
      await loadWorkspaces();
      setMessage("You left the workspace.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to leave workspace.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void loadWorkspaces();
  }, []);

  useEffect(() => {
    if (!selectedWorkspace?.id) return;

    const workspace = selectedWorkspace as Workspace & {
      members?: WorkspaceMember[];
      settings?: WorkspaceSettings;
    };

    if (workspace.members) {
      setMembers(workspace.members);
    }

    if (workspace.settings) {
      setSettings(workspace.settings);
    }
  }, [selectedWorkspace]);

  const isAdmin =
    selectedWorkspace?.role === "owner" ||
    selectedWorkspace?.role === "admin";

  return (
    <motion.div
      className="workspace-page"
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="workspace-header">
        <div>
          <span className="eyebrow">Collaboration</span>
          <h1>Workspaces</h1>
          <p>
            Solve, learn, assign and analyse computational problems together.
          </p>
        </div>

        <button type="button" className="secondary" onClick={onBack}>
          Back to Solver
        </button>
      </div>

      <AnimatePresence>
        {error && (
          <motion.div
            className="workspace-error-popup"
            role="alert"
            initial={{ opacity: 0, y: -18, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -18, scale: 0.97 }}
            transition={{ duration: 0.2 }}
            style={{
              position: "fixed",
              top: "20px",
              left: "50%",
              transform: "translateX(-50%)",
              zIndex: 10000,
              display: "flex",
              alignItems: "center",
              gap: "12px",
              width: "min(560px, calc(100vw - 32px))",
              padding: "14px 16px",
              borderRadius: "10px",
              border: "1px solid rgba(255, 90, 90, 0.55)",
              background: "rgba(105, 20, 25, 0.97)",
              color: "#fff",
              boxShadow: "0 14px 38px rgba(0, 0, 0, 0.38)",
              backdropFilter: "blur(12px)",
              fontSize: "14px",
              lineHeight: 1.45,
            }}
          >
            <span style={{ flex: 1 }}>{error}</span>

            <button
              type="button"
              aria-label="Dismiss error"
              onClick={() => setError("")}
              style={{
                border: 0,
                background: "transparent",
                color: "#fff",
                fontSize: "22px",
                lineHeight: 1,
                cursor: "pointer",
                padding: "2px 5px",
                opacity: 0.9,
              }}
            >
              ×
            </button>
          </motion.div>
        )}
      </AnimatePresence>
      {message && <div className="workspace-message">{message}</div>}

      <div className="workspace-grid">
        <section className="workspace-card workspace-list-card">
          <div className="workspace-card-header">
            <div>
              <h2>My Workspaces</h2>
              <span>{workspaces.length} workspace{workspaces.length === 1 ? "" : "s"}</span>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => void loadWorkspaces()}
              disabled={busy}
            >
              Refresh
            </button>
          </div>

          <div className="workspace-create-row">
            <input
              value={workspaceName}
              onChange={(event) => setWorkspaceName(event.target.value)}
              placeholder="New workspace name"
              onKeyDown={(event) => {
                if (event.key === "Enter") void createNewWorkspace();
              }}
            />
            <button
              type="button"
              className="primary"
              onClick={() => void createNewWorkspace()}
              disabled={busy || !workspaceName.trim()}
            >
              Create
            </button>
          </div>

          <div className="workspace-create-row">
            <input
              value={joinCode}
              onChange={(event) => setJoinCode(event.target.value)}
              placeholder="Join code"
              onKeyDown={(event) => {
                if (event.key === "Enter") void joinExistingWorkspace();
              }}
            />
            <button
              type="button"
              className="secondary"
              onClick={() => void joinExistingWorkspace()}
              disabled={busy || !joinCode.trim()}
            >
              Join
            </button>
          </div>

          <div className="workspace-list">
            {workspaces.length === 0 ? (
              <div className="workspace-empty">
                No workspaces yet. Create one or join an existing workspace.
              </div>
            ) : (
              workspaces.map((workspace) => (
                <button
                  type="button"
                  key={workspace.id}
                  className={`workspace-list-item ${selectedWorkspace?.id === workspace.id ? "active" : ""
                    }`}
                  onClick={() => void loadWorkspace(Number(workspace.id))}
                >
                  <strong>{workspace.name}</strong>
                  <span>
                    {workspace.role ?? "member"}
                    {workspace.join_code ? ` · ${workspace.join_code}` : ""}
                  </span>
                </button>
              ))
            )}
          </div>

          <div className="workspace-invitations workspace-home-invitations">
            <div className="workspace-card-header">
              <div>
                <h3>Invitations</h3>
                <span>
                  {invitations.length} pending invitation{invitations.length === 1 ? "" : "s"}
                </span>
              </div>
            </div>

            {invitations.length === 0 ? (
              <div className="workspace-empty">
                You have no pending invitations.
              </div>
            ) : (
              invitations.map((invitation) => (
                <div
                  className="workspace-invitation-item"
                  key={invitation.id}
                >
                  <div>
                    <strong>
                      {invitation.workspace_name ?? "Workspace"}
                    </strong>
                    <span>
                      Invited by{" "}
                      {String(
                        invitation.invited_username ??
                        invitation.invited_by ??
                        "workspace member",
                      )}
                    </span>
                  </div>

                  {invitation.id != null && (
                    <div className="workspace-invitation-actions">
                      <button
                        type="button"
                        className="primary"
                        onClick={() =>
                          void handleAcceptInvitation(Number(invitation.id))
                        }
                        disabled={busy}
                      >
                        Accept
                      </button>

                      <button
                        type="button"
                        className="secondary"
                        onClick={() =>
                          void handleDeclineInvitation(Number(invitation.id))
                        }
                        disabled={busy}
                      >
                        Decline
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </section>

        <section className="workspace-card workspace-main-card">
          {!selectedWorkspace ? (
            <div className="workspace-empty workspace-empty-large">
              <div className="workspace-empty-icon">∑</div>
              <h2>Select a workspace</h2>
              <p>
                Create or join a workspace to access questions, members,
                computation, attempts and collaboration tools.
              </p>
            </div>
          ) : (
            <>
              <div className="workspace-card-header workspace-selected-header">
                <div>
                  <span className="eyebrow">Workspace</span>
                  <h2>{selectedWorkspace.name}</h2>
                  <span>
                    Role: {selectedWorkspace.role ?? "member"}
                    {selectedWorkspace.join_code
                      ? ` · Join code: ${selectedWorkspace.join_code}`
                      : ""}
                  </span>
                </div>

                <button
                  type="button"
                  className="secondary danger-action"
                  onClick={() => void leaveCurrentWorkspace()}
                  disabled={busy}
                >
                  Leave
                </button>
              </div>

              <div className="workspace-tabs">
                {(["dashboard", "questions", "members", ...(isAdmin ? ["invitations" as const] : []), "settings"] as const).map((tab) => (
                  <button
                    type="button"
                    key={tab}
                    className={activeTab === tab ? "active" : ""}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab.charAt(0).toUpperCase() + tab.slice(1)}
                  </button>
                ))}
              </div>

              {activeTab === "dashboard" && (
                <div className="workspace-dashboard">
                  <div className="workspace-stat-grid">
                    <div className="workspace-stat">
                      <span>Questions</span>
                      <strong>{questions.length}</strong>
                    </div>
                    <div className="workspace-stat">
                      <span>Members</span>
                      <strong>{members.length}</strong>
                    </div>
                    <div className="workspace-stat">
                      <span>Invitations</span>
                      <strong>{invitations.length}</strong>
                    </div>
                    <div className="workspace-stat">
                      <span>Computation</span>
                      <strong>Online</strong>
                    </div>
                  </div>

                  <div className="workspace-dashboard-actions">
                    <button
                      type="button"
                      className="primary"
                      onClick={() => setActiveTab("questions")}
                    >
                      Open Questions
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setActiveTab("members")}
                    >
                      View Members
                    </button>
                    {isAdmin && (
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => setActiveTab("settings")}
                      >
                        Workspace Settings
                      </button>
                    )}
                  </div>
                </div>
              )}

              {activeTab === "invitations" && isAdmin && (
                <div className="workspace-invitations">
                  <div className="workspace-card-header">
                    <div>
                      <h3>Invitations</h3>
                      <span>
                        {sentInvitations.length} pending invitation{sentInvitations.length === 1 ? "" : "s"} sent by this workspace
                      </span>
                    </div>
                  </div>

                  {sentInvitations.length === 0 ? (
                    <div className="workspace-empty-state">
                      No pending invitations.
                    </div>
                  ) : (
                    <div className="workspace-invitation-list">
                      {sentInvitations.map((invitation) => (
                        <div
                          className="workspace-invitation-card"
                          key={
                            invitation.id ??
                            `${invitation.invited_username}-${invitation.created_at ?? ""}`
                          }
                        >
                          <div>
                            <strong>
                              {invitation.invited_username ?? "Invited user"}
                            </strong>
                            <span>
                              Pending invitation
                              {invitation.created_at
                                ? ` · ${new Date(invitation.created_at).toLocaleString()}`
                                : ""}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {activeTab === "questions" && (
                <div className="workspace-questions">
                  <div className="workspace-question-create">
                    <h3>Post a Question</h3>

                    <textarea
                      value={questionText}
                      onChange={(event) => setQuestionText(event.target.value)}
                      placeholder="Enter a computational problem..."
                      rows={4}
                    />

                    <div className="workspace-form-row">

                      <select
                        value={visibility}
                        onChange={(event) => setVisibility(event.target.value)}
                      >
                        <option value="public">Public</option>
                        <option value="private">Private</option>
                      </select>

                      <label
                        className="secondary"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          cursor: workspaceImageUploading ? "wait" : "pointer",
                        }}
                      >
                        {workspaceImageUploading ? "Uploading..." : "Attach Image"}
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
                          onChange={(event) => void selectWorkspaceImage(event)}
                          disabled={busy || workspaceImageUploading}
                          style={{ display: "none" }}
                        />
                      </label>
                      <button
                        type="button"
                        className="primary"
                        onClick={() => void createQuestion()}
                        disabled={busy || workspaceImageUploading || (!questionText.trim() && !workspaceImage)}
                      >
                        Post Question
                      </button>
                    </div>
                  </div>

                  {workspaceImagePreview && (
                    <div
                      className="workspace-image-preview-marker"
                      style={{
                        marginTop: "12px",
                        position: "relative",
                        width: "fit-content",
                      }}
                    >
                      <img
                        src={workspaceImagePreview}
                        alt="Attached question"
                        style={{
                          display: "block",
                          maxWidth: "320px",
                          maxHeight: "220px",
                          borderRadius: "10px",
                          border: "1px solid rgba(255,255,255,0.14)",
                          objectFit: "contain",
                        }}
                      />
                      <button
                        type="button"
                        className="secondary"
                        onClick={removeWorkspaceImage}
                        disabled={busy || workspaceImageUploading}
                        style={{
                          position: "absolute",
                          top: "8px",
                          right: "8px",
                          padding: "4px 8px",
                          minWidth: "auto",
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  )}
                  <div className="workspace-question-columns">
                    <div className="workspace-question-list">
                      <div className="workspace-card-header">
                        <div>
                          <h3>Questions</h3>
                          <span>{questions.length} posted</span>
                        </div>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => void refreshQuestions()}
                        >
                          Refresh
                        </button>
                      </div>

                      {questions.length === 0 ? (
                        <div className="workspace-empty">
                          No questions have been posted yet.
                        </div>
                      ) : (
                        questions.map((question, questionIndex) => (
                          <button
                            type="button"
                            className={`workspace-question-item ${selectedQuestion?.id === question.id ? "active" : ""
                              }`}
                            key={question.id}
                            onClick={() => void openQuestion(Number(question.id))}
                          >
                            <strong>
                              Question {questionIndex + 1}
                            </strong>
                            <div className="workspace-question-title">
                              {question.question}
                            </div>
                            <span>
                              {question.visibility ?? "public"}
                            </span>
                          </button>
                        ))
                      )}
                    </div>

                    <div className="workspace-question-detail">
                      {!selectedQuestion ? (
                        <div className="workspace-empty">
                          Select a question to view its details and solution.
                        </div>
                      ) : (
                        <>
                          <span className="eyebrow">Question</span>
                          <h3>{selectedQuestion.question}</h3>

                          {(
                            isAdmin ||
                            Number(selectedQuestion.author_id) === Number(user.id)
                          ) && (
                            <button
                              type="button"
                              className="secondary"
                              onClick={() => void deleteQuestion(selectedQuestion)}
                              disabled={busy}
                            >
                              Delete Question
                            </button>
                          )}

                          <div className="workspace-detail-meta">
                            <span>{selectedQuestion.visibility ?? "public"}</span>
                            <span>Status: {selectedQuestion.status ?? "active"}</span>
                            {selectedQuestion.image_path && (
                              <button
                                type="button"
                                className="workspace-attachment-button"
                                onClick={() =>
                                  setAttachmentUrl(
                                    getQuestionImageUrl(
                                      selectedQuestion.image_path as string,
                                    ),
                                  )
                                }
                              >
                                View attachment
                              </button>
                            )}
                          </div>

                          <div className="workspace-compute-row">

                            <button
                              type="button"
                              className="primary"
                              onClick={() => void computeQuestion()}
                              disabled={busy}
                            >
                              Solve
                            </button>

                            <button
                              type="button"
                              className="secondary"
                              onClick={() => void createAttempt()}
                              disabled={busy}
                            >
                              Guided Attempt
                            </button>
                          </div>

                          {solution && (
                            <div className="workspace-solution">
                              <div className="workspace-solution-header">
                                <span className="eyebrow">Solution</span>
                                <span>
                                  {solution.status ?? "completed"}
                                </span>
                              </div>

                              <div className="workspace-solution-content">
                                {(() => {
                                  const rawSolution = solution.result_json as any;

                                  let solutionData: any = rawSolution;

                                  if (typeof solutionData === "string") {
                                    try {
                                      solutionData = JSON.parse(solutionData);
                                    } catch {
                                      solutionData = {
                                        solution: solutionData,
                                      };
                                    }
                                  }

                                  const resultData =
                                    solutionData?.result_json ??
                                    solutionData?.result ??
                                    solutionData;

                                  let readableData: any = resultData;

                                  if (typeof readableData === "string") {
                                    try {
                                      readableData = JSON.parse(readableData);
                                    } catch {
                                      readableData = {
                                        solution: readableData,
                                      };
                                    }
                                  }

                                  const originalQuestion =
                                    readableData?.user_question;

                                  const solutionText =
                                    originalQuestion?.solution ??
                                    readableData?.solution ??
                                    readableData?.explanation ??
                                    readableData?.final_solution;

                                  return (
                                    <>
                                      {originalQuestion?.question && (
                                        <h4>{String(originalQuestion.question)}</h4>
                                      )}

                                      {typeof solutionText === "string" ? (
                                        <WorkspaceSolutionText className="workspace-guided-solution-text">
                                          {solutionText}
                                        </WorkspaceSolutionText>
                                      ) : (
                                        <pre>
                                          {JSON.stringify(readableData, null, 2)}
                                        </pre>
                                      )}
                                    </>
                                  );
                                })()}
                              </div>
                            </div>
                          )}

                          {followUps.length > 0 && (
                            <div className="workspace-followups">
                              <div className="workspace-card-header">
                                <div>
                                  <h3>Follow-ups</h3>
                                  <span>{followUps.length} answered</span>
                                </div>
                              </div>

                              {followUps.map((item, index) => (
                                <div
                                  className="workspace-followup-item"
                                  key={item.id ?? `${item.created_at ?? "followup"}-${index}`}
                                >
                                  <div className="workspace-followup-question">
                                    <strong>You asked</strong>
                                    <p>{item.question}</p>
                                  </div>

                                  {item.answer && (
                                    <div className="workspace-followup-answer">
                                      <strong>Answer</strong>
                                      <WorkspaceRichText>
                                        {item.answer}
                                      </WorkspaceRichText>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                          <div className="workspace-attempts">
                            <div className="workspace-card-header">
                              <div>
                                <h3>Attempts</h3>
                                <span>{attempts.length} recorded</span>
                              </div>
                            </div>

                            {attempts.map((attempt) => (
                              <div className="workspace-attempt-item" key={attempt.id}>
                                <strong>
                                  Attempt #{attempt.id}
                                </strong>
                                <span>
                                  {String(attempt.status ?? "in progress")}
                                  {attempt.score != null
                                    ? ` · Score: ${attempt.score}`
                                    : ""}
                                </span>
                              </div>
                            ))}
                          </div>

                          <div className="workspace-follow-up">
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
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "members" && (
                <div className="workspace-members">
                  <div className="workspace-card-header">
                    <div>
                      <h3>Members</h3>
                      <span>{members.length} members</span>
                    </div>
                  </div>

                  {isAdmin && (
                    <div className="workspace-create-row">
                      <input
                        value={inviteUsername}
                        onChange={(event) =>
                          setInviteUsername(event.target.value)
                        }
                        placeholder="Username to invite"
                      />
                      <button
                        type="button"
                        className="primary"
                        onClick={() => void sendInvitation()}
                        disabled={busy || !inviteUsername.trim()}
                      >
                        Invite
                      </button>
                    </div>
                  )}

                  <div className="workspace-member-table">
                    <div className="workspace-member-table-head">
                      <span>Username</span>
                      <span>Role</span>
                      <span className="workspace-member-actions-heading">
                        Actions
                      </span>
                    </div>

                    {members.length === 0 ? (
                      <div className="workspace-empty">
                        No members found in this workspace.
                      </div>
                    ) : (
                      members.map((member) => {
                        const memberActionKey = String(
                          member.user_id ??
                          member.id ??
                          member.username ??
                          "member",
                        );
                        const isMemberOwner = member.role === "owner";
                        const isMemberAdmin = member.role === "admin";
                        const isCurrentUser =
                          member.user_id !== undefined &&
                          String(member.user_id) === String(user.id);
                        const canRemoveMember =
                          isAdmin &&
                          !isCurrentUser &&
                          !isMemberOwner &&
                          !!member.username &&
                          (selectedWorkspace?.role === "owner" ||
                            !isMemberAdmin);
                        const canTransferOwnership =
                          selectedWorkspace?.role === "owner" &&
                          !isCurrentUser &&
                          !isMemberOwner &&
                          !!member.username;

                        return (
                          <div
                            className="workspace-member-table-row"
                            key={memberActionKey}
                          >
                            <div className="workspace-member-identity">
                              <strong>
                                {member.username ??
                                  `User ${member.user_id}`}
                              </strong>
                            </div>

                            <div>
                              <span
                                className={`workspace-member-role workspace-member-role-${member.role ?? "member"}`}
                              >
                                {isMemberOwner
                                  ? "Owner"
                                  : isMemberAdmin
                                    ? "Admin"
                                    : "Member"}
                              </span>
                            </div>

                            <div className="workspace-member-actions">
                              {isAdmin && (
                                <div className="workspace-member-menu">
                                  <button
                                    type="button"
                                    className="workspace-member-menu-button"
                                    aria-label={`Actions for ${member.username ?? "member"}`}
                                    title="Member actions"
                                    onClick={() =>
                                      setOpenMemberMenu((current) =>
                                        current === memberActionKey
                                          ? null
                                          : memberActionKey,
                                      )
                                    }
                                    disabled={
                                      busy || performanceLoading
                                    }
                                  >
                                    <span aria-hidden="true">?</span>
                                  </button>

                                  {openMemberMenu === memberActionKey && (
                                    <div className="workspace-member-menu-panel">
                                      {member.user_id && (
                                        <button
                                          type="button"
                                          className="workspace-member-menu-item"
                                          onClick={() => {
                                            setOpenMemberMenu(null);
                                            void showMemberPerformance(
                                              member,
                                            );
                                          }}
                                          disabled={
                                            busy || performanceLoading
                                          }
                                        >
                                          Performance
                                        </button>
                                      )}

                                      {member.username &&
                                        !isMemberOwner &&
                                        !isMemberAdmin && (
                                          <button
                                            type="button"
                                            className="workspace-member-menu-item"
                                            onClick={async () => {
                                              if (
                                                !selectedWorkspace?.id ||
                                                !member.username
                                              ) {
                                                return;
                                              }

                                              setOpenMemberMenu(null);

                                              try {
                                                await promoteWorkspaceMember(
                                                  Number(
                                                    selectedWorkspace.id,
                                                  ),
                                                  member.username,
                                                );
                                                await loadWorkspace(
                                                  Number(
                                                    selectedWorkspace.id,
                                                  ),
                                                );
                                                setMessage(
                                                  `${member.username} promoted.`,
                                                );
                                              } catch (err) {
                                                setError(
                                                  err instanceof Error
                                                    ? err.message
                                                    : "Unable to promote member.",
                                                );
                                              }
                                            }}
                                            disabled={busy}
                                          >
                                            Promote
                                          </button>
                                        )}

                                      {canRemoveMember && (
                                        <button
                                          type="button"
                                          className="workspace-member-menu-item"
                                          onClick={() =>
                                            void removeMember(member)
                                          }
                                          disabled={busy}
                                        >
                                          Remove member
                                        </button>
                                      )}

                                      {canTransferOwnership && (
                                        <button
                                          type="button"
                                          className="workspace-member-menu-item workspace-member-menu-item-danger"
                                          onClick={() =>
                                            void transferOwnership(member)
                                          }
                                          disabled={busy}
                                        >
                                          Transfer ownership
                                        </button>
                                      )}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              )}

              {activeTab === "settings" && (
                <WorkspaceSettingsPanel
                  workspace={selectedWorkspace}
                  settings={settings}
                  enabled={isAdmin}
                  busy={busy}
                  onSaved={(nextSettings) => {
                    setSettings(nextSettings);
                    setMessage("Workspace settings updated.");
                  }}
                  onError={setError}
                />
              )}
            </>
          )}
        </section>
      </div>

      <div className="workspace-user">
        Signed in as <strong>{user.username}</strong>
      </div>
      {performanceMember && (
        <div className="workspace-member-performance-overlay">
          <div className="workspace-member-performance-modal">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "16px",
                marginBottom: "18px",
              }}
            >
              <div>
                <h2 style={{ margin: 0 }}>
                  {performanceMember.username ?? "Member"} Performance
                </h2>
                <p style={{ margin: "6px 0 0", opacity: 0.7 }}>
                  Workspace attempts and results
                </p>
              </div>

              <button
                type="button"
                className="secondary"
                onClick={() => setPerformanceMember(null)}
              >
                Close
              </button>
            </div>

            {performanceLoading ? (
              <p>Loading performance...</p>
            ) : memberPerformance.length === 0 ? (
              <p>No attempts recorded for this member.</p>
            ) : (
              (() => {
                const scoredAttempts = memberPerformance.filter(
                  (attempt) =>
                    typeof attempt.score_percent === "number" &&
                    Number.isFinite(attempt.score_percent),
                );

                const averagePercent =
                  scoredAttempts.length > 0
                    ? scoredAttempts.reduce(
                      (sum, attempt) =>
                        sum + Number(attempt.score_percent),
                      0,
                    ) / scoredAttempts.length
                    : null;

                return (
                  <div className="workspace-performance-content">
                    <div className="workspace-performance-summary">
                      <div className="workspace-stat-card">
                        <strong>{memberPerformance.length}</strong>
                        <span>Total Attempts</span>
                      </div>

                      <div className="workspace-stat-card">
                        <strong>
                          {
                            memberPerformance.filter(
                              (attempt) => attempt.status === "completed",
                            ).length
                          }
                        </strong>
                        <span>Completed</span>
                      </div>

                      <div className="workspace-stat-card">
                        <strong>
                          {averagePercent == null
                            ? "—"
                            : `${averagePercent.toFixed(1)}%`}
                        </strong>
                        <span>Average Score</span>
                      </div>
                    </div>

                    <div className="workspace-performance-table">
                      <div className="workspace-performance-table-head">
                        <div>Attempt</div>
                        <div>Question</div>
                        <div>Score</div>
                        <div>Status</div>
                        <div>Started</div>
                      </div>

                      <div className="workspace-performance-table-body">
                        {memberPerformance.map((attempt, attemptIndex) => (
                          <div
                            key={String(attempt.id ?? attemptIndex)}
                            className="workspace-performance-table-row"
                          >
                            <div className="workspace-performance-attempt-number">
                              Attempt {attemptIndex + 1}
                            </div>

                            <div className="workspace-performance-question-cell">
                              <div className="workspace-performance-question-scroll">
                                {attempt.question?.trim() ||
                                  "Question text unavailable"}
                              </div>

                              {attempt.image_path && (
                                <button
                                  type="button"
                                  className="workspace-performance-attachment"
                                  onClick={() =>
                                    setAttachmentUrl(
                                      getQuestionImageUrl(
                                        attempt.image_path as string,
                                      ),
                                    )
                                  }
                                >
                                  View attachment
                                </button>
                              )}
                            </div>

                            <div className="workspace-performance-score">
                              {attempt.score_label ??
                                (typeof attempt.score === "number"
                                  ? String(attempt.score)
                                  : "—")}
                              {typeof attempt.score_percent === "number" && (
                                <small>
                                  {attempt.score_percent.toFixed(1)}%
                                </small>
                              )}
                            </div>

                            <div className="workspace-performance-status">
                              {attempt.status ?? "unknown"}
                            </div>

                            <div className="workspace-performance-date">
                              {attempt.started_at
                                ? new Date(
                                  attempt.started_at,
                                ).toLocaleString()
                                : "Unknown"}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })()
            )}
          </div>
        </div>
      )}
      {attachmentUrl && (
        <div
          className="workspace-attachment-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="Question attachment"
          onClick={() => setAttachmentUrl(null)}
        >
          <div
            className="workspace-attachment-viewer"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="workspace-attachment-viewer-header">
              <strong>Question Attachment</strong>
              <button
                type="button"
                className="secondary"
                onClick={() => setAttachmentUrl(null)}
              >
                Close
              </button>
            </div>

            <div className="workspace-attachment-image-wrap">
              <img
                src={attachmentUrl}
                alt="Original question attachment"
                className="workspace-attachment-image"
              />
            </div>
          </div>
        </div>
      )}
      {guidedAttempt && (
        <div className="workspace-attempt-overlay">
          <div className="workspace-attempt-window">
            {!guidedAttempt.completed ? (
              <>
                <div className="workspace-attempt-header">
                  <div>
                    <span className="eyebrow">Guided Attempt</span>
                    <h2>
                      Question {guidedAttempt.currentIndex + 1} of{" "}
                      {guidedAttempt.questions.length}
                    </h2>
                  </div>

                  <div className="workspace-attempt-header-actions">
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => void closeGuidedAttempt("exit")}
                      disabled={busy}
                    >
                      Exit
                    </button>

                    <button
                      type="button"
                      className="secondary"
                      onClick={() => void closeGuidedAttempt("terminate")}
                      disabled={busy}
                    >
                      Terminate
                    </button>
                  </div>
                </div>

                <div className="workspace-attempt-progress">
                  <div
                    className="workspace-attempt-progress-fill"
                    style={{
                      width: `${((guidedAttempt.currentIndex + 1) /
                          guidedAttempt.questions.length) *
                        100
                        }%`,
                    }}
                  />
                </div>

                {(() => {
                  const question =
                    guidedAttempt.questions[guidedAttempt.currentIndex];

                  if (!question) {
                    return (
                      <div className="workspace-empty">
                        No question is available.
                      </div>
                    );
                  }

                  const selectedAnswer =
                    guidedAttempt.answers[guidedAttempt.currentIndex];

                  const showHint =
                    guidedAttempt.hints[guidedAttempt.currentIndex] === true;

                  const options = Array.isArray(question.options)
                    ? question.options
                    : [];

                  return (
                    <div className="workspace-attempt-body">
                      <div className="workspace-attempt-card">
                        <span className="eyebrow">Question</span>

                        <h3>
                          {String(
                            question.question ??
                            question.text ??
                            "",
                          )}
                        </h3>

                        <div className="workspace-attempt-options">
                          {options.map(
                            (option: unknown, optionIndex: number) => {
                              const optionNumber = optionIndex + 1;

                              return (
                                <button
                                  key={optionIndex}
                                  type="button"
                                  className={`workspace-attempt-option${selectedAnswer === optionNumber
                                      ? " selected"
                                      : ""
                                    }`}
                                  onClick={() =>
                                    setGuidedAttempt((current) =>
                                      current
                                        ? {
                                          ...current,
                                          answers: {
                                            ...current.answers,
                                            [current.currentIndex]:
                                              optionNumber,
                                          },
                                        }
                                        : current,
                                    )
                                  }
                                >
                                  <span className="workspace-attempt-option-number">
                                    {String.fromCharCode(65 + optionIndex)}
                                  </span>

                                  <span>{String(option)}</span>
                                </button>
                              );
                            },
                          )}
                        </div>

                        <div className="workspace-attempt-hint-area">
                          <button
                            type="button"
                            className="secondary"
                            onClick={() =>
                              setGuidedAttempt((current) =>
                                current
                                  ? {
                                    ...current,
                                    hints: {
                                      ...current.hints,
                                      [current.currentIndex]:
                                        !showHint,
                                    },
                                  }
                                  : current,
                              )
                            }
                          >
                            {showHint ? "Hide Hint" : "Show Hint"}
                          </button>

                          {showHint && (
                            <div className="workspace-attempt-hint">
                              {String(
                                question.hint ??
                                "No hint is available for this question.",
                              )}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="workspace-attempt-stats">
                        <span>
                          Correct: <strong>{guidedAttempt.correct}</strong>
                        </span>
                        <span>
                          Wrong: <strong>{guidedAttempt.wrong}</strong>
                        </span>
                      </div>

                      <div className="workspace-attempt-actions">
                        <button
                          type="button"
                          className="secondary"
                          onClick={() =>
                            setGuidedAttempt((current) =>
                              current
                                ? {
                                  ...current,
                                  currentIndex: Math.max(
                                    0,
                                    current.currentIndex - 1,
                                  ),
                                }
                                : current,
                            )
                          }
                          disabled={busy || guidedAttempt.currentIndex === 0}
                        >
                          Previous
                        </button>

                        {guidedAttempt.currentIndex <
                          guidedAttempt.questions.length - 1 ? (
                          <button
                            type="button"
                            className="primary"
                            onClick={() =>
                              setGuidedAttempt((current) =>
                                current
                                  ? {
                                    ...current,
                                    currentIndex:
                                      current.currentIndex + 1,
                                  }
                                  : current,
                              )
                            }
                            disabled={busy || selectedAnswer == null}
                          >
                            Next
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="primary"
                            onClick={() => void finishGuidedAttempt()}
                            disabled={busy || selectedAnswer == null}
                          >
                            Finish Attempt
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })()}
              </>
            ) : (
              <div className="workspace-attempt-complete">
                <span className="eyebrow">Attempt Complete</span>

                <h2>Guided Attempt Complete</h2>

                <div className="workspace-attempt-final-stats">
                  <div>
                    <strong>{guidedAttempt.correct}</strong>
                    <span>Correct</span>
                  </div>

                  <div>
                    <strong>{guidedAttempt.wrong}</strong>
                    <span>Wrong</span>
                  </div>

                  <div>
                    <strong>
                      {guidedAttempt.questions.length > 0
                        ? Math.round(
                          (guidedAttempt.correct /
                            guidedAttempt.questions.length) *
                          100,
                        )
                        : 0}
                      %
                    </strong>
                    <span>Score</span>
                  </div>
                </div>

                <div className="workspace-attempt-solution">
                  <div className="workspace-solution-header">
                    <span className="eyebrow">Solution</span>
                    <span>Completed</span>
                  </div>

                  <div className="workspace-guided-solution-content">
                    {(() => {
                      const rawSolution = guidedAttempt.solution as any;

                      let solutionData: any = rawSolution;

                      if (typeof solutionData === "string") {
                        try {
                          solutionData = JSON.parse(solutionData);
                        } catch {
                          solutionData = {
                            solution: solutionData,
                          };
                        }
                      }

                      const resultData =
                        solutionData?.result_json ??
                        solutionData?.result ??
                        solutionData;

                      let readableData: any = resultData;

                      if (typeof readableData === "string") {
                        try {
                          readableData = JSON.parse(readableData);
                        } catch {
                          readableData = {
                            solution: readableData,
                          };
                        }
                      }

                      const originalQuestion =
                        readableData?.user_question;

                      const solutionText =
                        originalQuestion?.solution ??
                        readableData?.solution ??
                        readableData?.explanation ??
                        readableData?.final_solution;

                      return (
                        <>
                          {originalQuestion?.question && (
                            <h3>{String(originalQuestion.question)}</h3>
                          )}

                          {typeof solutionText === "string" ? (
                            <WorkspaceRichText className="workspace-guided-solution-text">
                              {solutionText}
                            </WorkspaceRichText>
                          ) : (
                            <pre>
                              {JSON.stringify(readableData, null, 2)}
                            </pre>
                          )}

                          <div className="workspace-guided-review">
                            <h3>Answer review</h3>

                            {guidedAttempt.questions.map(
                              (question: any, index: number) => {
                                const selected =
                                  guidedAttempt.answers[index];

                                const correct =
                                  Number(question.correct_option);

                                const isCorrect = selected === correct;

                                return (
                                  <div
                                    className={`workspace-guided-review-item ${isCorrect ? "correct" : "incorrect"
                                      }`}
                                    key={index}
                                  >
                                    <strong>
                                      {index + 1}.{" "}
                                      {String(
                                        question.question ??
                                        question.text ??
                                        "",
                                      )}
                                    </strong>

                                    <span>
                                      Your answer:{" "}
                                      {selected == null
                                        ? "Not answered"
                                        : String(
                                          question.options?.[selected - 1] ??
                                          selected,
                                        )}
                                    </span>

                                    <span>
                                      Correct answer:{" "}
                                      {String(
                                        question.options?.[correct - 1] ??
                                        correct,
                                      )}
                                    </span>
                                  </div>
                                );
                              },
                            )}
                          </div>
                        </>
                      );
                    })()}
                  </div>
                </div>

                <div className="workspace-attempt-actions">
                  <button
                    type="button"
                    className="primary"
                    onClick={() => setGuidedAttempt(null)}
                  >
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

    </motion.div>
  );
}

function WorkspaceSettingsPanel({
  workspace,
  settings,
  enabled,
  busy,
  onSaved,
  onError,
}: {
  workspace: Workspace;
  settings: WorkspaceSettings | null;
  enabled: boolean;
  busy: boolean;
  onSaved: (settings: WorkspaceSettings) => void;
  onError: (message: string) => void;
}) {
  const [allowPosting, setAllowPosting] = useState(
    settings?.allow_member_posting ?? true,
  );
  const [allowSolving, setAllowSolving] = useState(
    settings?.allow_member_solving ?? true,
  );

  useEffect(() => {
    setAllowPosting(settings?.allow_member_posting ?? true);
    setAllowSolving(settings?.allow_member_solving ?? true);
  }, [settings]);

  async function save() {
    if (!enabled || workspace.id == null) return;

    try {
      const response = await updateWorkspaceSettings({
        WorkspaceId: Number(workspace.id),
        ComputationMode: "online",
        AllowMemberPosting: allowPosting,
        AllowMemberSolving: allowSolving,
      });

      onSaved(response.data as WorkspaceSettings);
    } catch (err) {
      onError(
        err instanceof Error
          ? err.message
          : "Unable to update workspace settings.",
      );
    }
  }

  return (
    <div className="workspace-settings">
      <div className="workspace-card-header">
        <div>
          <h3>Workspace Settings</h3>
          <span>
            {enabled
              ? "Owner/admin controls"
              : "Only workspace owners and admins can change these settings."}
          </span>
        </div>
      </div>

      <label className="workspace-setting-toggle">
        <input
          type="checkbox"
          checked={allowPosting}
          onChange={(event) => setAllowPosting(event.target.checked)}
          disabled={!enabled}
        />
        <span>Allow members to post questions</span>
      </label>

      <label className="workspace-setting-toggle">
        <input
          type="checkbox"
          checked={allowSolving}
          onChange={(event) => setAllowSolving(event.target.checked)}
          disabled={!enabled}
        />
        <span>Allow members to solve questions</span>
      </label>

      <button
        type="button"
        className="primary"
        onClick={() => void save()}
        disabled={!enabled || busy}
      >
        Save Settings
      </button>
    </div>
  );
}

function LoadingState({ message }: { message: string }) {
  return (
    <motion.div className="center-state" aria-live="polite" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <motion.div
        className="spinner"
        aria-hidden="true"
        animate={{ rotate: 360 }}
        transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }}
      />
      <h2>{message}</h2>
      <p>Please wait while Stepwise Prism AI prepares your session.</p>
    </motion.div>
  );
}

function Composer({
  value,
  onChange,
  onSubmit,
  onImage,
  onOpenVoice,
  disabled,
  graphical,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onImage: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onOpenVoice: () => void;
  disabled: boolean;
  graphical: boolean;
}) {
  const placeholder = "Ask your question...";

  return (
    <div className="composer-outer-wrapper" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', width: '100%' }}>

      {/* The main text input box */}
      <motion.div
        className="composer"
        style={{ flex: 1 }}
        whileHover={{ y: -2 }}
        transition={{ type: "spring", stiffness: 250, damping: 20 }}
      >
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit();
            }
          }}
          placeholder={placeholder}
          aria-label={placeholder}
          disabled={disabled}
        />

        {!graphical && (
          <label className="icon-button" aria-label="Upload image">
            📎
            <input
              type="file"
              accept="image/*,.jpg,.jpeg,.png,.webp,.heic,.heif"
              hidden
              onChange={onImage}
              disabled={disabled}
            />
          </label>
        )}

        <motion.button
          className="send"
          whileHover={{ scale: 1.08, rotate: -5 }}
          whileTap={{ scale: 0.9 }}
          onClick={onSubmit}
          disabled={disabled}
          aria-label="Send"
        >
          ➤
        </motion.button>
      </motion.div>

      {/* Voice Tutor Button - Outside on the right and hidden in graphical mode */}
      {!graphical && (
        <motion.button
          type="button"
          className="voice-btn-outside"
          whileHover={{ scale: 1.08, y: -2 }}
          whileTap={{ scale: 0.92 }}
          onClick={onOpenVoice}
          disabled={disabled}
          aria-label="Open Voice Tutor"
          title="Live Voice Tutor"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" x2="12" y1="19" y2="22" />
          </svg>
        </motion.button>
      )}

    </div>
  );
}

function GraphEditor({
  coordinates,
  onChange,
}: {
  coordinates: Coordinate[];
  onChange: (coordinates: Coordinate[]) => void;
}) {
  return (
    <motion.div className="graph-editor" initial={{ opacity: 0, height: 0, y: -10 }} animate={{ opacity: 1, height: "auto", y: 0 }} exit={{ opacity: 0, height: 0 }} transition={{ type: "spring", stiffness: 150, damping: 20 }}>
      <div className="graph-editor-header">
        <div>
          <strong>Graph</strong>
          <span>{coordinates.length}/4 points</span>
        </div>
        <div className="graph-editor-actions">
          <button
            type="button"
            className="graph-control"
            onClick={() => onChange([...coordinates, [0, 0]])}
            disabled={coordinates.length >= 4}
          >
            + Add point
          </button>
          <button
            type="button"
            className="graph-control"
            onClick={() => onChange(coordinates.slice(0, -1))}
            disabled={coordinates.length === 0}
          >
            − Remove point
          </button>
        </div>
      </div>
      <GraphCanvas coordinates={coordinates} editable onChange={onChange} />
      <p className="graph-help">Drag points to place them on the 20 × 20 grid.</p>
    </motion.div>
  );
}

function GraphCanvas({
  coordinates,
  editable = false,
  onChange,
}: {
  coordinates: Coordinate[];
  editable?: boolean;
  onChange?: (coordinates: Coordinate[]) => void;
}) {
  const size = 540;
  const graphPadding = 30;
  const origin = size / 2;
  const plotSize = size - graphPadding * 2;
  const largestCoordinate = coordinates.reduce(
    (largest, [x, y]) => Math.max(largest, Math.abs(x), Math.abs(y)),
    0,
  );
  const axisLimit = editable
    ? 20
    : Math.max(10, Math.ceil((largestCoordinate + 10) / 10) * 10);
  const unit = plotSize / (axisLimit * 2);
  const toSvg = ([x, y]: Coordinate) => [origin + x * unit, origin - y * unit];

  function movePoint(index: number, event: React.PointerEvent<SVGCircleElement>) {
    if (!editable || !onChange) return;
    const svg = event.currentTarget.ownerSVGElement;
    if (!svg) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const update = (moveEvent: PointerEvent) => {
      const rect = svg.getBoundingClientRect();
      const x = ((moveEvent.clientX - rect.left) / rect.width) * size;
      const y = ((moveEvent.clientY - rect.top) / rect.height) * size;
      const next: Coordinate = [
        Math.max(-axisLimit, Math.min(axisLimit, Math.round(((x - origin) / unit) * 2) / 2)),
        Math.max(-axisLimit, Math.min(axisLimit, Math.round(((origin - y) / unit) * 2) / 2)),
      ];
      onChange(coordinates.map((point, pointIndex) => pointIndex === index ? next : point));
    };
    const stop = () => {
      window.removeEventListener("pointermove", update);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", update);
    window.addEventListener("pointerup", stop, { once: true });
  }

  return (
    <svg
      className={`graph-canvas ${editable ? "editable" : ""}`}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label="Coordinate graph"
      onPointerDown={(event) => { if (editable && event.target === event.currentTarget) event.preventDefault(); }}
    >
      <rect width={size} height={size} className="graph-background" />
      {Array.from({ length: 21 }, (_, index) => {
        const label = -axisLimit + index * (axisLimit / 10);
        const position = graphPadding + index * (plotSize / 20);
        return <g key={index}>
          <line x1={position} y1="0" x2={position} y2={size} className="graph-grid-line" />
          <line x1="0" y1={position} x2={size} y2={position} className="graph-grid-line" />
          {label !== 0 && label % 2 === 0 && <>
            <text x={position} y={origin + 16} textAnchor="middle" className="graph-coordinate-label">{label}</text>
            <text x={origin - 7} y={origin - label * unit + 4} textAnchor="end" className="graph-coordinate-label">{label}</text>
          </>}
        </g>;
      })}
      <line x1="0" y1={origin} x2={size} y2={origin} className="graph-axis" />
      <line x1={origin} y1={size} x2={origin} y2="0" className="graph-axis" />
      <text x="16" y={origin - 8} className="graph-axis-label">x&apos;</text>
      <text x={size - 18} y={origin - 8} className="graph-axis-label">x</text>
      <text x={origin + 8} y="20" className="graph-axis-label">y</text>
      <text x={origin + 8} y={size - 10} className="graph-axis-label">y&apos;</text>
      <text x={origin + 8} y={origin + 16} className="graph-axis-label">O</text>
      {coordinates.length >= 3 && <polygon points={coordinates.map(toSvg).map(([x, y]) => `${x},${y}`).join(" ")} className="graph-line" />}
      {coordinates.length === 2 && <polyline points={coordinates.map(toSvg).map(([x, y]) => `${x},${y}`).join(" ")} className="graph-line" />}
      {coordinates.map((point, index) => {
        const [x, y] = toSvg(point);
        return <g key={index}><circle cx={x} cy={y} r="8" className={`graph-point point-${index}`} onPointerDown={(event) => movePoint(index, event)} /><text x={x + 10} y={y - 10} className="graph-point-label">P{index + 1} ({point[0]}, {point[1]})</text></g>;
      })}
    </svg>
  );
}

function Quiz({
  question,
  current,
  total,
  progress,
  selected,
  showHint,
  finalQuestion = false,
  learnAgain = false,
  onSelect,
  onHint,
  onNext,
  onPrevious,
}: {
  question: Question;
  current: number;
  total: number;
  progress: number;
  selected: number | null;
  showHint: boolean;
  finalQuestion?: boolean;
  learnAgain?: boolean;
  onSelect: (option: number) => void;
  onHint: () => void;
  onNext: () => void;
  onPrevious: () => void;
}) {
  return (
    <motion.div className="quiz-page" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      <motion.div className="quiz-header" initial={{ y: -14, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.35 }}>
        <span>
          {finalQuestion
            ? "Your original question"
            : learnAgain
              ? `Learn Again · Question ${current + 1} of ${total}`
              : `Question ${current + 1} of ${total}`}
        </span>
        {!finalQuestion && <div className="progress-track"><div style={{ width: `${progress}%` }} /></div>}
      </motion.div>

      <motion.section className="quiz-card" layout transition={{ type: "spring", stiffness: 170, damping: 24 }}>
        {question.coordinates && question.coordinates.length > 0 && <GraphCanvas coordinates={question.coordinates} />}
        <h1><MathText>{question.question}</MathText></h1>
        <motion.div className="options" role="radiogroup" aria-label="Answer options" variants={{ show: { transition: { staggerChildren: 0.07 } } }} initial="hidden" animate="show">
          {question.options.map((option, index) => {
            const number = index + 1;
            const selectedClass = selected === number ? " selected" : "";
            return (
              <motion.button
                key={`${number}-${option}`}
                variants={{ hidden: { opacity: 0, x: -20 }, show: { opacity: 1, x: 0 } }}
                whileHover={{ scale: 1.018, x: 5 }}
                whileTap={{ scale: 0.985 }}
                type="button"
                role="radio"
                aria-checked={selected === number}
                className={`option${selectedClass}`}
                onClick={() => onSelect(number)}
              >
                <span className="option-letter">{String.fromCharCode(64 + number)}</span>
                <MathText>{option}</MathText>
              </motion.button>
            );
          })}
        </motion.div>

        <div className="hint-area">
          {!showHint ? (
            <button type="button" className="hint-button" onClick={onHint}>💡 Need a hint?</button>
          ) : (
            <motion.div className="hint" initial={{ opacity: 0, height: 0, y: 8 }} animate={{ opacity: 1, height: "auto", y: 0 }} transition={{ type: "spring", stiffness: 170, damping: 20 }}>
              <strong>💡 Hint</strong>
              <MathText>{question.hint}</MathText>
            </motion.div>
          )}
        </div>

        <div className="quiz-actions">
          {current > 0 || finalQuestion ? (
            <button type="button" className="secondary" onClick={onPrevious}>← Previous</button>
          ) : <span />}
          <motion.button
            type="button"
            whileHover={{ scale: 1.035, y: -2 }}
            whileTap={{ scale: 0.97 }}
            className="primary"
            onClick={onNext}
            disabled={selected == null}
          >
            {finalQuestion ? "Submit Answer" : current === total - 1 ? "Finish →" : "Next →"}
          </motion.button>
        </div>
      </motion.section>
    </motion.div>
  );
}

type ReviewItem = {
  question: Question;
  index: number;
  selected: number | null;
  correct: boolean;
};

function QuestionReview({
  review,
  loadingIndex,
  onLearnAgain,
  hideLearnAgain = false,
}: {
  review: ReviewItem[];
  loadingIndex: number | null;
  onLearnAgain: (question: Question, index: number) => void;
  hideLearnAgain?: boolean;
}) {
  return (
    <section className="review-section" aria-labelledby="review-title">
      <div className="review-heading">
        <div>
          <span className="eyebrow">Performance</span>
          <h2 id="review-title">Question Review</h2>
        </div>
        <span className="review-count">{review.length} questions</span>
      </div>

      <div className="review-list">
        {review.map((item, index) => (
          <motion.article className="review-item" key={item.index} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.06, duration: 0.35 }} whileHover={{ y: -3, scale: 1.005 }}>
            <div className={`review-status ${item.correct ? "correct" : "incorrect"}`} aria-label={item.correct ? "Correct" : "Incorrect"}>
              {item.correct ? "✓" : "×"}
            </div>
            <div className="review-content">
              <div className="review-number">Question {item.index + 1}</div>
              <div className="review-question"><MathText>{item.question.question}</MathText></div>
              {item.selected != null && (
                <div className="review-answer">
                  Your answer: <strong><MathText>{item.question.options[item.selected - 1]}</MathText></strong>
                  {!item.correct && <> · Correct: <strong><MathText>{item.question.options[item.question.correct_option - 1]}</MathText></strong></>}
                </div>
              )}
            </div>
            {!item.correct && !hideLearnAgain && (
              <button
                type="button"
                className="secondary learn-button"
                onClick={() => onLearnAgain(item.question, item.index)}
                disabled={loadingIndex !== null}
              >
                {loadingIndex === item.index ? "Preparing..." : "Learn Again"}
              </button>
            )}
          </motion.article>
        ))}
      </div>
    </section>
  );
}

function LearnAgainResult({
  score,
  review,
}: {
  score: number;
  review: ReviewItem[];
}) {
  const incorrect = review.length - score;
  const percentage = review.length ? Math.round((score / review.length) * 100) : 0;

  return (
    <section className="learn-result-section" aria-labelledby="learn-result-title">
      <div className="learn-result-card">
        <span className="eyebrow">Learn Again Result</span>
        <h2 id="learn-result-title">Concept Practice Complete</h2>
        <div className="learn-score">{score} / {review.length}</div>
        <p>{percentage}% correct</p>

        <div className="learn-stats" aria-label="Learn Again score breakdown">
          <div className="learn-stat">
            <span className="learn-stat-value">{score}</span>
            <span>Correct</span>
          </div>
          <div className="learn-stat">
            <span className="learn-stat-value">{incorrect}</span>
            <span>Incorrect</span>
          </div>
        </div>
      </div>

      <div className="learn-review">
        <div className="review-heading">
          <div>
            <span className="eyebrow">Answer key</span>
            <h2>Learn Again Answers</h2>
          </div>
          <span className="review-count">{review.length} questions</span>
        </div>

        <div className="review-list">
          {review.map((item, index) => (
            <motion.article className="review-item learn-review-item" key={item.index} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.06, duration: 0.35 }} whileHover={{ y: -3, scale: 1.005 }}>
              <div
                className={`review-status ${item.correct ? "correct" : "incorrect"}`}
                aria-label={item.correct ? "Correct" : "Incorrect"}
              >
                {item.correct ? "✓" : "×"}
              </div>

              <div className="review-content">
                <div className="review-number">Question {item.index + 1}</div>
                <div className="review-question"><MathText>{item.question.question}</MathText></div>
                <div className="review-answer">
                  Your answer: <strong>
                    {item.selected != null
                      ? <MathText>{item.question.options[item.selected - 1]}</MathText>
                      : "Not answered"}
                  </strong>
                  {!item.correct && (
                    <> · Right answer: <strong><MathText>{item.question.options[item.question.correct_option - 1]}</MathText></strong></>
                  )}
                </div>
              </div>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}

function parseStoredList(value: string): string[] {
  try {
    const parsed: unknown = JSON.parse(value);
    if (Array.isArray(parsed)) {
      return parsed.filter((item): item is string => typeof item === "string");
    }
  } catch {
    // Fall through to the legacy delimiter format.
  }

  return value.split(", ").map((item) => item.trim()).filter((item) => item.length > 0);
}

function HistoryReview({ historyDetail }: { historyDetail: HistoryDetail }) {
  const aiQuestionsList = parseStoredList(historyDetail.ai_questions);
  const aiAnswersList = parseStoredList(historyDetail.ai_answers);

  const wrongQuestions = historyDetail.wrong_answered_question
    ? historyDetail.wrong_answered_question
      .split(", ")
      .map((q) => q.trim())
      .filter((q) => q.length > 0)
    : [];

  // Parse score to get total questions
  const scoreParts = historyDetail.score.split("/");
  const totalQuestions = scoreParts.length === 2 ? parseInt(scoreParts[1]) : aiQuestionsList.length;

  // Ensure answer list matches question list length
  const answersWithFallback = aiQuestionsList.map((_, index) => aiAnswersList[index] || "Not recorded");

  return (
    <section className="review-section history-review-section" aria-labelledby="history-review-title">
      <div className="review-heading">
        <div>
          <span className="eyebrow">Your Question</span>
          <h2 id="history-review-title">Question & Answer Review</h2>
        </div>
      </div>

      {/* User Question */}
      <div className="user-question-section">
        <div className="review-item user-question-review">
          <div className="review-content">
            <div className="review-label">Your Original Question</div>
            <div className="review-question">{historyDetail.user_question}</div>
          </div>
        </div>
      </div>

      {/* AI Generated Questions and Answers */}
      <div className="review-heading" style={{ marginTop: "2rem" }}>
        <div>
          <span className="eyebrow">Practice Questions</span>
          <h3>Generated Questions & Your Responses</h3>
        </div>
        <span className="review-count">{totalQuestions} questions</span>
      </div>

      <div className="review-list">
        {aiQuestionsList.map((question, index) => {
          const isWrong = wrongQuestions.some((wq) => question.includes(wq) || wq.includes(question.substring(0, 30)));
          return (
            <article className="review-item history-review-item" key={index}>
              <div
                className={`review-status ${isWrong ? "incorrect" : "correct"}`}
                aria-label={isWrong ? "Incorrect" : "Correct"}
              >
                {isWrong ? "×" : "✓"}
              </div>
              <div className="review-content">
                <div className="review-number">Question {index + 1}</div>
                <div className="review-question"><MathText>{question}</MathText></div>
                <div className="review-answer">
                  Correct answer: <strong><MathText>{answersWithFallback[index]}</MathText></strong>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default App;

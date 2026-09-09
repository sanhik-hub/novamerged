
import type {
  AuthResponse,
  LearnAgainResponse,
  QuestionResponse,
  Coordinate,
  HistoryEntry,
  HistoryDetail,
} from "../types";

const API_URL = (import.meta.env.VITE_API_URL ?? "").trim().replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function friendlyHttpMessage(status: number, serverMessage?: string): string {
  if (serverMessage) {
    if (serverMessage.includes("Failed to get response from Gemini API")) {
      return "Nova AI could not generate a practice session. Please try again.";
    }
    if (serverMessage.includes("Database")) {
      return "Nova AI is having trouble accessing your account. Please try again.";
    }
    return serverMessage;
  }

  switch (status) {
    case 400:
      return "Please check the information you entered.";
    case 401:
      return "Incorrect password.";
    case 404:
      return "Username not found.";
    case 409:
      return "That username already exists.";
    case 500:
      return "Nova AI is temporarily unavailable. Please try again.";
    default:
      return "Unable to connect to Nova AI. Please try again.";
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  if (!API_URL) {
    throw new ApiError(
      "Nova AI is not configured. Set VITE_API_URL in the frontend environment.",
    );
  }

  let response: Response;

  try {
    response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError("Unable to connect to Nova AI. Please try again.");
  }

  const raw = await response.text();

  let data: unknown = {};

  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      throw new ApiError(
        "Nova AI returned an invalid response.",
        response.status,
      );
    }
  }

  if (!response.ok) {
    const message =
      typeof data === "object" &&
      data !== null &&
      "error" in data &&
      typeof data.error === "string"
        ? data.error
        : undefined;

    throw new ApiError(
      friendlyHttpMessage(response.status, message),
      response.status,
    );
  }

  return data as T;
}

// -------------------------
// AUTHENTICATION
// -------------------------

export function signup(
  username: string,
  password: string,
): Promise<AuthResponse> {
  return request<AuthResponse>("/NewUser_login", {
    method: "POST",
    body: JSON.stringify({
      Username: username,
      NewPassword: password,
    }),
  });
}

export function login(
  username: string,
  password: string,
): Promise<AuthResponse> {
  return request<AuthResponse>("/Old_User_login", {
    method: "POST",
    body: JSON.stringify({
      Username: username,
      Password: password,
    }),
  });
}

// -------------------------
// STANDARD QUESTION
// -------------------------

export function postQuestion(
  username: string,
  question: string,
  imagePath = "",
): Promise<QuestionResponse> {
  return request<QuestionResponse>("/QuestionPost", {
    method: "POST",
    body: JSON.stringify({
      Username: username,
      Question: question,
      Image_path: imagePath,
    }),
  });
}

// -------------------------
// GRAPHICAL QUESTION
// -------------------------

export function postGraphicalQuestion(
  username: string,
  question: string,
  coordinates: Coordinate[],
): Promise<QuestionResponse> {
  return request<QuestionResponse>("/GraphicalQuestionPost", {
    method: "POST",
    body: JSON.stringify({
      Username: username,
      Question: question,
      Coordinates: coordinates,
    }),
  });
}

// -------------------------
// SCORE
// -------------------------

export function postScore(
  username: string,
  questionJson: string,
  wrongAnsweredQuestions: string,
  score: string,
): Promise<{ message: string }> {
  return request<{ message: string }>("/ScorePost", {
    method: "POST",
    body: JSON.stringify({
      Username: username,
      QuestionJson: questionJson,
      wrong_answered_questions: wrongAnsweredQuestions,
      Score: score,
    }),
  });
}

// -------------------------
// WRONG ANSWER / LEARN AGAIN
// -------------------------

export function postDoubtQuestion(
  username: string,
  wrongAnsweredQuestion: string,
  questionJson: string,
): Promise<LearnAgainResponse> {
  return request<LearnAgainResponse>("/DoubtQuestionPost", {
    method: "POST",
    body: JSON.stringify({
      Username: username,
      WrongAnsweredquestion: wrongAnsweredQuestion,
      QuestionJson: questionJson,
    }),
  });
}

// -------------------------
// HISTORY
// -------------------------

export type HistoryResponse = {
  message: string;
  data: HistoryEntry[];
};

export type HistoryDetailResponse = {
  message: string;
  data: HistoryDetail;
};

export function getUserHistory(
  username: string,
): Promise<HistoryResponse> {
  return request<HistoryResponse>("/GetUserHistory", {
    method: "POST",
    body: JSON.stringify({
      Username: username,
    }),
  });
}

export function getHistoryDetail(
  username: string,
  historyId: number,
): Promise<HistoryDetailResponse> {
  return request<HistoryDetailResponse>("/GetHistoryDetail", {
    method: "POST",
    body: JSON.stringify({
      Username: username,
      HistoryId: historyId,
    }),
  });
}


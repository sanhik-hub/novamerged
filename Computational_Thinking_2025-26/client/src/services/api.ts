import type {
  AuthResponse,
  LearnAgainResponse,
  QuestionResponse,
  Coordinate,
  HistoryEntry,
  HistoryDetail,
} from "../types";

const API_URL = (import.meta.env.VITE_API_URL ?? "").trim().replace(/\/$/, "");

const AUTH_TOKEN_KEY = "nova_ai_auth_token";

function getAuthToken(): string | null {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

function storeAuthToken(token: string): void {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

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
      return "Prism AI could not generate a practice session. Please try again.";
    }
    if (serverMessage.includes("Database")) {
      return "Prism AI is having trouble accessing your account. Please try again.";
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
      return "Prism AI is temporarily unavailable. Please try again.";
    default:
      return "Unable to connect to Prism AI. Please try again.";
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  if (!API_URL) {
    throw new ApiError(
      "Prism AI is not configured. Set VITE_API_URL in the frontend environment.",
    );
  }

  let response: Response;

  try {
    response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(getAuthToken()
          ? { Authorization: `Bearer ${getAuthToken()}` }
          : {}),
        ...(options.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError("Unable to connect to Prism AI. Please try again.");
  }

  const raw = await response.text();

  let data: unknown = {};

  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      throw new ApiError(
        "Prism AI returned an invalid response.",
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
  _standard: number,
): Promise<AuthResponse> {
  return request<AuthResponse>("/NewUser_login", {
    method: "POST",
    body: JSON.stringify({
      Username: username,
      NewPassword: password,
    }),
  }).then((response) => {
    storeAuthToken(response.data.token);
    return response;
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
  }).then((response) => {
    storeAuthToken(response.data.token);
    return response;
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

// === NOVA WORKSPACE API ===

import type {
  Workspace,
  WorkspaceSettings,
  WorkspaceQuestion,
  WorkspaceSolution,
  WorkspaceAttempt,
  WorkspaceInvitation,
  WorkspaceFollowUp,
  WorkspaceApiResponse,
  WorkspaceComputeRequest,
  WorkspaceQuestionCreateRequest,
  WorkspaceSettingsUpdateRequest,
} from "../types";

type WorkspaceDataResponse<T> = Promise<WorkspaceApiResponse<T>>;

export function createWorkspace(name: string): WorkspaceDataResponse<Workspace> {
  return request<WorkspaceApiResponse<Workspace>>("/WorkspaceCreate", {
    method: "POST",
    body: JSON.stringify({ Name: name }),
  });
}

export function joinWorkspace(joinCode: string): WorkspaceDataResponse<Workspace> {
  return request<WorkspaceApiResponse<Workspace>>("/WorkspaceJoin", {
    method: "POST",
    body: JSON.stringify({ JoinCode: joinCode }),
  });
}

export function getWorkspaces(): WorkspaceDataResponse<Workspace[]> {
  return request<WorkspaceApiResponse<Workspace[]>>("/Workspaces", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getWorkspaceDetails(
  workspaceId: number,
): WorkspaceDataResponse<Workspace> {
  return request<WorkspaceApiResponse<Workspace>>("/WorkspaceDetails", {
    method: "POST",
    body: JSON.stringify({ WorkspaceId: workspaceId }),
  });
}

export function leaveWorkspace(
  workspaceId: number,
): WorkspaceDataResponse<unknown> {
  return request<WorkspaceApiResponse<unknown>>("/WorkspaceLeave", {
    method: "POST",
    body: JSON.stringify({ WorkspaceId: workspaceId }),
  });
}

export function inviteToWorkspace(
  workspaceId: number,
  username: string,
): WorkspaceDataResponse<unknown> {
  return request<WorkspaceApiResponse<unknown>>("/WorkspaceInvite", {
    method: "POST",
    body: JSON.stringify({
      WorkspaceId: workspaceId,
      Username: username,
    }),
  });
}

export function getWorkspaceInvitations(): WorkspaceDataResponse<WorkspaceInvitation[]> {
  return request<WorkspaceApiResponse<WorkspaceInvitation[]>>(
    "/WorkspaceInvitations",
    {
      method: "POST",
      body: JSON.stringify({}),
    },
  );
}

export function getWorkspaceSentInvitations(
  workspaceId: number,
): WorkspaceDataResponse<WorkspaceInvitation[]> {
  return request<WorkspaceApiResponse<WorkspaceInvitation[]>>(
    "/WorkspaceSentInvitations",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
      }),
    },
  );
}

export function acceptWorkspaceInvitation(
  invitationId: number,
): WorkspaceDataResponse<unknown> {
  return request<WorkspaceApiResponse<unknown>>(
    "/WorkspaceInvitationAccept",
    {
      method: "POST",
      body: JSON.stringify({ InvitationId: invitationId }),
    },
  );
}

export function declineWorkspaceInvitation(
  invitationId: number,
): WorkspaceDataResponse<unknown> {
  return request<WorkspaceApiResponse<unknown>>(
    "/WorkspaceInvitationDecline",
    {
      method: "POST",
      body: JSON.stringify({ InvitationId: invitationId }),
    },
  );
}

export function promoteWorkspaceMember(
  workspaceId: number,
  username: string,
): WorkspaceDataResponse<unknown> {
  return request<WorkspaceApiResponse<unknown>>("/WorkspacePromote", {
    method: "POST",
    body: JSON.stringify({
      WorkspaceId: workspaceId,
      Username: username,
    }),
  });
}

export function removeWorkspaceMember(
  workspaceId: number,
  username: string,
): WorkspaceDataResponse<unknown> {
  return request<WorkspaceApiResponse<unknown>>("/WorkspaceRemoveMember", {
    method: "POST",
    body: JSON.stringify({
      WorkspaceId: workspaceId,
      MemberUsername: username,
    }),
  });
}

export function transferWorkspaceOwnership(
  workspaceId: number,
  username: string,
): WorkspaceDataResponse<unknown> {
  return request<WorkspaceApiResponse<unknown>>(
    "/WorkspaceTransferOwnership",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        MemberUsername: username,
      }),
    },
  );
}

export type WorkspaceRoleValue = "member" | "teacher" | "admin" | "owner" | string;

export function updateWorkspaceSettings(
  settings: WorkspaceSettingsUpdateRequest,
): WorkspaceDataResponse<WorkspaceSettings> {
  return request<WorkspaceApiResponse<WorkspaceSettings>>(
    "/WorkspaceSettingsUpdate",
    {
      method: "POST",
      body: JSON.stringify(settings),
    },
  );
}

export function createWorkspaceQuestion(
  question: WorkspaceQuestionCreateRequest,
): WorkspaceDataResponse<WorkspaceQuestion> {
  return request<WorkspaceApiResponse<WorkspaceQuestion>>(
    "/WorkspaceQuestionCreate",
    {
      method: "POST",
      body: JSON.stringify(question),
    },
  );
}

export function getWorkspaceQuestions(
  workspaceId: number,
): WorkspaceDataResponse<WorkspaceQuestion[]> {
  return request<WorkspaceApiResponse<WorkspaceQuestion[]>>(
    "/WorkspaceQuestions",
    {
      method: "POST",
      body: JSON.stringify({ WorkspaceId: workspaceId }),
    },
  );
}

export function getWorkspaceQuestionDetails(
  workspaceId: number,
  questionId: number,
): WorkspaceDataResponse<WorkspaceQuestion> {
  return request<WorkspaceApiResponse<WorkspaceQuestion>>(
    "/WorkspaceQuestionDetails",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        QuestionId: questionId,
      }),
    },
  );
}


export function deleteWorkspaceQuestion(
  workspaceId: number,
  questionId: number,
): WorkspaceDataResponse<{ id: number; deleted: boolean }> {
  return request<
    WorkspaceApiResponse<{ id: number; deleted: boolean }>
  >(
    "/WorkspaceQuestionDelete",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        QuestionId: questionId,
      }),
    },
  );
}
export function getWorkspaceQuestionSolution(
  workspaceId: number,
  questionId: number,
): WorkspaceDataResponse<WorkspaceSolution | null> {
  return request<WorkspaceApiResponse<WorkspaceSolution | null>>(
    "/WorkspaceQuestionSolution",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        QuestionId: questionId,
      }),
    },
  );
}

export function storeWorkspaceQuestionSolution(
  workspaceId: number,
  questionId: number,
  engine: string,
  result: unknown,
): WorkspaceDataResponse<WorkspaceSolution> {
  return request<WorkspaceApiResponse<WorkspaceSolution>>(
    "/WorkspaceQuestionSolutionStore",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        QuestionId: questionId,
        Engine: engine,
        Result: result,
      }),
    },
  );
}

export function computeWorkspaceQuestion(
  payload: WorkspaceComputeRequest,
): Promise<unknown> {
  return request<unknown>("/WorkspaceQuestionCompute", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createWorkspaceAttempt(
  workspaceId: number,
  questionId: number,
  mode: string,
  submittedAnswer: string,
): WorkspaceDataResponse<WorkspaceAttempt> {
  return request<WorkspaceApiResponse<WorkspaceAttempt>>(
    "/WorkspaceQuestionAttemptCreate",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        QuestionId: questionId,
        Mode: mode,
        SubmittedAnswer: submittedAnswer,
      }),
    },
  );
}

export function completeWorkspaceAttempt(
  workspaceId: number,
  attemptId: number,
  result: unknown,
  score: number,
  solutionRevealed: boolean,
): WorkspaceDataResponse<WorkspaceAttempt> {
  return request<WorkspaceApiResponse<WorkspaceAttempt>>(
    "/WorkspaceQuestionAttemptComplete",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        AttemptId: attemptId,
        Result: result,
        Score: score,
        SolutionRevealed: solutionRevealed,
      }),
    },
  );
}

export function exitWorkspaceAttempt(
  workspaceId: number,
  attemptId: number,
): WorkspaceDataResponse<WorkspaceAttempt> {
  return request<WorkspaceApiResponse<WorkspaceAttempt>>(
    "/WorkspaceQuestionAttemptExit",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        AttemptId: attemptId,
      }),
    },
  );
}

export function terminateWorkspaceAttempt(
  workspaceId: number,
  attemptId: number,
): WorkspaceDataResponse<WorkspaceAttempt> {
  return request<WorkspaceApiResponse<WorkspaceAttempt>>(
    "/WorkspaceQuestionAttemptTerminate",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        AttemptId: attemptId,
      }),
    },
  );
}

export function getWorkspaceQuestionAttempts(
  workspaceId: number,
  questionId: number,
): WorkspaceDataResponse<WorkspaceAttempt[]> {
  return request<WorkspaceApiResponse<WorkspaceAttempt[]>>(
    "/WorkspaceQuestionAttempts",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        QuestionId: questionId,
      }),
    },
  );
}

export function getWorkspaceMemberPerformance(
  workspaceId: number,
  userId: number,
): WorkspaceDataResponse<WorkspaceAttempt[]> {
  return request<WorkspaceApiResponse<WorkspaceAttempt[]>>(
    "/WorkspaceMemberPerformance",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        UserId: userId,
      }),
    },
  );
}
export function postWorkspaceQuestionFollowUp(
  workspaceId: number,
  questionId: number,
  question: string,
  answer?: string,
  engine?: string,
): WorkspaceDataResponse<WorkspaceFollowUp> {
  return request<WorkspaceApiResponse<WorkspaceFollowUp>>(
    "/WorkspaceQuestionFollowUp",
    {
      method: "POST",
      body: JSON.stringify({
        WorkspaceId: workspaceId,
        QuestionId: questionId,
        Question: question,
        Answer: answer ?? "",
        Engine: engine ?? "wolfram",
      }),
    },
  );
}



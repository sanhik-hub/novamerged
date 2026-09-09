const API_URL = (import.meta.env.VITE_API_URL ?? "").trim().replace(/\/$/, "");

export type AdminUser = { id: number; username: string };
export type HistoryEntry = { id: number; user_question: string; score: string };
export type HistoryDetail = {
  id: number;
  user_question: string;
  ai_questions: string;
  ai_answers: string;
  score: string;
  wrong_answered_question: string | null;
  remarks: string | null;
};

async function request<T>(endpoint: string, body: Record<string, unknown>): Promise<T> {
  if (!API_URL) throw new Error("Admin API is not configured. Set VITE_API_URL.");

  let response: Response;
  try {
    response = await fetch(`${API_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Unable to connect to Nova AI.");
  }

  const data = await response.json().catch(() => ({})) as { error?: string };
  if (!response.ok) throw new Error(data.error || "The request failed.");
  return data as T;
}

export function adminLogin(username: string, password: string) {
  return request<{ message: string; data: AdminUser }>("/AdminLogin", {
    Username: username,
    Password: password,
  });
}

export function getStudentHistory(adminUsername: string, adminPassword: string, username: string) {
  return request<{ message: string; data: HistoryEntry[] }>("/AdminUserHistory", {
    AdminUsername: adminUsername,
    AdminPassword: adminPassword,
    Username: username,
  });
}

export function getStudentHistoryDetail(
  adminUsername: string,
  adminPassword: string,
  username: string,
  historyId: number,
) {
  return request<{ message: string; data: HistoryDetail }>("/AdminHistoryDetail", {
    AdminUsername: adminUsername,
    AdminPassword: adminPassword,
    Username: username,
    HistoryId: historyId,
  });
}

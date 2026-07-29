import type { ApiError, TaskStatus, TaskView, TripPlan } from "./types";

const API_PREFIX = "/api/v1";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers
    }
  });
  if (!response.ok) {
    const payload = (await response.json()) as ApiError;
    throw new Error(payload.error?.message ?? "请求失败");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function auth(token: string, version?: number): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    ...(version === undefined ? {} : { "If-Match": `"${version}"` })
  };
}

export async function createTask(message: string): Promise<{
  task_token: string;
  status: TaskStatus;
  row_version: number;
}> {
  return request("/planning-tasks", {
    method: "POST",
    body: JSON.stringify({ message })
  });
}

export async function getTask(token: string): Promise<TaskView> {
  return request("/planning-tasks/current", { headers: auth(token) });
}

export async function addMessage(
  token: string,
  version: number,
  message: string
): Promise<{ status: TaskStatus; row_version: number }> {
  return request("/planning-tasks/current/messages", {
    method: "POST",
    headers: auth(token, version),
    body: JSON.stringify({ message })
  });
}

export async function confirmTask(
  token: string,
  version: number
): Promise<{ status: TaskStatus; row_version: number }> {
  return request("/planning-tasks/current/confirmation", {
    method: "POST",
    headers: auth(token, version),
    body: JSON.stringify({ confirmed: true })
  });
}

export async function cancelTask(token: string): Promise<void> {
  await request("/planning-tasks/current/cancellation", {
    method: "POST",
    headers: auth(token)
  });
}

export async function getResult(token: string): Promise<TripPlan> {
  return request("/planning-tasks/current/result", { headers: auth(token) });
}

export async function savePlan(token: string): Promise<{
  plan_token: string;
  version: number;
  expires_at: string;
}> {
  return request("/planning-tasks/current/saved-plan", {
    method: "POST",
    headers: auth(token)
  });
}

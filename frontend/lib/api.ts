import type { components } from "./api-types";

type S = components["schemas"];

export type ProjectOut = S["ProjectOut"];
export type ProblemSpec = S["ProblemSpec"];
export type DataProfile = S["DataProfile"];
export type ColumnProfile = S["ColumnProfile"];
export type IntakeResponse = S["IntakeResponse"];
export type IntakeMessage = S["IntakeMessage"];
export type ProtectReport = S["ProtectReport"];
export type Finding = S["Finding"];
export type SplitPart = S["SplitPart"];
export type LeaderboardOut = S["LeaderboardOut"];
export type SubmissionOut = S["SubmissionOut"];
export type PackageOut = S["PackageOut"];
export type ValidationStep = S["ValidationStep"];
export type Stage = ProjectOut["stage"];
export type TemplateId = S["ProjectCreate"]["template"];

export type TemplateOut = { id: TemplateId; name: string; description: string; has_dataset: boolean };
export type SolverOut = { name: string; label: string; local: boolean; agent?: boolean };
export type DockerStatus = { available: boolean; info: string };
export type IntakeStatus = { offline: boolean; model: string; has_key: boolean };
export type ScoreOut = {
  rows: number;
  flagged: number;
  threshold: number;
  solver: string;
  preview: Record<string, unknown>[];
  columns: string[];
  download: string;
};

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let detail = `${res.status} ${res.statusText}`;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") detail = body.detail;
    else if (Array.isArray(body?.detail)) {
      detail = body.detail.map((d: { msg?: string; loc?: unknown[] }) => `${(d.loc || []).join(".")}: ${d.msg}`).join("; ");
    } else if (body?.detail) detail = JSON.stringify(body.detail);
  } catch {
    // keep the status text
  }
  return new ApiError(res.status, detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError(0, `Could not reach the backend at ${API_URL}. Start it and reload.`);
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function json(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
}

function form(file: File): FormData {
  const fd = new FormData();
  fd.append("file", file, file.name);
  return fd;
}

export const api = {
  templates: () => request<TemplateOut[]>("/templates"),
  intakeStatus: () => request<IntakeStatus>("/intake/status"),

  projects: () => request<ProjectOut[]>("/projects"),
  project: (id: string) => request<ProjectOut>(`/projects/${id}`),
  createProject: (template: TemplateId, name?: string) =>
    request<ProjectOut>("/projects", json("POST", { template, name })),
  deleteProject: (id: string) => request<{ ok: boolean }>(`/projects/${id}`, { method: "DELETE" }),

  uploadData: (id: string, file: File) =>
    request<DataProfile>(`/projects/${id}/data`, { method: "POST", body: form(file) }),
  profile: (id: string) => request<DataProfile>(`/projects/${id}/data/profile`),

  intake: (id: string, message: string) =>
    request<IntakeResponse>(`/projects/${id}/intake`, json("POST", { message })),
  intakeHistory: (id: string) => request<IntakeMessage[]>(`/projects/${id}/intake`),
  intakeReset: (id: string) => request<unknown>(`/projects/${id}/intake`, { method: "DELETE" }),

  putSpec: (id: string, spec: ProblemSpec) => request<ProjectOut>(`/projects/${id}/spec`, json("PUT", spec)),

  protect: (id: string) => request<ProtectReport>(`/projects/${id}/protect`, { method: "POST" }),
  protectReport: (id: string) => request<ProtectReport>(`/projects/${id}/protect/report`),

  solvers: () => request<SolverOut[]>("/arena/solvers"),
  docker: () => request<DockerStatus>("/arena/docker"),
  arenaRun: (id: string, body: { solvers?: string[]; replay?: boolean; rebuild?: boolean } = {}) =>
    request<{ submission_ids: string[] }>(`/projects/${id}/arena/run`, json("POST", body)),
  arenaStatus: (id: string) => request<{ running: boolean }>(`/projects/${id}/arena/status`),
  arenaAgent: (id: string) => request<{ started: boolean; max_attempts: number }>(`/projects/${id}/arena/agent`, { method: "POST" }),
  leaderboard: (id: string) => request<LeaderboardOut>(`/projects/${id}/arena/leaderboard`),
  finalize: (id: string) => request<LeaderboardOut>(`/projects/${id}/arena/finalize`, { method: "POST" }),
  streamUrl: (id: string) => `${API_URL}/projects/${id}/arena/stream`,

  packageBuild: (id: string) => request<PackageOut>(`/projects/${id}/package`, { method: "POST" }),
  packageGet: (id: string) => request<PackageOut>(`/projects/${id}/package`),
  packageFile: (id: string, path: string) =>
    request<{ path: string; content: string }>(`/projects/${id}/package/file?path=${encodeURIComponent(path)}`),
  handoffUrl: (id: string) => `${API_URL}/projects/${id}/handoff`,

  score: (id: string, file: File, solver?: string) =>
    request<ScoreOut>(`/projects/${id}/score${solver ? `?solver=${encodeURIComponent(solver)}` : ""}`, {
      method: "POST",
      body: form(file),
    }),
  scoreDownloadUrl: (id: string) => `${API_URL}/projects/${id}/score/download`,
  sampleCsv: async (id: string, n = 2000): Promise<File> => {
    let res: Response;
    try {
      res = await fetch(`${API_URL}/projects/${id}/sample-csv?n=${n}`, { cache: "no-store" });
    } catch {
      throw new ApiError(0, `Could not reach the backend at ${API_URL}.`);
    }
    if (!res.ok) throw await parseError(res);
    const blob = await res.blob();
    return new File([blob], "new_rows.csv", { type: "text/csv" });
  },
};

export function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return String(e);
}

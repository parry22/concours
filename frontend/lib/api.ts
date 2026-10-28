import type { components } from "./api-types";

type S = components["schemas"];

// Fields with backend defaults are optional in the schema; the API always sends them.
export type ProjectOut = S["ProjectOut"] & { versions: S["ModelVersionOut"][] };
export type ProblemSpec = S["ProblemSpec"];
export type DataProfile = S["DataProfile"];
export type ColumnProfile = S["ColumnProfile"];
export type IntakeResponse = S["IntakeResponse"];
export type IntakeMessage = S["IntakeMessage"];
export type ProtectReport = S["ProtectReport"];
export type Finding = S["Finding"];
export type SplitPart = S["SplitPart"];
export type FairnessReport = S["FairnessReport"];
export type FraudSettings = S["FraudSettings"];
export type SchemaOut = S["SchemaOut"];
export type SchemaField = S["SchemaField"];
export type QueueOut = S["QueueOut"];
export type QueueCase = S["QueueCase"];
export type DriftOut = S["DriftOut"];
export type WeekHealth = S["WeekHealth"];
export type GateResult = S["GateResult"];
export type MaturitySummary = S["MaturitySummary"];
export type FairnessColumn = S["FairnessColumn"];
export type LeaderboardOut = S["LeaderboardOut"];
export type SubmissionOut = S["SubmissionOut"];
export type PackageOut = S["PackageOut"];
export type ValidationStep = S["ValidationStep"];
export type ValueReport = S["ValueReport"];
export type ValueParam = S["ValueParam"];
export type ValuePoint = S["ValuePoint"];
export type ValueParamsIn = S["ValueParamsIn"];
export type ModelVersionOut = S["ModelVersionOut"];
export type ListOut = S["ListOut"];
export type HealthOut = S["HealthOut"];
export type PlanOut = S["PlanOut"] & { lines: string[] };
export type ProjectSettingsIn = S["ProjectSettingsIn"];
export type ModelStatus = ProjectOut["model_status"];
export type Stage = ProjectOut["stage"];
export type TemplateId = S["ProjectCreate"]["template"];

export type TemplateOut = {
  id: TemplateId;
  name: string;
  description: string;
  label: string;
  icon: string;
  metric_line: string;
  goal: string;
  replies: string[];
  list: { name: string; top_n: number; row_label: string; action_label: string } | null;
  has_dataset: boolean;
  people?: boolean | null;
  source_url?: string | null;
  source_note?: string | null;
};
export type SolverOut = { name: string; label: string; local: boolean; agent?: boolean };
export type DockerStatus = { available: boolean; info: string };
export type IntakeStatus = { offline: boolean; model: string; has_key: boolean };

// Same origin by default (Next or the reverse proxy forwards /api to the backend), so the session cookie is first-party.
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

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
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", credentials: "include", ...init });
  } catch {
    throw new ApiError(0, `Could not reach the backend at ${API_URL}. Start it and reload.`);
  }
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/") && !window.location.pathname.startsWith("/login")) {
    // signed out (or the session expired): sign in, then come back here
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
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

export type Me = { id: string | null; email: string | null; name: string; org_id: string; org_name: string; role: string; auth: "required" | "off" };
export type AuthConfig = { auth: "required" | "off"; signup: string; first_run: boolean; can_signup: boolean };
export type ApiKey = { id: string; name: string; prefix: string; created_at: string; last_used_at?: string | null; token?: string | null };

export const api = {
  authConfig: () => request<AuthConfig>("/auth/config"),
  me: () => request<Me>("/auth/me"),
  login: (email: string, password: string) => request<Me>("/auth/login", json("POST", { email, password })),
  signup: (body: { email: string; password: string; name?: string; org_name?: string; invite?: string | null }) => request<Me>("/auth/signup", json("POST", body)),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  keys: () => request<ApiKey[]>("/auth/keys"),
  createKey: (name: string) => request<ApiKey>("/auth/keys", json("POST", { name })),
  revokeKey: (id: string) => request<{ ok: boolean }>(`/auth/keys/${id}`, { method: "DELETE" }),
  invite: (email: string) => request<{ token: string; expires_at: string }>("/auth/invites", json("POST", { email })),

  templates: () => request<TemplateOut[]>("/templates"),
  intakeStatus: () => request<IntakeStatus>("/intake/status"),

  projects: () => request<ProjectOut[]>("/projects"),
  project: (id: string) => request<ProjectOut>(`/projects/${id}`),
  createProject: (template: TemplateId, name?: string, sample = true) =>
    request<ProjectOut>("/projects", json("POST", { template, name, sample })),
  deleteProject: (id: string) => request<{ ok: boolean }>(`/projects/${id}`, { method: "DELETE" }),

  uploadData: (id: string, file: File) =>
    request<DataProfile>(`/projects/${id}/data`, { method: "POST", body: form(file) }),
  profile: (id: string) => request<DataProfile>(`/projects/${id}/data/profile`),

  intake: (id: string, message: string) =>
    request<IntakeResponse>(`/projects/${id}/intake`, json("POST", { message })),
  intakeHistory: (id: string) => request<IntakeMessage[]>(`/projects/${id}/intake`),
  intakeReset: (id: string) => request<unknown>(`/projects/${id}/intake`, { method: "DELETE" }),

  schema: (id: string) => request<SchemaOut>(`/projects/${id}/schema`),
  putSchema: (id: string, mapping: Record<string, string | null>) => request<ProjectOut>(`/projects/${id}/schema`, json("PUT", { mapping })),
  putFraudSettings: (id: string, body: FraudSettings) => request<ProjectOut>(`/projects/${id}/fraud-settings`, json("PUT", body)),
  fraudQuestions: () => request<{ questions: string[]; suggested: string[] }>("/intake/fraud-questions"),
  queue: (id: string) => request<QueueOut>(`/projects/${id}/queue`),
  labelCase: (id: string, tx: string, label: "fraud" | "not_fraud" | null) =>
    request<QueueOut>(`/projects/${id}/queue/${encodeURIComponent(tx)}/label`, json("POST", { label })),
  queueDownloadUrl: (id: string) => `${API_URL}/projects/${id}/queue/download`,
  drift: (id: string) => request<DriftOut | null>(`/projects/${id}/drift`),
  jump: (id: string, days = 28, autoRound = true) => request<DriftOut>(`/projects/${id}/clock`, json("POST", { days, auto_round: autoRound })),

  putSpec: (id: string, spec: ProblemSpec) => request<ProjectOut>(`/projects/${id}/spec`, json("PUT", spec)),

  protect: (id: string) => request<ProtectReport>(`/projects/${id}/protect`, { method: "POST" }),
  protectReport: (id: string) => request<ProtectReport>(`/projects/${id}/protect/report`),
  fairness: (id: string) => request<FairnessReport | null>(`/projects/${id}/fairness`),

  solvers: () => request<SolverOut[]>("/arena/solvers"),
  docker: () => request<DockerStatus>("/arena/docker"),
  arenaRun: (id: string, body: { solvers?: string[]; replay?: boolean; rebuild?: boolean } = {}) =>
    request<{ submission_ids: string[] }>(`/projects/${id}/arena/run`, json("POST", body)),
  arenaStatus: (id: string) => request<{ running: boolean }>(`/projects/${id}/arena/status`),
  arenaAgent: (id: string) => request<{ started: boolean; max_attempts: number }>(`/projects/${id}/arena/agent`, { method: "POST" }),
  leaderboard: (id: string) => request<LeaderboardOut>(`/projects/${id}/arena/leaderboard`),
  finalize: (id: string) => request<LeaderboardOut>(`/projects/${id}/arena/finalize`, { method: "POST" }),
  value: (id: string, solver?: string) => request<ValueReport>(`/projects/${id}/value${solver ? `?solver=${encodeURIComponent(solver)}` : ""}`),
  putValueParams: (id: string, body: ValueParamsIn, solver?: string) =>
    request<ValueReport>(`/projects/${id}/value/params${solver ? `?solver=${encodeURIComponent(solver)}` : ""}`, json("PUT", body)),
  streamUrl: (id: string) => `${API_URL}/projects/${id}/arena/stream`,

  packageBuild: (id: string) => request<PackageOut>(`/projects/${id}/package`, { method: "POST" }),
  packageGet: (id: string) => request<PackageOut>(`/projects/${id}/package`),
  packageFile: (id: string, path: string) =>
    request<{ path: string; content: string }>(`/projects/${id}/package/file?path=${encodeURIComponent(path)}`),
  handoffUrl: (id: string) => `${API_URL}/projects/${id}/handoff`,

  versions: (id: string) => request<ModelVersionOut[]>(`/projects/${id}/versions`),
  putSettings: (id: string, body: ProjectSettingsIn) => request<ProjectOut>(`/projects/${id}/settings`, json("PUT", body)),
  plan: (id: string) => request<PlanOut>(`/projects/${id}/plan`),

  lists: (id: string) => request<ListOut[]>(`/projects/${id}/lists`),
  list: (id: string, listId: string) => request<ListOut>(`/projects/${id}/lists/${listId}`),
  createList: (id: string, file?: File, opts: { sample?: boolean; top_n?: number } = {}) => {
    const q = new URLSearchParams();
    if (opts.sample) q.set("sample", "true");
    if (opts.top_n) q.set("top_n", String(opts.top_n));
    return request<ListOut>(`/projects/${id}/lists${q.size ? `?${q}` : ""}`, { method: "POST", body: file ? form(file) : new FormData() });
  },
  listDownloadUrl: (id: string, listId: string) => `${API_URL}/projects/${id}/lists/${listId}/download`,

  health: (id: string, file?: File, opts: { sample?: boolean; degrade?: boolean } = {}) => {
    const q = new URLSearchParams();
    if (opts.sample) q.set("sample", "true");
    if (opts.degrade) q.set("degrade", "true");
    return request<HealthOut>(`/projects/${id}/health${q.size ? `?${q}` : ""}`, { method: "POST", body: file ? form(file) : new FormData() });
  },
};

export function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return String(e);
}

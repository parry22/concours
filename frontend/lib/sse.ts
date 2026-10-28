import type { LeaderboardOut, ModelVersionOut, SubmissionOut } from "./api";

export type ArenaEvent =
  | { type: "connected" }
  | { type: "log"; line: string }
  | { type: "submission_started"; id: string; solver: string; cached: boolean }
  | { type: "submission_scored"; submission: SubmissionOut }
  | { type: "leaderboard_updated"; board: LeaderboardOut }
  | { type: "run_complete"; ids: string[]; purpose?: string }
  | { type: "finalized"; board: LeaderboardOut }
  | { type: "model_version"; version: ModelVersionOut }
  | { type: "model_promoted"; version: ModelVersionOut }
  | { type: "ping" }
  | { type: "error" };

const EVENT_NAMES = ["connected", "log", "submission_started", "submission_scored", "leaderboard_updated", "run_complete", "finalized", "model_version", "model_promoted", "ping"] as const;

function parse(name: string, raw: string): ArenaEvent | null {
  let data: unknown = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = {};
  }
  const d = data as Record<string, unknown>;
  switch (name) {
    case "connected":
      return { type: "connected" };
    case "ping":
      return { type: "ping" };
    case "log":
      return { type: "log", line: String(d.line ?? "") };
    case "submission_started":
      return { type: "submission_started", id: String(d.id), solver: String(d.solver), cached: Boolean(d.cached) };
    case "submission_scored":
      return { type: "submission_scored", submission: data as SubmissionOut };
    case "leaderboard_updated":
      return { type: "leaderboard_updated", board: data as LeaderboardOut };
    case "finalized":
      return { type: "finalized", board: data as LeaderboardOut };
    case "run_complete":
      return { type: "run_complete", ids: (d.ids as string[]) ?? [], purpose: d.purpose ? String(d.purpose) : undefined };
    case "model_version":
      return { type: "model_version", version: data as ModelVersionOut };
    case "model_promoted":
      return { type: "model_promoted", version: data as ModelVersionOut };
    default:
      return null;
  }
}

/** Open the project event stream. Returns a close function. */
export function openArenaStream(url: string, onEvent: (e: ArenaEvent) => void): () => void {
  const es = new EventSource(url, { withCredentials: true });
  for (const name of EVENT_NAMES) {
    es.addEventListener(name, (ev) => {
      const parsed = parse(name, (ev as MessageEvent).data);
      if (parsed) onEvent(parsed);
    });
  }
  es.onerror = () => onEvent({ type: "error" });
  return () => es.close();
}

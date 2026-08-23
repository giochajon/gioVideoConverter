export interface Job {
  id: string;
  mode: string;
  source_path: string;
  dest_path?: string;
  status: string;
  progress: string;
  preset: string;
  initial_size?: string;
  final_size?: string;
  started_at?: string;
  finished_at?: string;
  error?: string;
}

export interface StatusResponse {
  jobs: Job[];
  queue_interactive_len: number;
  queue_batch_len: number;
  halted: { job_id: string; error: string; at: string } | null;
}

export interface SettingsResponse {
  preset: string;
  batch_enabled: boolean;
  batch_target: "none" | "movies" | "series";
  batch_start_time: string;
  batch_stop_time: string;
  movie_dir: string;
  series_dir: string;
  interactive_dir: string;
}

export interface BrowseEntry {
  name: string;
  path: string;
  size?: number;
}

export interface BrowseResponse {
  cwd: string;
  dirs: BrowseEntry[];
  files: BrowseEntry[];
}

export type BrowseRoot = "interactive" | "movies" | "series";

export interface RootInfo {
  path: string;
  readable: boolean;
  writable: boolean;
}

export type RootsResponse = Record<BrowseRoot, RootInfo>;

export interface BatchLogEntry {
  started_at: string;
  finished_at?: string;
  duration_seconds?: number;
  filename: string;
  initial_size: number;
  final_size: number | null;
  status: string;
}

export interface TonightEntry {
  source_path: string;
  initial_size?: string;
  status?: string;
  progress?: string;
  id?: string;
}

export interface TonightResponse {
  queued: boolean;
  jobs: TonightEntry[];
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

export const api = {
  browse: (root: BrowseRoot, path: string) =>
    fetch(`/api/browse/${root}?path=${encodeURIComponent(path)}`).then((r) => json<BrowseResponse>(r)),
  roots: () => fetch("/api/browse/roots").then((r) => json<RootsResponse>(r)),
  status: () => fetch("/api/queue/status").then((r) => json<StatusResponse>(r)),
  enqueue: (paths: string[]) =>
    fetch("/api/queue/enqueue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paths }),
    }).then((r) => json(r)),
  stopAll: () => fetch("/api/queue/stop-all", { method: "POST" }).then((r) => json(r)),
  resume: () => fetch("/api/queue/resume", { method: "POST" }).then((r) => json(r)),
  getSettings: () => fetch("/api/settings").then((r) => json<SettingsResponse>(r)),
  putSettings: (update: Partial<SettingsResponse>) =>
    fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    }).then((r) => json<SettingsResponse>(r)),
  presets: () => fetch("/api/settings/presets").then((r) => json<string[]>(r)),
  batchTonight: () => fetch("/api/batch/tonight").then((r) => json<TonightResponse>(r)),
  batchLog: () => fetch("/api/batch/log").then((r) => json<BatchLogEntry[]>(r)),
  removeBatchQueueItem: (jobId: string) =>
    fetch(`/api/batch/queue/${encodeURIComponent(jobId)}`, { method: "DELETE" }).then((r) => json(r)),
  removeBatchLogEntry: (startedAt: string) =>
    fetch("/api/batch/log/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ started_at: startedAt }),
    }).then((r) => json(r)),
  pruneBatchLog: () =>
    fetch("/api/batch/log/prune", { method: "POST" }).then((r) => json<{ removed: number }>(r)),
  recalculateBatch: () =>
    fetch("/api/batch/recalculate", { method: "POST" }).then((r) => json<{ queued: number }>(r)),
};

export function formatBytes(bytes?: string | number): string {
  const n = typeof bytes === "string" ? parseInt(bytes, 10) : bytes;
  if (!n || Number.isNaN(n)) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let val = n;
  let i = 0;
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return `${val.toFixed(1)} ${units[i]}`;
}

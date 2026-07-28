import { useCallback, useEffect, useState } from "react";
import { api, BatchLogEntry, BrowseResponse, BrowseRoot, RootsResponse, StatusResponse, formatBytes } from "../api";

const ROOT_LABELS: Record<BrowseRoot, string> = {
  interactive: "Interactive",
  movies: "Movies",
  series: "Series",
};

function formatDuration(seconds?: number): string {
  if (seconds == null) return "-";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function Interactive() {
  const [root, setRoot] = useState<BrowseRoot>("interactive");
  const [roots, setRoots] = useState<RootsResponse | null>(null);
  const [browse, setBrowse] = useState<BrowseResponse | null>(null);
  const [cwd, setCwd] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"queue" | "log">("queue");
  const [log, setLog] = useState<BatchLogEntry[]>([]);

  const loadBrowse = useCallback((forRoot: BrowseRoot, path: string) => {
    setLoading(true);
    setError(null);
    api
      .browse(forRoot, path)
      .then((res) => {
        setBrowse(res);
        setCwd(path);
      })
      .catch((err) => setError(err.message || "failed to load folder"))
      .finally(() => setLoading(false));
  }, []);

  const loadStatus = useCallback(() => {
    api.status().then(setStatus).catch(() => {});
  }, []);

  const loadRoots = useCallback(() => {
    api.roots().then(setRoots).catch(() => {});
  }, []);

  const loadLog = useCallback(() => {
    api.batchLog().then(setLog).catch(() => {});
  }, []);

  useEffect(() => {
    loadRoots();
    loadStatus();
    const interval = setInterval(loadStatus, 2000);
    return () => clearInterval(interval);
  }, [loadRoots, loadStatus]);

  useEffect(() => {
    loadLog();
    const interval = setInterval(loadLog, 5000);
    return () => clearInterval(interval);
  }, [loadLog]);

  useEffect(() => {
    loadBrowse(root, "");
    setSelected(new Set());
  }, [root, loadBrowse]);

  function switchRoot(next: BrowseRoot) {
    if (next === root) return;
    setRoot(next);
  }

  function toggleSelect(path: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  async function enqueueSelected() {
    if (selected.size === 0) return;
    await api.enqueue(Array.from(selected));
    setSelected(new Set());
    loadStatus();
  }

  async function stopAll() {
    if (!confirm("Stop all conversion processes and clear the interactive queue?")) return;
    await api.stopAll();
    loadStatus();
  }

  async function resume() {
    await api.resume();
    loadStatus();
  }

  async function removeLogEntry(startedAt: string) {
    await api.removeBatchLogEntry(startedAt);
    loadLog();
  }

  async function pruneLog() {
    if (!confirm("Delete all log entries older than one week?")) return;
    await api.pruneBatchLog();
    loadLog();
  }

  const parts = cwd.split("/").filter(Boolean);
  const currentRootInfo = roots?.[root];
  const permOk = !currentRootInfo || (currentRootInfo.readable && currentRootInfo.writable);

  return (
    <div>
      <div className="toolbar">
        <h1>Interactive Mode</h1>
        <button className="stop" onClick={stopAll}>■ STOP ALL</button>
      </div>

      {status?.halted && (
        <div className="halt-banner">
          <div>
            <strong>Processing halted</strong> — a conversion failed and the queue was left untouched for review.
            <div style={{ fontSize: "0.85rem", opacity: 0.85 }}>{status.halted.error}</div>
          </div>
          <button onClick={resume}>Resume</button>
        </div>
      )}

      <div className="panel">
        <div className="root-tabs">
          {(Object.keys(ROOT_LABELS) as BrowseRoot[]).map((key) => {
            const info = roots?.[key];
            const bad = info && (!info.readable || !info.writable);
            return (
              <button
                key={key}
                className={key === root ? "primary" : ""}
                onClick={() => switchRoot(key)}
                title={info?.path}
              >
                {ROOT_LABELS[key]}
                {bad ? " ⚠" : ""}
              </button>
            );
          })}
        </div>

        {currentRootInfo && !permOk && (
          <div className="perm-warning">
            <strong>{ROOT_LABELS[root]}</strong> ({currentRootInfo.path}):{" "}
            {!currentRootInfo.readable && "no read access — this folder can't be browsed."}
            {currentRootInfo.readable && !currentRootInfo.writable &&
              "no write access — files can be browsed but conversion will fail (can't write the output or delete the original)."}
          </div>
        )}

        <div className="breadcrumb">
          <a href="#" onClick={(e) => { e.preventDefault(); loadBrowse(root, ""); }}>{ROOT_LABELS[root]}</a>
          {parts.map((p, i) => (
            <span key={i}>
              {" / "}
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  loadBrowse(root, parts.slice(0, i + 1).join("/"));
                }}
              >
                {p}
              </a>
            </span>
          ))}
        </div>

        {loading && <p>Loading...</p>}
        {error && <p style={{ color: "#f87171" }}>{error}</p>}

        {browse?.dirs.map((d) => (
          <div className="dir-row" key={d.path}>
            <a href="#" onClick={(e) => { e.preventDefault(); loadBrowse(root, d.path); }}>📁 {d.name}</a>
          </div>
        ))}

        {browse?.files.map((f) => (
          <div className="file-row" key={f.path}>
            <input
              type="checkbox"
              checked={selected.has(f.path)}
              onChange={() => toggleSelect(f.path)}
            />
            <span>{f.name}</span>
            <span style={{ color: "#9aa4b2", fontSize: "0.85rem" }}>{formatBytes(f.size)}</span>
          </div>
        ))}

        <div style={{ marginTop: "1rem" }}>
          <button
            className="primary"
            disabled={selected.size === 0 || currentRootInfo?.writable === false}
            onClick={enqueueSelected}
          >
            Enqueue Selected ({selected.size})
          </button>
        </div>
      </div>

      <div className="root-tabs">
        <button className={view === "queue" ? "primary" : ""} onClick={() => setView("queue")}>
          Queued
        </button>
        <button className={view === "log" ? "primary" : ""} onClick={() => setView("log")}>
          Recently Processed
        </button>
      </div>

      {view === "queue" && (
        <div className="panel">
          <h2>Queue &amp; Status</h2>
          <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Size</th>
              </tr>
            </thead>
            <tbody>
              {status?.jobs.map((j) => (
                <tr key={j.id}>
                  <td>{j.source_path.split("/").pop()}</td>
                  <td>{j.mode}</td>
                  <td><span className={`badge ${j.status}`}>{j.status}</span></td>
                  <td>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${Number(j.progress || 0)}%` }} />
                    </div>
                  </td>
                  <td>
                    {formatBytes(j.initial_size)}
                    {j.final_size ? ` → ${formatBytes(j.final_size)}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {view === "log" && (
        <div className="panel">
          <div className="toolbar">
            <h2>Conversion Log</h2>
            <button onClick={pruneLog}>Delete older than 1 week</button>
          </div>
          <table>
            <thead>
              <tr>
                <th>Started</th>
                <th>Finished</th>
                <th>Duration</th>
                <th>File</th>
                <th>Before</th>
                <th>After</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {log.map((entry, i) => (
                <tr key={i}>
                  <td>{new Date(entry.started_at).toLocaleString()}</td>
                  <td>{entry.finished_at ? new Date(entry.finished_at).toLocaleString() : "-"}</td>
                  <td>{formatDuration(entry.duration_seconds)}</td>
                  <td>{entry.filename}</td>
                  <td>{formatBytes(entry.initial_size)}</td>
                  <td>{entry.final_size ? formatBytes(entry.final_size) : "-"}</td>
                  <td><span className={`badge ${entry.status}`}>{entry.status}</span></td>
                  <td>
                    <button onClick={() => removeLogEntry(entry.started_at)}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
